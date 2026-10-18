"""Serien: Tabellen aus CSV/Excel bzw. Nummerierung und Platzhalter ``{Spalte}`` im Text.

Qt-frei. Tabellendateien sind fremde Eingabe: Größe, Zeilen und Spalten sind begrenzt (Zeilen
werden gestreamt, leere sofort verworfen), jeder Fehler wird zur deutschen ``SeriesError`` –
nie ein Traceback.
"""
from __future__ import annotations

import copy
import csv
import datetime
import io
import itertools
import os
import re
import stat
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from .document import (CUTS, MAX_DIGITS, MAX_NUMBER, MAX_SERIES_ROWS, Document, Numbering,
                       Paragraph, Series, Span, TextObject)
from .storage import LINE_BREAKS

MAX_BYTES = 20 * 1024 * 1024        # Tabellendatei
MAX_UNPACKED = 200 * 1024 * 1024    # Excel: ausgepackt (gegen Zip-Bomben)
MAX_ROWS = MAX_SERIES_ROWS          # Zeilen ohne Spaltennamen (leere zählen nicht)
MAX_COLUMNS = 200
MAX_CELL = 100_000                  # Zeichen je Zelle (CSV)
CSV_SUFFIXES = (".csv", ".tsv", ".txt")
EXCEL_SUFFIXES = (".xlsx", ".xlsm")
NUMBER_COLUMN = "Nummer"
# bei Gleichstand gewinnt das frühere: Tab steht kaum je im Text, deutsches Excel nimmt „;“
_SEPARATORS = ("\t", ";", ",", "|")
_SNIFF_LINES = 20
_BREAKS = re.compile("[" + re.escape(LINE_BREAKS) + "\t]+")   # werden Leerzeichen
_PLACEHOLDER = re.compile(r"\{([^{}\n]+)\}")


class SeriesError(ValueError):
    """Tabelle oder Serie unbrauchbar (Meldung auf Deutsch, mit Dateiname)."""


@dataclass
class Table:
    """Spaltennamen und Zeilen (Texte, jede Zeile so lang wie ``columns``)."""
    columns: list[str]
    rows: list[list[str]]


# --- Tabellen lesen ----------------------------------------------------------------------------
def load_table(path: str | Path, sheet: str | None = None) -> Table:
    """CSV oder Excel; erste Zeile = Spaltennamen; leere Zeilen entfallen (auch mittendrin).
    ``sheet``: Excel-Blatt (None = erstes sichtbares Arbeitsblatt)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in EXCEL_SUFFIXES:
        return _read_excel(path, sheet)
    if suffix in CSV_SUFFIXES:
        return _read_csv(path)
    raise SeriesError(f"{path.name or path}: kein Tabellenformat – CSV oder Excel (.xlsx)")


def sheet_names(path: str | Path) -> list[str]:
    """Arbeitsblätter einer Excel-Datei (ohne Diagrammblätter); CSV: keine."""
    path = Path(path)
    if path.suffix.lower() not in EXCEL_SUFFIXES:
        return []
    book = _open_excel(path)
    try:
        return [ws.title for ws in book.worksheets]
    finally:
        book.close()


def _read_bytes(path: Path) -> bytes:
    """Datei ganz lesen – nur eine reguläre (ein FIFO würde hängen), höchstens ``MAX_BYTES``."""
    try:
        info = os.stat(path)
        if not stat.S_ISREG(info.st_mode):
            raise SeriesError(f"{path.name}: keine Datei")
        if info.st_size > MAX_BYTES:
            raise SeriesError(f"{path.name}: Datei zu groß (höchstens {MAX_BYTES // 2**20} MB)")
        return path.read_bytes()
    except SeriesError:
        raise
    except FileNotFoundError as e:
        raise SeriesError(f"Tabelle nicht gefunden: {path}") from e
    except (OSError, ValueError) as e:         # ValueError: NUL-Zeichen im Pfad
        raise SeriesError(f"{path.name or path} kann nicht gelesen werden") from e


def _decode(data: bytes, path: Path) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):          # „Unicode-Text“ aus Excel
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError as e:
            raise SeriesError(f"{path.name}: Tabelle nicht lesbar (UTF-16 beschädigt)") from e
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")                             # nimmt jedes Byte


def _separator(text: str) -> str:
    """Trennzeichen, mit dem die ersten Zeilen gleich viele Felder (mehr als eines) ergeben."""
    sample = "\n".join(itertools.islice((line for line in text.splitlines() if line.strip()),
                                        _SNIFF_LINES))
    best, best_score = ";", (False, 0)
    for separator in _SEPARATORS:
        try:
            rows = list(csv.reader(io.StringIO(sample), delimiter=separator))
        except csv.Error:
            continue
        if not rows or len(rows[0]) < 2:
            continue
        score = (True, sum(len(row) == len(rows[0]) for row in rows))
        if score > best_score:
            best, best_score = separator, score
    return best


def _read_csv(path: Path) -> Table:
    text = _decode(_read_bytes(path), path)
    if "\x00" in text:                                   # Binärdatei mit falscher Endung
        raise SeriesError(f"{path.name}: Tabelle nicht lesbar (keine Textdatei)")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=_separator(text))
    limit = csv.field_size_limit()
    try:
        csv.field_size_limit(MAX_CELL)
        return _collect(reader, path)
    except csv.Error as e:
        if "field larger" in str(e):
            raise SeriesError(f"{path.name}: Zelle zu lang (höchstens {MAX_CELL:,} Zeichen)"
                              .replace(",", ".")) from e
        raise SeriesError(f"{path.name}: Tabelle nicht lesbar") from e
    finally:
        csv.field_size_limit(limit)


def _open_excel(path: Path):
    """Arbeitsmappe aus den einmal gelesenen Bytes (kein zweites Öffnen des Pfads)."""
    import openpyxl
    if not openpyxl.DEFUSEDXML:                # ohne defusedxml wären XML-Angriffe möglich
        raise SeriesError(f"{path.name}: Excel-Dateien lesen ist ohne Schutz abgeschaltet "
                          "(defusedxml fehlt)")
    data = io.BytesIO(_read_bytes(path))
    try:
        with zipfile.ZipFile(data) as archive:
            if sum(info.file_size for info in archive.infolist()) > MAX_UNPACKED:
                raise SeriesError(f"{path.name}: Datei ausgepackt zu groß")
        return openpyxl.load_workbook(data, read_only=True, data_only=True)
    except SeriesError:
        raise
    except Exception as e:  # openpyxl/zipfile werfen je nach Schaden verschiedene Fehler
        raise SeriesError(f"{path.name}: Excel-Datei nicht lesbar") from e


def _read_excel(path: Path, sheet: str | None) -> Table:
    book = _open_excel(path)
    try:
        sheets = book.worksheets                          # ohne Diagrammblätter
        if sheet is not None:
            chosen = next((ws for ws in sheets if ws.title == sheet), None)
            if chosen is None:
                raise SeriesError(f"{path.name}: Blatt „{sheet}“ fehlt")
        else:
            chosen = next((ws for ws in sheets if ws.sheet_state == "visible"),
                          sheets[0] if sheets else None)
        if chosen is None:
            raise SeriesError(f"{path.name}: Tabelle ist leer")
        rows = ([_cell(cell.value, getattr(cell, "number_format", "General")) for cell in row]
                for row in chosen.iter_rows(max_col=MAX_COLUMNS + 1))
        return _collect(rows, path)
    except SeriesError:
        raise
    except Exception as e:
        raise SeriesError(f"{path.name}: Excel-Datei nicht lesbar") from e
    finally:
        book.close()


def _cell(value, number_format: str = "General") -> str:
    """Zellwert wie das deutsche Excel ihn zeigt: führende Nullen („000“), Prozent, feste
    Nachkommastellen, Komma; Datum TT.MM.JJJJ (mit Uhrzeit nur, wenn nicht 0:00)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "WAHR" if value else "FALSCH"
    if isinstance(value, (int, float)):
        return _number(value, number_format or "General")
    if isinstance(value, datetime.datetime):
        return value.strftime("%d.%m.%Y" if value.time() == datetime.time() else "%d.%m.%Y %H:%M")
    if isinstance(value, datetime.date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, datetime.time):
        return value.strftime("%H:%M")
    if isinstance(value, datetime.timedelta):
        minutes = round(value.total_seconds() / 60)
        return f"{minutes // 60}:{minutes % 60:02d}"
    return str(value)


def _number(value: int | float, number_format: str) -> str:
    fmt = number_format.split(";")[0]                     # nur der Teil für positive Zahlen
    if "%" in fmt:
        value, suffix = value * 100, "%"
    else:
        suffix = ""
    match = re.search(r"(0+)(?:\.(0+))?", fmt.replace("#", "").replace(",", ""))
    if match and fmt not in ("General", "@"):
        decimals = len(match.group(2) or "")
        text = f"{abs(value):.{decimals}f}".replace(".", ",")
        whole, _, fraction = text.partition(",")
        text = whole.zfill(len(match.group(1))) + ("," + fraction if fraction else "")
        return ("-" if value < 0 and float(text.replace(",", ".")) else "") + text + suffix
    if isinstance(value, int) or (value.is_integer() and abs(value) < 1e21):
        return f"{value:.0f}" + suffix if isinstance(value, float) else str(value) + suffix
    return f"{value:.15g}".replace(".", ",") + suffix


def _collect(rows: Iterable[list], path: Path) -> Table:
    """Zeilen einsammeln: Zellen als Text (Umbrüche → Leerzeichen), leere Zellen am Zeilenende
    und leere Zeilen weg, Spaltennamen eindeutig, Grenzen sofort prüfen."""
    header: list[str] | None = None
    data: list[list[str]] = []
    for row in rows:
        cells = [_BREAKS.sub(" ", str(cell)) for cell in row]
        while cells and not cells[-1].strip():
            cells.pop()
        if not cells:
            continue
        if header is None:
            if len(cells) > MAX_COLUMNS:
                raise SeriesError(f"{path.name}: zu viele Spalten (höchstens {MAX_COLUMNS})")
            header = cells
            continue
        if len(data) == MAX_ROWS:
            raise SeriesError(f"{path.name}: zu viele Zeilen (höchstens {MAX_ROWS:,})"
                              .replace(",", "."))
        data.append(cells)
    if header is None:
        raise SeriesError(f"{path.name}: Tabelle ist leer")
    columns: list[str] = []
    for number, name in enumerate(header, start=1):
        name = name.strip() or f"Spalte {number}"
        unique, n = name, 2
        while unique in columns:
            unique, n = f"{name} ({n})", n + 1
        columns.append(unique)
    width = len(columns)
    return Table(columns, [(row + [""] * width)[:width] for row in data])


# --- Nummerierung und Serie --------------------------------------------------------------------
def _whole(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def check_numbering(numbering: Numbering) -> None:
    """Grenzen der Nummerierung – auch die letzte Zahl bleibt bei höchstens ``MAX_NUMBER``."""
    limit = f"{MAX_NUMBER:,}".replace(",", ".")
    for value, name in ((numbering.start, "Start"), (numbering.step, "Schritt")):
        if not _whole(value) or abs(value) > MAX_NUMBER:
            raise SeriesError(f"{name} der Nummerierung: ganze Zahl bis {limit}")
    if numbering.step == 0:
        raise SeriesError("Schritt der Nummerierung darf nicht 0 sein")
    if not _whole(numbering.count) or not 1 <= numbering.count <= MAX_SERIES_ROWS:
        raise SeriesError(f"Anzahl der Nummerierung: 1 bis {MAX_SERIES_ROWS:,}".replace(",", "."))
    if not _whole(numbering.digits) or not 0 <= numbering.digits <= MAX_DIGITS:
        raise SeriesError(f"Stellen der Nummerierung: 0 bis {MAX_DIGITS}")
    if abs(numbering.start + (numbering.count - 1) * numbering.step) > MAX_NUMBER:
        raise SeriesError(f"Zahlen der Nummerierung zu groß (höchstens {limit})")


def numbering_table(numbering: Numbering) -> Table:
    """Spalte „Nummer“: ``start``, ``start + step`` … – mit Nullen auf ``digits`` Stellen."""
    check_numbering(numbering)

    def text(n: int) -> str:
        digits = str(abs(n)).zfill(numbering.digits)
        return f"-{digits}" if n < 0 else digits
    return Table([NUMBER_COLUMN], [[text(numbering.start + i * numbering.step)]
                                   for i in range(numbering.count)])


def check(value: Series) -> None:
    """Serie prüfen: genau eins von Tabelle und Nummerierung, bekannter Schnitt."""
    if (value.source is None) == (value.numbering is None):
        raise SeriesError("Serie braucht genau eins: Tabelle oder Nummerierung")
    if value.source is not None and (not isinstance(value.source, str) or not value.source
                                     or "\x00" in value.source):
        raise SeriesError(f"Tabelle der Serie ungültig: {value.source!r}")
    if value.sheet is not None and not isinstance(value.sheet, str):
        raise SeriesError(f"Blatt der Serie ungültig: {value.sheet!r}")
    if value.cut not in CUTS:
        raise SeriesError(f"Unbekannter Schnitt {value.cut!r} – erlaubt: {', '.join(CUTS)}")
    if value.numbering is not None:
        check_numbering(value.numbering)


def table_for(value: Series, base: str | Path | None = None) -> Table:
    """Zeilen der Serie: Tabelle (relativer Pfad zu ``base``) bzw. Nummerierung."""
    check(value)
    if value.numbering is not None:
        return numbering_table(value.numbering)
    path = Path(value.source)
    if not path.is_absolute() and base is not None:
        path = Path(base) / path
    return load_table(path, value.sheet)


# --- Platzhalter -------------------------------------------------------------------------------
def placeholders(doc: Document) -> list[str]:
    """Namen der Platzhalter ``{Name}`` in den Textobjekten (Reihenfolge, jeder einmal)."""
    names: list[str] = []
    for obj in doc.objects:
        if isinstance(obj, TextObject):
            for name in _PLACEHOLDER.findall(obj.text):
                name = name.strip()              # { Klemme } passt zur Spalte „Klemme“
                if name not in names:
                    names.append(name)
    return names


def missing(doc: Document, columns: list[str]) -> list[str]:
    """Platzhalter ohne passende Spalte."""
    return [name for name in placeholders(doc) if name not in columns]


def fill(doc: Document, columns: list[str], row: list[str], keep: int | None = None) -> Document:
    """``doc`` mit den Werten der Zeile statt der Platzhalter – **nur zum Lesen** (Rendern,
    Drucken): Objekte ohne Platzhalter, Bilder und ``keep`` sind dieselben wie im Original
    (Renderer-Cache trifft), nur gefüllte Textobjekte sind neu; ``doc`` bleibt unverändert.

    Der Wert übernimmt die Formatierung des Stücks, in dem sein Platzhalter beginnt (auch über
    Stückgrenzen hinweg); unbekannte Platzhalter bleiben stehen; Zeilenumbrüche und Tabs im
    Wert werden Leerzeichen. ``keep``: Objekt, das unverändert bleibt (wird gerade bearbeitet).
    """
    values = {name: _BREAKS.sub(" ", value) for name, value in zip(columns, row)}
    out = copy.copy(doc)
    out.objects = [obj if i == keep or not isinstance(obj, TextObject) else _fill_text(obj, values)
                   for i, obj in enumerate(doc.objects)]
    return out


def _fill_text(obj: TextObject, values: dict[str, str]) -> TextObject:
    paragraphs = [_fill_paragraph(p, values) for p in obj.paragraphs]
    if all(new is old for new, old in zip(paragraphs, obj.paragraphs)):
        return obj
    filled = copy.copy(obj)
    filled.paragraphs = paragraphs
    return filled


def _fill_paragraph(para: Paragraph, values: dict[str, str]) -> Paragraph:
    # Zeichen mit dem Index ihres Stücks; Ersetzen von hinten, damit Positionen gelten
    chars = [(c, i) for i, span in enumerate(para.spans) for c in span.text]
    text = "".join(c for c, _ in chars)
    matches = [m for m in _PLACEHOLDER.finditer(text) if m.group(1).strip() in values]
    if not matches:
        return para
    for m in reversed(matches):
        style = chars[m.start()][1]
        chars[m.start():m.end()] = [(c, style) for c in values[m.group(1).strip()]]
    spans: list[Span] = []
    styles: list[int] = []                          # Stück, dessen Formatierung jedes neue trägt
    for c, i in chars:
        if styles and styles[-1] == i:
            spans[-1].text += c
        else:
            spans.append(replace(para.spans[i], text=c))
            styles.append(i)
    if not spans:                                   # nur leere Werte: eine leere Zeile, formatiert
        spans = [replace(para.spans[_span_at(para, matches[0].start())], text="")]
    return Paragraph(spans, para.align)


def _span_at(para: Paragraph, pos: int) -> int:
    """Index des Stücks, in dem die Position ``pos`` des Absatztexts liegt."""
    for i, span in enumerate(para.spans):
        if pos < len(span.text):
            return i
        pos -= len(span.text)
    return len(para.spans) - 1
