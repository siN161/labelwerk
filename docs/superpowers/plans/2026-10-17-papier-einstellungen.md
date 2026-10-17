# Papier komplett + Einstellungen (Etappe 1) – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Papier-Panel wie im P-touch Editor (Ausrichtung Horizontal/Vertikal, Ränder, Medium prüfen), Einstellungen für GUI und CLI, Live-Druckererkennung.

**Architecture:** Kern (Qt-frei): `render_document` rendert in Leserichtung und dreht bei „horizontal“ ins Druckbild; neues `settings.py` (JSON in `$XDG_CONFIG_HOME/labelwerk/settings.json`); neues `media.py` (Statusabfrage `ESC i S` mit eigener nicht blockierender Leseroutine). CLI nutzt Einstellungen als Standard. GUI: Papier-Panel erweitert, Arbeitsfläche dreht die Ansicht bei „horizontal“, `MediaWorker` im Hintergrund, 2-s-Abfrage des Druckers, Einstellungsdialog.

**Tech Stack:** Python ≥ 3.10, Pillow, brother_ql-inventree, PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-17-papier-einstellungen-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge, nach jedem Task volle Suite grün (124 → 133 → 140 → 151 → 159 → 166 → 174 → 179), je mehrfach ohne Wackler. `media.read_media` und `labelwerk media` am echten QL-600 geprüft (reine Statusabfrage, Antwort „62 mm endlos“). Code wörtlich übernehmen.

## Global Constraints

- Kern bleibt **Qt-frei** (`document.py`, `render.py`, `settings.py`, `media.py`, `labels.py`, `detect.py`); keine Drucklogik in der GUI.
- **Vorschau = Druck:** `render_document` liefert immer das fertige Druckbild (Breite = bedruckbare Bandbreite); horizontal wird um 90° **im Uhrzeigersinn** gedreht (`rotate(-90, expand=True)`), damit der Textanfang zuerst gedruckt wird und das veränderliche Ende in Leserichtung rechts liegt.
- Begriffe wie P-touch: **Vertikal** = Text quer zum Band (bisheriges Verhalten, Standard), **Horizontal** = Text längs zum Band.
- Automatische Schriftgröße in beiden Ausrichtungen: höchstens 1/5 der Bandbreite.
- Ränder 0–20 mm, wirken in Bandlaufrichtung; quer zum Band fest 1 mm (`MARGIN`).
- Einstellungen: fehlende/ungültige Werte → Standardwert + Hinweis in `Settings.warnings`, nie Ausnahme beim Laden.
- **Medium prüfen druckt nie**: nur Invalidate + `ESC @` + `ESC i S`, nicht blockierend, Zeitlimit 2 s; nie gleichzeitig mit einem Druck.
- Benutzer-Meldungen und Kommentare **auf Deutsch**; keine Tracebacks für Nutzer.
- **Tests ohne Hardware und ohne echte Nutzer-Einstellungen:** `tests/conftest.py` lenkt `XDG_CONFIG_HOME` in einen Temp-Ordner; GUI-Tests patchen Druckererkennung, `print_image` und `read_media`.
- Tests: `.venv/bin/python -m pytest -q` im Repo-Wurzelverzeichnis (GUI-Tests offscreen).
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Code geschrieben hat).

## Dateien

| Datei | Task |
|---|---|
| `src/labelwerk/document.py`, `render.py` | 1 |
| `src/labelwerk/settings.py` (neu) | 2 |
| `src/labelwerk/media.py` (neu) | 3 |
| `src/labelwerk/cli.py`, `tests/conftest.py` (neu) | 4 |
| `src/labelwerk/gui/panels/paper.py`, `canvas.py`, `main_window.py` | 5 |
| `src/labelwerk/gui/media_worker.py` (neu), `panels/paper.py`, `main_window.py`, `theme/rawblock.qss` | 6 |
| `src/labelwerk/gui/settings_dialog.py` (neu), `app.py`, `main_window.py`, `theme/rawblock.qss` | 7 |
| `README.md`, `CLAUDE.md` | 8 |

---
### Task 1: Kern – Ausrichtung und Ränder beim Rendern

**Files:** Modify `src/labelwerk/document.py`, `src/labelwerk/render.py` (komplett), `tests/test_document.py` (anhängen)

**Interfaces:**
- Produces: `document.ORIENTATIONS = ("vertical", "horizontal")`, `document.MAX_MARGIN_MM = 20.0`; `Document.orientation: str = "vertical"`, `Document.margin_mm: float = 1.0`. `render_document(doc, model)` unterstützt beide Ausrichtungen, wirft `ValueError` („Ausrichtung“) bei unbekannter, Ränder auf 0–20 mm begrenzt. Schriftgrößensuche per Halbierung (`_fit_font`), Textmaße ganzzahlig (`_text_box` rundet).

- [ ] **Step 1: Failing tests**

An `tests/test_document.py` **anhängen**:

```python
def _ink(img):
    return img.convert("L").point(lambda v: 255 if v < 128 else 0)


def test_horizontal_endless_prints_across_full_width_and_grows_with_text():
    short = render_document(Document("62", orientation="horizontal", objects=[TextObject("Hi")]))
    long = render_document(Document("62", orientation="horizontal",
                                    objects=[TextObject("Max Mustermann")]))
    assert short.width == long.width == 696
    assert long.height > short.height


def test_horizontal_text_reads_along_the_tape():
    img = render_document(Document("62", orientation="horizontal",
                                   objects=[TextObject("Hallo\n.", font_size=150)]))
    reading = img.rotate(90, expand=True)              # zurück in Leserichtung
    ink = _ink(reading)
    top = ink.crop((0, 0, reading.width, reading.height // 2)).histogram()[255]
    bottom = ink.crop((0, reading.height // 2, reading.width, reading.height)).histogram()[255]
    assert top > 3 * bottom                             # „Hallo“ oben, kleiner Punkt unten


def test_horizontal_auto_font_matches_vertical():
    def ink_height(orientation):
        img = render_document(Document("62", orientation=orientation, objects=[TextObject("Hallo")]))
        reading = img.rotate(90, expand=True) if orientation == "horizontal" else img
        box = _ink(reading).getbbox()
        return box[3] - box[1]
    assert ink_height("horizontal") == ink_height("vertical")   # gleiche Obergrenze


def test_horizontal_fixed_length():
    doc = Document("62", length_mm=50, orientation="horizontal", objects=[TextObject("Hallo")])
    assert render_document(doc).size == (696, 591)


def test_horizontal_die_cut_keeps_print_size():
    doc = Document("62x29", orientation="horizontal", objects=[TextObject("Hallo")])
    assert render_document(doc).size == (696, 271)


def test_margin_extends_auto_length():
    def height(margin):
        doc = Document("62", margin_mm=margin, objects=[TextObject("A", font_size=200)])
        return render_document(doc).height
    assert height(5) - height(1) == 2 * (59 - 12)        # 5 mm = 59 Punkte, 1 mm = 12


def test_margin_is_clamped_to_20_mm():
    def height(margin):
        doc = Document("62", margin_mm=margin, objects=[TextObject("A", font_size=200)])
        return render_document(doc).height
    assert height(50) == height(20)
    assert height(-3) == height(0)


def test_unknown_orientation_raises():
    import pytest
    with pytest.raises(ValueError, match="Ausrichtung"):
        render_document(Document("62", orientation="schräg", objects=[TextObject("A")]))


def test_horizontal_render_is_fast_enough_for_live_preview():
    import time
    doc = Document("62", orientation="horizontal",
                   objects=[TextObject("Max Mustermann\nMusterstr. 5\n12345 Musterstadt")])
    start = time.perf_counter()
    render_document(doc)
    assert time.perf_counter() - start < 0.5
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: Fehler bei den neuen Tests (`TypeError: Document.__init__() got an unexpected keyword argument 'orientation'` bzw. `'margin_mm'`), bisherige Tests grün.

- [ ] **Step 3: Implementierung**

`src/labelwerk/document.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Etikett-Dokument: Etikett und Liste von Objekten (UI-unabhängig)."""
from __future__ import annotations

from dataclasses import dataclass, field

ORIENTATIONS = ("vertical", "horizontal")
MAX_MARGIN_MM = 20.0


@dataclass
class TextObject:
    text: str = ""
    font_size: int | None = None      # None = automatisch
    font_path: str | None = None

    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass
class Document:
    label_id: str = "62"
    length_mm: float | None = None    # nur Endlosband; None = automatisch
    orientation: str = "vertical"     # "vertical" (Text quer zum Band) | "horizontal" (längs)
    margin_mm: float = 1.0            # Rand in Bandlaufrichtung (vorne/hinten)
    objects: list[TextObject] = field(default_factory=list)

    def is_empty(self) -> bool:
        """True, wenn kein Objekt sichtbaren Inhalt hat."""
        return all(obj.is_empty() for obj in self.objects)
```

`src/labelwerk/render.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Rendert Etiketteninhalte als Bild in exakter Druckauflösung."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .document import MAX_MARGIN_MM, ORIENTATIONS, Document, TextObject
from .labels import DPI, get_label, length_limits

MARGIN = 12  # Punkte, ca. 1 mm
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",            # Arch
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",  # Fedora
]


class TextTooLarge(ValueError):
    """Text passt bei fester Schriftgröße nicht aufs Etikett."""

    def __init__(self, size: int, max_size: int, label_id: str):
        super().__init__(f"Text passt nicht auf Etikett {label_id!r} bei Schriftgröße {size} "
                         f"(höchstens {max_size}).")
        self.size, self.max_size = size, max_size


def _load_font(size: int, font_path: str | None):
    for path in [font_path, *_FONT_CANDIDATES]:
        if path and Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _text_box(text: str, font) -> tuple[int, int, int, int]:
    probe = ImageDraw.Draw(Image.new("1", (1, 1)))
    box = probe.multiline_textbbox((0, 0), text, font=font, align="center")
    return tuple(round(v) for v in box)        # Pillow liefert teils Kommazahlen


def render_text(
    text: str,
    label_id: str,
    font_size: int | None = None,
    font_path: str | None = None,
) -> Image.Image:
    obj = TextObject(text, font_size=font_size, font_path=font_path)
    return render_document(Document(label_id, objects=[obj]))


def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
    """Dokument als Druckbild in exakter Auflösung (Vorschau = Druck).

    Gerendert wird in Leserichtung; bei Ausrichtung „horizontal“ (Text längs zum Band)
    wird das Bild danach für den Drucker um 90° im Uhrzeigersinn gedreht – so kommt der
    Textanfang zuerst aus dem Drucker und das veränderliche Ende liegt in Leserichtung rechts.
    """
    if doc.orientation not in ORIENTATIONS:
        raise ValueError(f"Unbekannte Ausrichtung {doc.orientation!r} – erlaubt: horizontal, vertical")
    horizontal = doc.orientation == "horizontal"
    label = get_label(doc.label_id)
    min_len, max_len = length_limits(model)
    margin = round(min(max(doc.margin_mm, 0.0), MAX_MARGIN_MM) * DPI / 25.4)
    across = label.width                      # quer zum Band (fest)
    feed = label.height                       # in Bandlaufrichtung; None = automatisch
    if feed is None and doc.length_mm is not None:
        feed = min(max(round(doc.length_mm * DPI / 25.4), min_len), max_len)
    obj = doc.objects[0] if doc.objects else TextObject()

    across_room = across - 2 * MARGIN
    feed_room = (feed if feed else max_len) - 2 * margin
    max_w, max_h = (feed_room, across_room) if horizontal else (across_room, feed_room)
    start = obj.font_size or max(10, across // 5)   # automatisch: höchstens 1/5 der Bandbreite
    font, (l, t, r, b) = _fit_font(obj, start, max_w, max_h, doc.label_id)

    text_w, text_h = r - l, b - t
    if feed is None:
        feed = min(max((text_w if horizontal else text_h) + 2 * margin, min_len), max_len)
    width, height = (feed, across) if horizontal else (across, feed)
    img = Image.new("RGB", (width, height), "white")
    x = (width - text_w) // 2 - l
    y = (height - text_h) // 2 - t
    ImageDraw.Draw(img).multiline_text((x, y), obj.text, fill="black", font=font, align="center")
    return img.rotate(-90, expand=True) if horizontal else img


def _fit_font(obj: TextObject, start: int, max_w: int, max_h: int, label_id: str):
    """Größte Schrift ≤ start, mit der der Text in max_w × max_h passt (Halbierungssuche)."""
    def attempt(size):
        font = _load_font(size, obj.font_path)
        box = _text_box(obj.text, font)
        return (box[2] - box[0]) <= max_w and (box[3] - box[1]) <= max_h, font, box

    ok, font, box = attempt(start)
    if ok:
        return font, box
    best, lo, hi = None, 8, start - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        ok, f, bx = attempt(mid)
        if ok:
            best, lo = (mid, f, bx), mid + 1
        else:
            hi = mid - 1
    if obj.font_size is not None:
        raise TextTooLarge(obj.font_size, best[0] if best else 8, label_id)
    if best is None:                          # passt nicht einmal in 8 – kleinste Größe zeigen
        _, f, bx = attempt(8)
        return f, bx
    return best[1], best[2]
```

- [ ] **Step 4: Grün prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: `133 passed`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/document.py src/labelwerk/render.py tests/test_document.py
git commit -m "Rendern: Ausrichtung horizontal/vertikal und Ränder

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 2: Kern – Einstellungen (`settings.py`)

**Files:** Create `src/labelwerk/settings.py`, `tests/test_settings.py`

**Interfaces:**
- Consumes: `document.ORIENTATIONS`, `MAX_MARGIN_MM`, `Document`, `TextObject`; `labels.get_label`.
- Produces: `Settings(label_id="62", orientation="vertical", margin_mm=1.0, font_size=None, check_media_on_start=True, start_zoom=200, warnings=[])` (dataclass, `warnings` nicht im Vergleich); `settings_path() -> Path`; `load_settings(path=None) -> Settings`; `save_settings(settings, path=None) -> Path` (wirft `OSError` „… nicht gespeichert …“); `new_document(settings) -> Document`.

- [ ] **Step 1: Failing tests**

`tests/test_settings.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
import json

import pytest

from labelwerk.settings import Settings, load_settings, new_document, save_settings, settings_path


def test_defaults_match_todays_behavior(tmp_path):
    s = load_settings(tmp_path / "fehlt.json")
    assert (s.label_id, s.orientation, s.margin_mm, s.font_size) == ("62", "vertical", 1.0, None)
    assert s.check_media_on_start is True and s.start_zoom == 200
    assert s.warnings == []


def test_path_follows_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert settings_path() == tmp_path / "labelwerk" / "settings.json"


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "cfg" / "settings.json"
    save_settings(Settings(label_id="62x29", orientation="horizontal", margin_mm=3,
                           font_size=80, check_media_on_start=False, start_zoom=150), path)
    s = load_settings(path)
    assert (s.label_id, s.orientation, s.margin_mm, s.font_size) == ("62x29", "horizontal", 3.0, 80)
    assert (s.check_media_on_start, s.start_zoom) == (False, 150)
    assert "warnings" not in json.loads(path.read_text())


def test_invalid_values_fall_back_with_warning(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"label_id": "999", "orientation": "schräg", "margin_mm": 99,
                                "font_size": "groß", "start_zoom": True, "unbekannt": 1,
                                "check_media_on_start": False}))
    s = load_settings(path)
    assert (s.label_id, s.orientation, s.margin_mm, s.font_size, s.start_zoom) == \
        ("62", "vertical", 1.0, None, 200)
    assert s.check_media_on_start is False                 # gültige Werte bleiben
    assert len(s.warnings) == 5
    assert all("ungültig" in w for w in s.warnings)


def test_broken_json_gives_defaults_and_warning(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{kaputt")
    s = load_settings(path)
    assert s.label_id == "62"
    assert len(s.warnings) == 1 and "nicht lesbar" in s.warnings[0]


def test_save_error_has_clear_message(tmp_path):
    blocker = tmp_path / "datei"
    blocker.write_text("x")                                # Ordner kann nicht angelegt werden
    with pytest.raises(OSError, match="nicht gespeichert"):
        save_settings(Settings(), blocker / "settings.json")


def test_new_document_uses_settings():
    doc = new_document(Settings(label_id="62x29", orientation="horizontal", margin_mm=3, font_size=80))
    assert (doc.label_id, doc.orientation, doc.margin_mm) == ("62x29", "horizontal", 3)
    assert doc.objects[0].font_size == 80 and doc.objects[0].text == ""
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: `ModuleNotFoundError: No module named 'labelwerk.settings'`

- [ ] **Step 3: Implementierung**

`src/labelwerk/settings.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Einstellungen für GUI und CLI in $XDG_CONFIG_HOME/labelwerk/settings.json.

Fehlende oder ungültige Werte fallen auf den Standard zurück – mit Hinweis in
`Settings.warnings`, nie mit Ausnahme. Neue Einstellung = neues Feld + Prüfregel.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .document import MAX_MARGIN_MM, ORIENTATIONS, Document, TextObject
from .labels import get_label


@dataclass
class Settings:
    label_id: str = "62"
    orientation: str = "vertical"
    margin_mm: float = 1.0
    font_size: int | None = None           # None = automatisch
    check_media_on_start: bool = True
    start_zoom: int = 200
    warnings: list[str] = field(default_factory=list, compare=False, repr=False)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _known_label(v) -> bool:
    try:
        get_label(v)
    except ValueError:
        return False
    return True


_RULES = {
    "label_id": lambda v: isinstance(v, str) and _known_label(v),
    "orientation": lambda v: v in ORIENTATIONS,
    "margin_mm": lambda v: (_is_int(v) or isinstance(v, float)) and 0 <= v <= MAX_MARGIN_MM,
    "font_size": lambda v: v is None or (_is_int(v) and 8 <= v <= 400),
    "check_media_on_start": lambda v: isinstance(v, bool),
    "start_zoom": lambda v: _is_int(v) and 25 <= v <= 400,
}


def settings_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "labelwerk" / "settings.json"


def load_settings(path: str | Path | None = None) -> Settings:
    path = Path(path) if path else settings_path()
    settings = Settings()
    if not path.exists():
        return settings
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("kein JSON-Objekt")
    except (OSError, ValueError) as e:
        settings.warnings.append(f"Einstellungen nicht lesbar ({path}): {e} – Standardwerte aktiv.")
        return settings
    for key, valid in _RULES.items():
        if key not in raw:
            continue
        value = raw[key]
        if valid(value):
            setattr(settings, key, float(value) if key == "margin_mm" else value)
        else:
            settings.warnings.append(f"Einstellung {key!r} ungültig ({value!r}) – "
                                     f"Standardwert {getattr(settings, key)!r} aktiv.")
    return settings


def save_settings(settings: Settings, path: str | Path | None = None) -> Path:
    path = Path(path) if path else settings_path()
    data = {key: getattr(settings, key) for key in _RULES}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as e:
        raise OSError(f"Einstellungen konnten nicht gespeichert werden ({path}): "
                      f"{e.strerror or e}") from e
    return path


def new_document(settings: Settings) -> Document:
    """Neues Etikett mit den Standardwerten aus den Einstellungen."""
    return Document(label_id=settings.label_id, orientation=settings.orientation,
                    margin_mm=settings.margin_mm, objects=[TextObject(font_size=settings.font_size)])
```

- [ ] **Step 4: Grün prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: `140 passed`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/settings.py tests/test_settings.py
git commit -m "Einstellungen: settings.json mit Standardwerten und Prüfung

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 3: Kern – Medium prüfen (`media.py`)

**Files:** Create `src/labelwerk/media.py`, `tests/test_media.py`

**Interfaces:**
- Consumes: `labels.labels_for_model` (mit `Label.shape`, `Label.size_mm`), `brother_ql.reader.interpret_response`.
- Produces: `Media(width_mm, length_mm, kind)` (frozen, `describe()`), `MediaError(ValueError)`, `STATUS_REQUEST`, `read_media(printer, timeout=2.0) -> Media`, `parse_media(bytes) -> Media`, `label_for_media(media, model="QL-600") -> str | None`, `query_status(printer, timeout=2.0, opener=...) -> bytes`.
- Wichtig: **nie** brother_ql-Backends zum Lesen verwenden (deren letzter Leseversuch kann ohne Zeitlimit blockieren); die eigene Routine mit `O_NONBLOCK` + `select` ist Absicht.

- [ ] **Step 1: Failing tests**

`tests/test_media.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
import os
import socket
import threading

import pytest

from labelwerk.media import (STATUS_REQUEST, Media, MediaError, label_for_media, parse_media,
                             query_status)


def status(width=62, media_code=0x0A, length=0, error2=0):
    """32-Byte-Statusantwort eines QL-600 (wie am echten Gerät gemessen)."""
    data = bytearray(32)
    data[0:3] = b"\x80\x20\x42"
    data[3], data[4] = 0x34, 0x47          # Serie/Modell QL-600
    data[9] = error2
    data[10], data[11], data[17] = width, media_code, length
    return bytes(data)


def test_parse_endless():
    assert parse_media(status()) == Media(62, 0, "endless")


def test_parse_die_cut():
    assert parse_media(status(width=62, media_code=0x0B, length=29)) == Media(62, 29, "die_cut")


def test_parse_no_media():
    assert parse_media(status(width=0, media_code=0x00)).kind == "none"


def test_parse_printer_error():
    with pytest.raises(MediaError, match="Replace media error"):
        parse_media(status(error2=0x01))


def test_parse_garbage():
    with pytest.raises(MediaError, match="Unverständliche Antwort"):
        parse_media(b"\x00" * 5)


def test_describe():
    assert Media(62, 0, "endless").describe() == "62 mm endlos"
    assert Media(62, 29, "die_cut").describe() == "62 × 29 mm gestanzt"
    assert Media(0, 0, "none").describe() == "keine Rolle eingelegt"


def test_label_for_media():
    assert label_for_media(Media(62, 0, "endless")) == "62"
    assert label_for_media(Media(62, 29, "die_cut")) == "62x29"
    assert label_for_media(Media(24, 24, "die_cut")) == "d24"
    assert label_for_media(Media(0, 0, "none")) is None
    assert label_for_media(Media(61, 0, "endless")) is None


def _fake_printer(reply):
    """Socket-Paar: unser Ende für query_status, am anderen Ende antwortet ein Fake-Drucker."""
    ours, theirs = socket.socketpair()
    received = []

    def serve():
        data = b""
        while len(data) < len(STATUS_REQUEST):
            data += theirs.recv(4096)
        received.append(data)
        if reply:
            theirs.sendall(reply)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    fd = os.dup(ours.fileno())
    os.set_blocking(fd, False)
    ours.close()
    return (lambda path: fd), received, thread, theirs


def test_query_status_sends_request_and_reads_reply():
    opener, received, thread, other = _fake_printer(status())
    data = query_status("file:///dev/usb/lp9", timeout=2, opener=opener)
    thread.join(1)
    other.close()
    assert received == [STATUS_REQUEST]
    assert parse_media(data) == Media(62, 0, "endless")


def test_query_status_times_out():
    opener, _, thread, other = _fake_printer(reply=None)
    with pytest.raises(MediaError, match="Keine Antwort"):
        query_status("file:///dev/usb/lp9", timeout=0.2, opener=opener)
    other.close()


def test_query_status_only_for_kernel_device():
    with pytest.raises(MediaError, match="nur über /dev/usb/lpN"):
        query_status("usb://0x04f9:0x20c0")


def test_query_status_missing_device(tmp_path):
    with pytest.raises(MediaError, match="nicht gefunden"):
        query_status(f"file://{tmp_path}/lp9")
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: `ModuleNotFoundError: No module named 'labelwerk.media'`

- [ ] **Step 3: Implementierung**

`src/labelwerk/media.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Eingelegte Rolle vom Drucker abfragen („Medium prüfen“) – reine Statusabfrage, druckt nichts."""
from __future__ import annotations

import os
import select
import time
from dataclasses import dataclass

from brother_ql.reader import interpret_response

from .labels import labels_for_model

# Puffer leeren (Invalidate), initialisieren (ESC @), Status anfragen (ESC i S)
STATUS_REQUEST = b"\x00" * 200 + b"\x1b\x40" + b"\x1b\x69\x53"
TIMEOUT_S = 2.0
_KINDS = {"Continuous length tape": "endless", "Die-cut labels": "die_cut", "No media": "none"}


class MediaError(ValueError):
    """Rolle konnte nicht ermittelt werden; die Meldung ist für Nutzer gedacht."""


@dataclass(frozen=True)
class Media:
    width_mm: int
    length_mm: int
    kind: str                # "endless", "die_cut" oder "none"

    def describe(self) -> str:
        if self.kind == "none":
            return "keine Rolle eingelegt"
        if self.kind == "endless":
            return f"{self.width_mm} mm endlos"
        return f"{self.width_mm} × {self.length_mm} mm gestanzt"


def read_media(printer: str, timeout: float = TIMEOUT_S) -> Media:
    """Rolle im Drucker (``file:///dev/usb/lpN``) abfragen."""
    return parse_media(query_status(printer, timeout))


def parse_media(data: bytes) -> Media:
    try:
        status = interpret_response(data)
    except Exception as e:  # brother_ql wirft je nach Fehler NameError, UnboundLocalError …
        raise MediaError(f"Unverständliche Antwort vom Drucker: {e}") from None
    kind = _KINDS.get(status["media_type"])
    if kind is None:
        raise MediaError(f"Unbekannte Rolle: {status['media_type']}")
    if kind == "none" or status["media_width"] == 0:
        return Media(0, 0, "none")
    if status["errors"]:
        raise MediaError("Drucker meldet: " + ", ".join(status["errors"]))
    return Media(status["media_width"], status["media_length"], kind)


def label_for_media(media: Media, model: str = "QL-600") -> str | None:
    """Passende Etikett-ID zur eingelegten Rolle, sonst None."""
    for label in labels_for_model(model):
        if media.kind == "endless" and label.shape == "endless" \
                and label.size_mm[0] == media.width_mm:
            return label.id
        if media.kind == "die_cut" and label.shape in ("die_cut", "round") \
                and label.size_mm == (media.width_mm, media.length_mm):
            return label.id
    return None


def _open_device(path: str) -> int:
    return os.open(path, os.O_RDWR | os.O_NONBLOCK)


def query_status(printer: str, timeout: float = TIMEOUT_S, opener=_open_device) -> bytes:
    """Statusabfrage senden und die 32-Byte-Antwort lesen – mit festem Zeitlimit, nie blockierend."""
    if not printer.startswith("file://"):
        raise MediaError("Medium prüfen geht nur über /dev/usb/lpN (Backend linux_kernel).")
    try:
        fd = opener(printer[len("file://"):])
    except FileNotFoundError:
        raise MediaError(f"Drucker nicht gefunden: {printer}") from None
    except PermissionError:
        raise MediaError(f"Keine Berechtigung für {printer} – Benutzer in Gruppe 'lp'?") from None
    except OSError as e:
        raise MediaError(f"Drucker nicht erreichbar: {e}") from None
    try:
        os.write(fd, STATUS_REQUEST)
        data, deadline = b"", time.monotonic() + timeout
        while len(data) < 32:
            left = deadline - time.monotonic()
            if left <= 0:
                raise MediaError("Keine Antwort vom Drucker auf die Statusabfrage.")
            ready, _, _ = select.select([fd], [], [], min(left, 0.1))
            if ready:
                try:
                    data += os.read(fd, 32 - len(data))
                except BlockingIOError:
                    pass
        return data
    except OSError as e:
        raise MediaError(f"Fehler bei der Statusabfrage: {e}") from None
    finally:
        os.close(fd)
```

- [ ] **Step 4: Grün prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: `151 passed`, dreimal hintereinander (Socket-Tests).

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/media.py tests/test_media.py
git commit -m "Medium prüfen: eingelegte Rolle per Statusabfrage lesen (druckt nichts)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 4: CLI – Einstellungen, `--orientation`, `--margin`, `labelwerk media`

**Files:** Modify `src/labelwerk/cli.py` (komplett), Create `tests/conftest.py`, Modify `tests/test_cli.py` (anhängen)

**Interfaces:**
- Consumes: `settings.load_settings`, `media.read_media/label_for_media/MediaError`, `render.render_document`, `document.Document/TextObject/ORIENTATIONS`.
- Produces: `-l` ohne Standardwert (aus Einstellungen), `print --orientation {vertical,horizontal} --margin MM`, `-s` Standard aus Einstellungen, Befehl `media`. Tests patchen `labelwerk.cli.find_brother_lp`, `labelwerk.cli.brother_busy`, `labelwerk.cli.read_media`.

- [ ] **Step 1: Test-Isolation und failing tests**

`tests/conftest.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
import pytest


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path_factory):
    """Kein Test liest oder schreibt die echten Einstellungen des Nutzers."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("config")))
```

An `tests/test_cli.py` **anhängen**:

```python
def _write_settings(**values):
    import json
    import os
    from pathlib import Path
    path = Path(os.environ["XDG_CONFIG_HOME"]) / "labelwerk" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values))


def test_default_label_comes_from_settings(tmp_path, capsys):
    _write_settings(label_id="62x29")
    rc = main(["print", "Hallo", "--preview", str(tmp_path / "v.png")])
    assert rc == 0
    assert "58,9 × 22,9 mm" in capsys.readouterr().out


def _preview(tmp_path, *args):
    out = tmp_path / "v.png"
    assert main(["print", "Hallo Welt", *args, "--preview", str(out)]) == 0
    return Image.open(out).convert("RGB").tobytes()


def _expected(orientation="vertical", margin=1.0):
    from labelwerk.document import Document, TextObject
    from labelwerk.render import render_document
    doc = Document("62", orientation=orientation, margin_mm=margin, objects=[TextObject("Hallo Welt")])
    return render_document(doc).convert("RGB").tobytes()


def test_default_orientation_comes_from_settings(tmp_path):
    _write_settings(orientation="horizontal")
    assert _preview(tmp_path) == _expected("horizontal")


def test_orientation_option_overrides_settings(tmp_path):
    _write_settings(orientation="horizontal")
    assert _preview(tmp_path, "--orientation", "vertical") == _expected("vertical")


def test_margin_option(tmp_path):
    assert _preview(tmp_path, "--margin", "5") == _expected(margin=5.0)


def test_broken_settings_warn_but_work(tmp_path, capsys):
    import os
    from pathlib import Path
    path = Path(os.environ["XDG_CONFIG_HOME"]) / "labelwerk" / "settings.json"
    path.parent.mkdir(parents=True)
    path.write_text("{kaputt")
    assert main(["print", "Hallo", "--preview", str(tmp_path / "v.png")]) == 0
    assert "nicht lesbar" in capsys.readouterr().err


def test_media_command_shows_loaded_roll(monkeypatch, capsys):
    from labelwerk.media import Media
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: "file:///dev/usb/lp0")
    monkeypatch.setattr("labelwerk.cli.read_media", lambda printer: Media(62, 0, "endless"))
    assert main(["media"]) == 0
    assert "Eingelegt: 62 mm endlos (Etikett 62)" in capsys.readouterr().out


def test_media_command_error(monkeypatch, capsys):
    from labelwerk.media import MediaError
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: "file:///dev/usb/lp0")

    def fail(printer):
        raise MediaError("Keine Antwort vom Drucker auf die Statusabfrage.")
    monkeypatch.setattr("labelwerk.cli.read_media", fail)
    assert main(["media"]) == 2
    assert "Keine Antwort" in capsys.readouterr().err


def test_media_command_without_printer(monkeypatch, capsys):
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: None)
    monkeypatch.setattr("labelwerk.cli.brother_busy", lambda: False)
    assert main(["media"]) == 2
    assert "nicht gefunden" in capsys.readouterr().err
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: die 8 neuen CLI-Tests schlagen fehl (u. a. `invalid choice: 'media'`, `unrecognized arguments: --orientation`), alle anderen grün.

- [ ] **Step 3: Implementierung**

`src/labelwerk/cli.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Kommandozeile: labelwerk labels | print "Text" | print-file datei.pdf | media | install-desktop"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from . import desktop
from . import printer as prn
from .detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp, find_brother_usb
from .files import crop, fit_to_label, load_file
from .document import ORIENTATIONS, Document, TextObject
from .labels import format_mm, labels_for_model
from .media import MediaError, label_for_media, read_media
from .render import render_document
from .settings import load_settings


def _add_output_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-l", "--label", help="Etikett, z. B. 62 (Standard aus den Einstellungen)")
    p.add_argument("-p", "--printer", default="auto",
                   help="auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP")
    p.add_argument("-b", "--backend", default=prn.DEFAULT_BACKEND,
                   choices=["linux_kernel", "pyusb", "network"])
    p.add_argument("--no-cut", action="store_true")
    p.add_argument("--preview", metavar="PNG", help="nur Vorschau speichern, nicht drucken")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=desktop.APP_NAME)
    p.add_argument("-m", "--model", default=prn.DEFAULT_MODEL)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("labels", help="Etiketten für das Modell auflisten")

    pr = sub.add_parser("print", help="Text drucken")
    pr.add_argument("text", help="Text, Zeilenumbruch mit \\n")
    pr.add_argument("-s", "--font-size", type=int, help="Standard aus den Einstellungen")
    pr.add_argument("--font", help="Pfad zu einer .ttf-Datei")
    pr.add_argument("--orientation", choices=ORIENTATIONS,
                    help="vertical: Text quer zum Band, horizontal: längs (Standard aus den Einstellungen)")
    pr.add_argument("--margin", type=float, metavar="MM",
                    help="Rand in Bandlaufrichtung in mm (Standard aus den Einstellungen)")
    _add_output_options(pr)

    pf = sub.add_parser("print-file", help="PDF/Bild 1:1 drucken")
    pf.add_argument("file", help="PDF, PNG oder JPG")
    pf.add_argument("--page", type=int, default=1, help="PDF-Seite (Standard 1)")
    pf.add_argument("--fit", action="store_true",
                    help="verkleinern, falls zu groß (Codes evtl. nicht mehr lesbar)")
    pf.add_argument("--rotate", default="auto", choices=["auto", "0", "90", "180", "270"],
                    help="auto (Standard: nur drehen wenn nötig) oder Grad im Uhrzeigersinn")
    _add_output_options(pf)

    sub.add_parser("media", help="eingelegte Rolle vom Drucker abfragen (druckt nichts)")

    di = sub.add_parser("install-desktop", help="labelwerk-gui im Starter (Super-Taste) eintragen")
    di.add_argument("--remove", action="store_true", help="Eintrag und Icon wieder entfernen")
    return p


_HARDWARE_HINT = "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb'"
_NOT_DETECTED = {
    "linux_kernel": f"{PRINTER_NOT_FOUND}\nManuell angeben mit -p file:///dev/usb/lpN",
    "pyusb": "Brother-Drucker per USB (pyusb) nicht gefunden.\n"
             f"{_HARDWARE_HINT}, Zugriff auf den USB-Bus (udev-Regel).\n"
             "Manuell angeben mit -p usb://0x04f9:0xPID",
    "network": "Netzwerkdrucker werden nicht automatisch erkannt.\n"
               "Adresse angeben mit -p tcp://IP",
}


def _detect_printer(backend: str) -> str | None:
    if backend == "linux_kernel":
        return find_brother_lp()
    if backend == "pyusb":
        return find_brother_usb()
    return None


def _make_image(args: argparse.Namespace) -> Image.Image:
    if args.cmd == "print-file":
        img = crop(load_file(args.file, page=args.page))
        rotate = args.rotate if args.rotate == "auto" else int(args.rotate)
        return fit_to_label(img, args.label, fit=args.fit, model=args.model, rotate=rotate)
    text = args.text.replace("\\n", "\n")
    doc = Document(args.label, orientation=args.orientation, margin_mm=args.margin,
                   objects=[TextObject(text, font_size=args.font_size, font_path=args.font)])
    return render_document(doc, args.model)


def _send(img: Image.Image, args: argparse.Namespace) -> int:
    if args.printer == "auto":
        args.printer = _detect_printer(args.backend)
        if args.printer is None:
            busy = args.backend == "linux_kernel" and brother_busy()
            print(BUSY_MESSAGE if busy else _NOT_DETECTED[args.backend], file=sys.stderr)
            return 2

    try:
        status = prn.print_image(img, args.label, model=args.model, printer=args.printer,
                                 backend=args.backend, cut=not args.no_cut)
    except prn.PrintError as e:
        print(e, file=sys.stderr)
        return 2
    ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
    print(f"Status: {status.get('outcome')}")
    return 0 if ok else 1


def _show_media() -> int:
    printer = find_brother_lp()
    if printer is None:
        print(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND, file=sys.stderr)
        return 2
    try:
        media = read_media(printer)
    except MediaError as e:
        print(e, file=sys.stderr)
        return 2
    label = label_for_media(media)
    hint = f" (Etikett {label})" if label else " (kein passendes Etikett)" if media.kind != "none" else ""
    print(f"Eingelegt: {media.describe()}{hint}")
    return 0


def _apply_settings(args: argparse.Namespace) -> None:
    """Nicht angegebene Optionen mit den Standardwerten aus den Einstellungen füllen."""
    settings = load_settings()
    for warning in settings.warnings:
        print(warning, file=sys.stderr)
    if getattr(args, "label", None) is None and hasattr(args, "label"):
        args.label = settings.label_id
    if args.cmd == "print":
        args.orientation = args.orientation or settings.orientation
        args.margin = settings.margin_mm if args.margin is None else args.margin
        args.font_size = args.font_size or settings.font_size


def _install_desktop(remove: bool) -> int:
    if remove:
        removed = desktop.uninstall()
        print("\n".join(f"Entfernt: {p}" for p in removed) or "Nichts zu entfernen.")
        return 0
    gui_exe = Path(sys.executable).parent / "labelwerk-gui"
    try:
        paths = desktop.install(gui_exe)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    for path in paths:
        print(f"Installiert: {path}")
    print("labelwerk erscheint jetzt im Starter (ggf. kurz warten oder neu anmelden).")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.cmd == "labels":
        for lbl in labels_for_model(args.model):
            size = f"{lbl.width}x{lbl.height}" if lbl.height else f"{lbl.width}"
            print(f"{lbl.id:<10} {size:<10} {lbl.description}")
        return 0

    if args.cmd == "install-desktop":
        return _install_desktop(args.remove)
    if args.cmd == "media":
        return _show_media()

    _apply_settings(args)

    try:
        img = _make_image(args)
    except (ValueError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        return 2

    if args.preview:
        try:
            img.save(args.preview)
        except (OSError, ValueError) as e:
            print(f"Vorschau kann nicht gespeichert werden: {args.preview} ({e})", file=sys.stderr)
            return 2
        print(f"Vorschau: {args.preview} ({format_mm(img.width)} × {format_mm(img.height)} mm)")
        return 0

    return _send(img, args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Grün prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: `159 passed`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/cli.py tests/conftest.py tests/test_cli.py
git commit -m "CLI: Standardwerte aus Einstellungen, --orientation, --margin, Befehl media

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 5: GUI – Papier-Panel (Ränder, Ausrichtung), gedrehte Arbeitsfläche, Start mit Einstellungen

**Files:** Modify `src/labelwerk/gui/panels/paper.py`, `src/labelwerk/gui/canvas.py`, `src/labelwerk/gui/main_window.py` (je komplett), Create `tests/gui/test_gui_papier.py`

**Interfaces:**
- Consumes: Task 1 (`Document.orientation/margin_mm`, `MAX_MARGIN_MM`), Task 2 (`Settings`, `load_settings`, `new_document`).
- Produces: `PaperPanel.margin` (QDoubleSpinBox), `PaperPanel.horizontal`/`.vertical` (QRadioButton); `Canvas.set_document(label, image, orientation="vertical")`, `Canvas.orientation`, `Canvas.label_view_rect() -> QRectF`, `Canvas._caption`; `MainWindow(doc=None, tools=TOOLS, model=DEFAULT_MODEL, settings=None)` mit `self.settings`, Startzoom aus Einstellungen, `Settings.warnings` in der Statusleiste.

- [ ] **Step 1: Failing tests**

`tests/gui/test_gui_papier.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import MM, Canvas
from labelwerk.gui.main_window import MainWindow
from labelwerk.labels import get_label
from labelwerk.render import render_document
from labelwerk.settings import Settings


@pytest.fixture
def window(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.panel("text").edit.setPlainText("Max Mustermann")
    win.render_now()
    return win


def test_orientation_switch_changes_document_and_preview(window):
    paper = window.panel("paper")
    assert paper.vertical.isChecked()
    paper.horizontal.setChecked(True)
    window.render_now()
    assert window.doc.orientation == "horizontal"
    assert window.image.tobytes() == render_document(window.doc).tobytes()


def test_margin_changes_document_and_length(window):
    paper = window.panel("paper")
    paper.horizontal.setChecked(True)
    window.render_now()
    before = window.image.height
    paper.margin.setValue(5.0)
    window.render_now()
    assert window.doc.margin_mm == 5.0
    assert window.image.height == before + 2 * (59 - 12)


def test_horizontal_view_shows_handle_right_of_label(window):
    window.panel("paper").horizontal.setChecked(True)
    window.render_now()
    canvas = window.canvas
    label_box = canvas.label_view_rect()
    handle = canvas.mapFromScene(canvas.handle.sceneBoundingRect().center())
    assert handle.x() > label_box.right()
    assert label_box.width() > label_box.height()          # Adresse liegt quer im Bild


def test_horizontal_caption_reads_length_first(qtbot):
    view = Canvas()
    qtbot.addWidget(view)
    doc = Document("62", length_mm=50, orientation="horizontal", objects=[TextObject("A")])
    view.set_document(get_label("62"), render_document(doc), "horizontal")
    assert view._caption == "50,0 × 62 mm"


def _mouse(view, kind, scene_point, buttons):
    pos = QPointF(view.mapFromScene(scene_point))
    event = QMouseEvent(kind, pos, QPointF(view.viewport().mapToGlobal(pos.toPoint())),
                        Qt.MouseButton.LeftButton if kind != QMouseEvent.Type.MouseMove
                        else Qt.MouseButton.NoButton,
                        buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), event)


def test_dragging_in_horizontal_view_sets_length(window):
    window.panel("paper").horizontal.setChecked(True)
    window.render_now()
    canvas = window.canvas
    start = canvas.handle.sceneBoundingRect().center()
    end = QPointF(start.x(), start.y() + 80.1 * MM - canvas.label_height())
    _mouse(canvas, QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseMove, end, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
    assert window.doc.length_mm == 80.0


def test_window_starts_with_settings(qtbot):
    settings = Settings(label_id="62x29", orientation="horizontal", margin_mm=3, font_size=80,
                        start_zoom=150)
    win = MainWindow(settings=settings)
    qtbot.addWidget(win)
    assert (win.doc.label_id, win.doc.orientation, win.doc.margin_mm) == ("62x29", "horizontal", 3)
    assert win.panel("paper").horizontal.isChecked()
    assert win.panel("paper").margin.value() == 3.0
    assert not win.panel("text").auto.isChecked() and win.panel("text").size.value() == 80
    assert win.canvas.zoom == 150


def test_settings_warnings_appear_in_status_bar(qtbot):
    win = MainWindow(settings=Settings(warnings=["Einstellung 'start_zoom' ungültig"]))
    qtbot.addWidget(win)
    assert "start_zoom" in win.result.text()
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: die neuen Tests schlagen fehl (z. B. `AttributeError: 'PaperPanel' object has no attribute 'vertical'`, `MainWindow.__init__() got an unexpected keyword argument 'settings'`).

- [ ] **Step 3: Implementierung**

`src/labelwerk/gui/panels/paper.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Panel „Papier“: Etikett, Länge (Endlosband), Ränder und Ausrichtung – wie im P-touch Editor."""
from __future__ import annotations

from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout,
                               QLabel, QRadioButton, QWidget)

from ...document import MAX_MARGIN_MM, Document
from ...labels import DPI, get_label, labels_for_model, length_limits
from ...printer import DEFAULT_MODEL
from . import Panel

_GROUPS = (("endless", "Endlos"), ("die_cut", "Gestanzt"), ("round", "Rund"))


class PaperPanel(Panel):
    def __init__(self, doc: Document, model: str = DEFAULT_MODEL):
        super().__init__(doc, "Papier")

        self.section("Etikett")
        self.combo = QComboBox()
        labels = labels_for_model(model)
        for shape, title in _GROUPS:
            group = [lbl for lbl in labels if lbl.shape == shape]
            if not group:
                continue
            self.combo.addItem(f"— {title} —")
            self.combo.model().item(self.combo.count() - 1).setEnabled(False)
            for lbl in group:
                self.combo.addItem(lbl.description, lbl.id)
        self.layout_.addWidget(self.combo)

        self.length_title = self.section("Länge")
        self.length_box = QWidget()
        row = QHBoxLayout(self.length_box)
        row.setContentsMargins(0, 0, 0, 0)
        self.length_auto = QCheckBox("Automatisch")
        self.length = QDoubleSpinBox()
        self.length.setSuffix(" mm")
        self.length.setDecimals(1)
        self.length.setSingleStep(0.5)
        min_len, max_len = length_limits(model)
        self.length.setRange(round(min_len * 25.4 / DPI, 1), round(max_len * 25.4 / DPI, 1))
        self.length.setValue(50.0)
        row.addWidget(self.length_auto)
        row.addWidget(self.length)
        self.layout_.addWidget(self.length_box)

        self.fixed_size = QLabel()
        self.fixed_size.setObjectName("fixedSize")
        self.layout_.addWidget(self.fixed_size)

        self.section("Ränder")
        self.margin = QDoubleSpinBox()
        self.margin.setSuffix(" mm")
        self.margin.setDecimals(1)
        self.margin.setSingleStep(0.5)
        self.margin.setRange(0.0, MAX_MARGIN_MM)
        self.margin.setToolTip("Abstand vorne/hinten in Bandlaufrichtung")
        self.layout_.addWidget(self.margin)

        self.section("Ausrichtung")
        self.horizontal = QRadioButton("Horizontal")
        self.horizontal.setToolTip("Text längs zum Band – z. B. Versandetikett")
        self.vertical = QRadioButton("Vertikal")
        self.vertical.setToolTip("Text quer zum Band")
        self.orientation_group = QButtonGroup(self)
        for button in (self.horizontal, self.vertical):
            self.orientation_group.addButton(button)
            self.layout_.addWidget(button)
        self.layout_.addStretch()

        self.refresh()
        self.combo.currentIndexChanged.connect(self._apply)
        self.length_auto.toggled.connect(self._apply)
        self.length.valueChanged.connect(self._apply)
        self.margin.valueChanged.connect(self._apply)
        self.horizontal.toggled.connect(self._apply)

    def _widgets(self):
        return (self.combo, self.length_auto, self.length, self.margin, self.horizontal, self.vertical)

    def _apply(self) -> None:
        self.doc.label_id = self.combo.currentData()
        self.doc.length_mm = None if self.length_auto.isChecked() else self.length.value()
        self.doc.margin_mm = self.margin.value()
        self.doc.orientation = "horizontal" if self.horizontal.isChecked() else "vertical"
        self._update_visibility()
        self.changed.emit()

    def refresh(self) -> None:
        for w in self._widgets():
            w.blockSignals(True)
        self.combo.setCurrentIndex(self.combo.findData(self.doc.label_id))
        self.length_auto.setChecked(self.doc.length_mm is None)
        if self.doc.length_mm is not None:
            self.length.setValue(self.doc.length_mm)
        self.margin.setValue(self.doc.margin_mm)
        (self.horizontal if self.doc.orientation == "horizontal" else self.vertical).setChecked(True)
        for w in self._widgets():
            w.blockSignals(False)
        self._update_visibility()

    def _update_visibility(self) -> None:
        label = get_label(self.doc.label_id)
        endless = label.shape == "endless"
        self.length_title.setVisible(endless)
        self.length_box.setVisible(endless)
        self.length.setEnabled(not self.length_auto.isChecked())
        self.fixed_size.setVisible(not endless)
        w, h = label.size_mm
        self.fixed_size.setText(f"Ø {w} mm · rund" if label.shape == "round"
                                else f"{w} × {h} mm · gestanzt")
```

`src/labelwerk/gui/canvas.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Arbeitsfläche: Etikett in echter Größe und Form, mm-Lineale, Zoom, Längen-Anfasser."""
from __future__ import annotations

import math

from PIL import Image, ImageOps
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from ..labels import DPI, Label, format_mm, length_limits
from ..printer import DEFAULT_MODEL

MM = DPI / 25.4          # Szene-Einheiten (Druckpunkte) pro mm
RULER = 22               # Linealbreite in Pixeln
_CORNER = 2 * MM         # Eckenradius gestanzter Etiketten
_MARGIN = 15 * MM        # grauer Rand um das Etikett
START_ZOOM = 200         # Prozent; 100 % = echte Größe


def to_qimage(img: Image.Image) -> QImage:
    """Druckbild als QImage; Weiß wird transparent, damit die Etikettform sichtbar bleibt."""
    gray = img.convert("L")
    # Immer schwarz, Alpha = 255 - L: über Weiß ergibt das exakt den Grauwert L (Vorschau = Druck)
    rgba = Image.merge("RGBA", (*(Image.new("L", gray.size, 0),) * 3, ImageOps.invert(gray)))
    return QImage(rgba.tobytes(), rgba.width, rgba.height, 4 * rgba.width,
                  QImage.Format.Format_RGBA8888).copy()


class Canvas(QGraphicsView):
    length_changed = Signal(object)   # neue Länge in mm (float) oder None = automatisch
    zoom_changed = Signal(int)        # Zoom in Prozent
    drag_finished = Signal()          # Anfasser losgelassen (nach tatsächlichem Ziehen)

    def __init__(self, model: str = DEFAULT_MODEL):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#9E9E9E"))
        self.setRenderHints(QPainter.RenderHint.Antialiasing
                            | QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        min_len, max_len = length_limits(model)
        self.min_mm, self.max_mm = min_len / MM, max_len / MM
        self.zoom = START_ZOOM
        self.orientation = "vertical"
        self._scale = 1.0
        self.label: Label | None = None
        self.outline = self.printable = self.handle = None
        self._caption = ""
        self._dragging = False
        self._moved = False
        self._grab_offset = 0.0
        self._apply_zoom()

    # --- Inhalt -----------------------------------------------------------
    def set_document(self, label: Label, image: Image.Image, orientation: str = "vertical") -> None:
        """Etikett (physische Form) und Druckbild darin anzeigen.

        Die Szene ist immer in Druckkoordinaten; bei „horizontal“ dreht die Ansicht um −90°,
        damit das Etikett in Leserichtung erscheint.
        """
        if orientation != self.orientation:
            self.orientation = orientation
            self._apply_zoom()
        scene = self.scene()
        scene.clear()
        self.label = label
        tw = label.total_width
        th = label.total_height or image.height
        path = QPainterPath()
        if label.shape == "round":
            path.addEllipse(0, 0, tw, th)
        elif label.shape == "die_cut":
            path.addRoundedRect(0, 0, tw, th, _CORNER, _CORNER)
        else:
            path.addRect(0, 0, tw, th)
        self.outline = scene.addPath(path, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))

        ox, oy = (tw - image.width) / 2, (th - image.height) / 2
        pixmap = scene.addPixmap(QPixmap.fromImage(to_qimage(image)))
        pixmap.setPos(ox, oy)
        dotted = QPen(QColor("#888888"), 1, Qt.PenStyle.DotLine)
        dotted.setCosmetic(True)
        self.printable = scene.addRect(QRectF(ox, oy, image.width, image.height), dotted)

        self.handle = None
        if label.shape == "endless":
            dashed = QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DashLine)
            dashed.setCosmetic(True)
            scene.addLine(-2 * MM, 0, tw + 2 * MM, 0, dashed)
            scene.addLine(-2 * MM, th, tw + 2 * MM, th, dashed)
            self.handle = scene.addRect(QRectF(tw / 2 - 5 * MM, th + MM, 10 * MM, 2 * MM),
                                        QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.black))
            self.handle.setCursor(Qt.CursorShape.SizeHorCursor if self.orientation == "horizontal"
                                  else Qt.CursorShape.SizeVerCursor)
            self.handle.setToolTip("Ziehen: Länge festlegen · Doppelklick: automatisch")
        self._caption = self._caption_for(th)
        scene.setSceneRect(-_MARGIN, -_MARGIN, tw + 2 * _MARGIN, th + 2 * _MARGIN)

    # --- Zoom -------------------------------------------------------------
    def set_zoom(self, percent: int) -> None:
        self.zoom = max(25, min(400, percent))
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom)

    def _apply_zoom(self) -> None:
        self._scale = self.zoom / 100 * self.logicalDpiX() / DPI   # 100 % = echte Größe
        self.resetTransform()
        self.scale(self._scale, self._scale)
        if self.orientation == "horizontal":
            self.rotate(-90)                                       # Leserichtung

    def _caption_for(self, length_dots: float) -> str:
        """Größenangabe in Leserichtung (Breite × Höhe)."""
        w, h = self.label.size_mm
        if self.label.shape == "round":
            return f"Ø {w} mm"
        along = format_mm(round(length_dots)) if self.label.shape == "endless" else str(h)
        return f"{along} × {w} mm" if self.orientation == "horizontal" else f"{w} × {along} mm"

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom + (10 if event.angleDelta().y() > 0 else -10))
        else:
            super().wheelEvent(event)

    # --- Länge ziehen -----------------------------------------------------
    def _on_handle(self, event) -> bool:
        return self.handle is not None and self.itemAt(event.position().toPoint()) is self.handle

    def is_dragging(self) -> bool:
        return self._dragging

    def snap_length(self, scene_y: float) -> float:
        """Szene-y der Unterkante → Länge in mm (Raster 0,5 mm, innerhalb der Modellgrenzen)."""
        mm = round(scene_y / MM * 2) / 2
        return min(max(mm, self.min_mm), self.max_mm)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_handle(event):
            self._dragging = True
            self._moved = False
            # Versatz zwischen Cursor und Schnittkante merken, damit der Anfasser nicht springt
            self._grab_offset = self.mapToScene(event.position().toPoint()).y() - self.label_height()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            mm = self.snap_length(
                self.mapToScene(event.position().toPoint()).y() - self._grab_offset)
            self.handle.setY(mm * MM - self.label_height())
            self._caption = self._caption_for(mm * MM)
            self.viewport().update()
            self._moved = True
            self.length_changed.emit(mm)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging:
            self._dragging = False
            if self._moved:
                self.drag_finished.emit()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._on_handle(event):
            self.length_changed.emit(None)
            return
        super().mouseDoubleClickEvent(event)

    def label_height(self) -> float:
        return self.outline.path().boundingRect().height() if self.outline else 0.0

    # --- Lineale und Beschriftung -----------------------------------------
    def drawForeground(self, painter: QPainter, rect) -> None:
        painter.save()
        painter.resetTransform()
        vw, vh = self.viewport().width(), self.viewport().height()
        if self.outline is not None:
            box = self.label_view_rect()
            painter.setPen(Qt.GlobalColor.black)
            font = QFont(painter.font())
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(box.center().x() - 150, box.top() - 26, 300, 20),
                             Qt.AlignmentFlag.AlignCenter, self._caption)
        self._draw_rulers(painter, vw, vh)
        painter.restore()

    def label_view_rect(self) -> QRectF:
        """Etikett in Ansichtskoordinaten (berücksichtigt Zoom und Drehung)."""
        if self.outline is None:
            return QRectF()
        return QRectF(self.mapFromScene(self.outline.path().boundingRect()).boundingRect())

    def _draw_rulers(self, painter: QPainter, vw: int, vh: int) -> None:
        origin = self.label_view_rect().topLeft() if self.outline else self.mapFromScene(QPointF(0, 0))
        ppm = self._scale * MM                            # Pixel pro mm
        small = QFont(painter.font())
        small.setPointSize(7)
        small.setBold(False)
        painter.setFont(small)
        painter.fillRect(0, 0, vw, RULER, Qt.GlobalColor.white)
        painter.fillRect(0, 0, RULER, vh, Qt.GlobalColor.white)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        step = 1 if ppm >= 4 else 5
        for axis, length, start in (("x", vw, origin.x()), ("y", vh, origin.y())):
            first = math.floor((RULER - start) / ppm / step) * step
            mm = first
            while True:
                pos = start + mm * ppm
                if pos > length:
                    break
                if pos >= RULER:
                    tick = 12 if mm % 10 == 0 else 7 if mm % 5 == 0 else 4
                    if axis == "x":
                        painter.drawLine(int(pos), RULER - tick, int(pos), RULER)
                        if mm % 10 == 0:
                            painter.drawText(int(pos) + 2, 9, str(mm))
                    else:
                        painter.drawLine(RULER - tick, int(pos), RULER, int(pos))
                        if mm % 10 == 0:
                            painter.drawText(1, int(pos) - 2, str(mm))
                mm += step
        painter.setPen(QPen(Qt.GlobalColor.black, 3))
        painter.drawLine(0, RULER, vw, RULER)
        painter.drawLine(RULER, 0, RULER, vh)
        painter.fillRect(0, 0, RULER, RULER, Qt.GlobalColor.white)
```

`src/labelwerk/gui/main_window.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Hauptfenster: Werkzeugleiste, Panel-Stapel, Arbeitsfläche, Statusleiste."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox, QSizePolicy,
                               QStackedWidget, QToolBar, QToolButton, QWidget)

from ..desktop import APP_NAME
from ..detect import brother_busy, find_brother_lp
from ..document import Document
from ..labels import get_label
from ..printer import DEFAULT_MODEL
from ..render import render_document
from ..settings import Settings, load_settings, new_document
from .canvas import Canvas
from .print_worker import PrintWorker
from .tools import TOOLS, Tool

RENDER_DELAY_MS = 150


class MainWindow(QMainWindow):
    def __init__(self, doc: Document | None = None, tools: list[Tool] = TOOLS,
                 model: str = DEFAULT_MODEL, settings: Settings | None = None):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)
        self.settings = settings if settings is not None else load_settings()
        self.doc = doc if doc is not None else new_document(self.settings)
        self.model = model
        self.image = None
        self._render_error: str | None = None
        self._print_signals = None

        # Werkzeugleiste + Panels aus der Registry
        toolbar = QToolBar("Werkzeuge")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)
        self.panels = QStackedWidget()
        self.panels.setObjectName("panels")
        self.panels.setFixedWidth(280)
        self.tool_actions: dict[str, QAction] = {}
        self._panel_by_key = {}
        group = QActionGroup(self)
        for index, tool in enumerate(tools):
            panel = tool.panel(self.doc)
            panel.changed.connect(self.schedule_render)
            self.panels.addWidget(panel)
            self._panel_by_key[tool.key] = panel
            action = QAction(QIcon.fromTheme(tool.icon), tool.title.upper(), self)
            action.setCheckable(True)
            action.triggered.connect(lambda _=False, i=index: self.panels.setCurrentIndex(i))
            group.addAction(action)
            toolbar.addAction(action)
            self.tool_actions[tool.key] = action
        next(iter(self.tool_actions.values())).setChecked(True)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.print_action = QAction(QIcon.fromTheme("document-print"), "DRUCKEN", self)
        self.print_action.triggered.connect(self.print_label)
        toolbar.addAction(self.print_action)
        toolbar.widgetForAction(self.print_action).setObjectName("print")

        # Arbeitsfläche
        self.canvas = Canvas(model)
        self.canvas.set_zoom(self.settings.start_zoom)
        self.canvas.length_changed.connect(self._on_length_dragged)
        self.canvas.drag_finished.connect(self.render_now)
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.panels)
        layout.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

        # Statusleiste: Drucker, Ergebnis, Zoom
        self.printer_status = QLabel()
        self.result = QLabel()
        self.statusBar().addWidget(self.printer_status)
        self.statusBar().addWidget(self.result, 1)
        self.zoom_label = QLabel()
        for text, delta in (("−", -10), ("+", 10)):
            button = QToolButton()
            button.setText(text)
            button.clicked.connect(lambda _=False, d=delta: self.canvas.set_zoom(self.canvas.zoom + d))
            self.statusBar().addPermanentWidget(button)
            if text == "−":
                self.statusBar().addPermanentWidget(self.zoom_label)
        self.canvas.zoom_changed.connect(lambda z: self.zoom_label.setText(f"{z} %"))
        self.zoom_label.setText(f"{self.canvas.zoom} %")

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(RENDER_DELAY_MS)
        self._timer.timeout.connect(self.render_now)
        self.render_now()
        self.refresh_printer()
        if self.settings.warnings:
            self._set_result(" · ".join(self.settings.warnings), "error")

    def panel(self, key: str):
        return self._panel_by_key[key]

    # --- Rendern ----------------------------------------------------------
    def schedule_render(self) -> None:
        self._timer.start()

    def render_now(self) -> None:
        self._timer.stop()
        try:
            image = render_document(self.doc, self.model)
        except ValueError as e:
            # letztes gültiges Bild bleibt in der Vorschau, wird aber nicht gedruckt
            self._render_error = str(e)
            self.panel("text").show_error(self._render_error)
            self._set_result(self._render_error, "error")
            return
        if self._render_error is not None and self.result.text() == self._render_error:
            self._set_result("", "")   # nur den Renderfehler löschen, kein Druckergebnis
        self._render_error = None
        self.panel("text").show_error(None)
        self.image = image
        self.canvas.set_document(get_label(self.doc.label_id), image, self.doc.orientation)

    def _on_length_dragged(self, length_mm) -> None:
        self.doc.length_mm = length_mm
        self.panel("paper").refresh()
        if not self.canvas.is_dragging():   # beim Ziehen erst nach dem Loslassen rendern
            self.schedule_render()

    def _set_result(self, text: str, state: str) -> None:
        self.result.setProperty("state", state)
        self.result.style().polish(self.result)
        self.result.setText(text)

    # --- Drucken ----------------------------------------------------------
    def refresh_printer(self) -> None:
        try:
            printer = find_brother_lp()
            if printer:
                text = f"● {self.model} · {Path(printer).name}"
            elif brother_busy():
                text = "● Drucker belegt (andere Anwendung)"
            else:
                text = "○ kein Drucker"
        except OSError:
            text = "○ Druckerstatus unbekannt"
        self.printer_status.setText(text)

    def confirm_empty(self) -> bool:
        answer = QMessageBox.question(
            self, "Leeres Etikett", "Das Etikett ist leer. Trotzdem drucken?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        return answer == QMessageBox.StandardButton.Yes

    def print_label(self) -> None:
        if self._timer.isActive():
            self.render_now()
        if self.image is None or self._render_error is not None:
            return   # Fehler steht bereits in der Statusleiste
        if self.doc.is_empty() and not self.confirm_empty():
            return
        self.print_action.setEnabled(False)
        self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
        self.result.style().polish(self.result)
        self.result.setText("Drucke …")
        worker = PrintWorker(self.image, self.doc.label_id, self.model)
        self._print_signals = worker.signals  # Referenz bis zum Ende des Drucks
        worker.signals.done.connect(self._print_done)
        worker.signals.failed.connect(self._print_failed)
        QThreadPool.globalInstance().start(worker)

    def _print_done(self, status: dict) -> None:
        ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
        self.result.setProperty("state", "ok" if ok else "error")
        self.result.setText("Gedruckt ✓" if ok else f"Status: {status.get('outcome')}")
        self._print_finished()

    def _print_failed(self, message: str) -> None:
        self.result.setProperty("state", "error")
        self.result.setText(message.replace("\n", " "))
        self._print_finished()

    def _print_finished(self) -> None:
        self._print_signals = None
        self.result.style().polish(self.result)
        self.print_action.setEnabled(True)
        self.refresh_printer()
```

- [ ] **Step 4: Grün prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: `166 passed`, dreimal.

- [ ] **Step 5: Sichtprüfung offscreen** (nicht committen):

```bash
XDG_CONFIG_HOME=/tmp/lw-cfg QT_QPA_PLATFORM=offscreen .venv/bin/python -c "
from PySide6.QtWidgets import QApplication
from labelwerk.gui.app import load_theme
from labelwerk.gui.main_window import MainWindow
app = QApplication([]); app.setStyleSheet(load_theme()); w = MainWindow(); w.show()
w.panel('text').edit.setPlainText('Max Mustermann\\nMusterstr. 5\\n12345 Musterstadt')
w.panel('text').auto.setChecked(False); w.panel('text').size.setValue(80)
w.panel('paper').horizontal.setChecked(True); w.render_now(); app.processEvents()
w.canvas.centerOn(w.canvas.outline); app.processEvents(); w.grab().save('/tmp/lw-horizontal.png')"
```

Expected: Adresse quer, Beschriftung „74,7 × 62 mm“, Anfasser rechts, gestrichelte Schnittkanten links/rechts, Lineal-Nullpunkt an der Etikettecke.

- [ ] **Step 6: Commit**

```bash
git add src/labelwerk/gui/panels/paper.py src/labelwerk/gui/canvas.py src/labelwerk/gui/main_window.py tests/gui/test_gui_papier.py
git commit -m "GUI: Ränder und Ausrichtung im Papier-Panel, gedrehte Arbeitsfläche, Start mit Einstellungen

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 6: GUI – Medium prüfen und Live-Druckererkennung

**Files:** Create `src/labelwerk/gui/media_worker.py`, `tests/gui/test_gui_media.py`; Modify `src/labelwerk/gui/panels/paper.py`, `src/labelwerk/gui/main_window.py`, `src/labelwerk/gui/theme/rawblock.qss`, `tests/gui/conftest.py` (je komplett)

**Interfaces:**
- Consumes: Task 3 (`read_media`, `label_for_media`, `Media`, `MediaError`), `detect.*`.
- Produces: `MediaWorker(model)` mit `signals.found(Media, label_id|None)` / `signals.failed(str)`; `PaperPanel.check` (QPushButton), `.media_status` (QLabel, `state` ok/warn/error), Signal `check_media_requested`, `set_checking()`, `show_media()`, `show_media_error()`, `clear_media()`; `MainWindow.check_media()`, `is_checking_media()`, `is_printing()`, `_printer_timer` (2000 ms), `PRINTER_POLL_MS`. Das autouse-Fixture lässt jeden echten `read_media`-Aufruf im Test scheitern.

- [ ] **Step 1: Failing tests + Fixture**

`tests/gui/conftest.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PySide6  # noqa: F401
except ImportError:  # reine CLI-Umgebung: GUI-Tests überspringen
    collect_ignore_glob = ["test_*.py"]
else:
    import pytest

    @pytest.fixture(autouse=True)
    def no_printer(monkeypatch):
        """Kein Test liest echte Druckerdaten aus /sys."""
        for module in ("labelwerk.gui.main_window", "labelwerk.gui.print_worker",
                       "labelwerk.gui.media_worker"):
            monkeypatch.setattr(f"{module}.find_brother_lp", lambda: None)
            monkeypatch.setattr(f"{module}.brother_busy", lambda: False)

        def no_hardware(printer):
            raise AssertionError("Test darf den Drucker nicht abfragen")
        monkeypatch.setattr("labelwerk.gui.media_worker.read_media", no_hardware)
```

`tests/gui/test_gui_media.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
import pytest

from labelwerk.gui.main_window import MainWindow
from labelwerk.media import Media, MediaError
from labelwerk.settings import Settings


def _printer_with(monkeypatch, media=None, error=None):
    monkeypatch.setattr("labelwerk.gui.media_worker.find_brother_lp", lambda: "file:///dev/usb/lp1")

    def read(printer):
        if error:
            raise MediaError(error)
        return media
    monkeypatch.setattr("labelwerk.gui.media_worker.read_media", read)


@pytest.fixture
def window(qtbot):
    win = MainWindow(settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    return win


def test_check_media_selects_matching_label(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, Media(62, 29, "die_cut"))
    paper = window.panel("paper")
    paper.check.click()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    assert window.doc.label_id == "62x29"
    assert paper.media_status.text() == "Eingelegt: 62 × 29 mm gestanzt ✓"
    assert paper.media_status.property("state") == "ok"
    assert paper.check.isEnabled()


def test_mismatch_warning_after_changing_label(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, Media(62, 0, "endless"))
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    paper = window.panel("paper")
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    assert paper.media_status.property("state") == "warn"
    assert "passt nicht" in paper.media_status.text()
    paper.combo.setCurrentIndex(paper.combo.findData("62"))
    assert paper.media_status.property("state") == "ok"


def test_check_media_error_is_shown(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, error="Keine Antwort vom Drucker auf die Statusabfrage.")
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    status = window.panel("paper").media_status
    assert "Keine Antwort" in status.text() and status.property("state") == "error"


def test_no_media_check_while_printing(window, monkeypatch):
    window.print_action.setEnabled(False)          # Druck läuft
    window.check_media()
    assert not window.is_checking_media()


def test_no_print_while_media_check_runs(window, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: pytest.fail("darf nicht drucken"))
    window.panel("text").edit.setPlainText("Hallo")
    window._media_signals = object()               # Prüfung läuft
    window.print_label()
    assert "geprüft" in window.result.text()


def test_printer_appearing_triggers_status_and_media_check(qtbot, monkeypatch):
    win = MainWindow(settings=Settings(check_media_on_start=True))
    qtbot.addWidget(win)
    assert win.printer_status.text() == "○ kein Drucker"
    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: "file:///dev/usb/lp1")
    _printer_with(monkeypatch, Media(62, 29, "die_cut"))
    win._printer_timer.timeout.emit()              # nächster Abfrage-Takt
    assert "lp1" in win.printer_status.text()
    qtbot.waitUntil(lambda: win.doc.label_id == "62x29", timeout=3000)


def test_printer_appearing_without_auto_check(window, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: "file:///dev/usb/lp1")
    window._printer_timer.timeout.emit()
    assert "lp1" in window.printer_status.text()
    assert not window.is_checking_media()


def test_printer_disconnect_clears_media_status(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: "file:///dev/usb/lp1")
    window.refresh_printer()
    _printer_with(monkeypatch, Media(62, 0, "endless"))
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    assert window.panel("paper").media_status.isVisibleTo(window.panel("paper"))
    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: None)
    window.refresh_printer()
    assert window.panel("paper").media_status.isHidden()
    assert window.printer_status.text() == "○ kein Drucker"
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: alle GUI-Tests mit Fehler (ERROR) aus dem autouse-Fixture: `ModuleNotFoundError: No module named 'labelwerk.gui.media_worker'`; Kern-/CLI-Tests grün.

- [ ] **Step 3: Implementierung**

`src/labelwerk/gui/media_worker.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""„Medium prüfen“ im Hintergrund-Thread (Statusabfrage, druckt nichts)."""
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal

from ..detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp
from ..media import MediaError, label_for_media, read_media


class MediaSignals(QObject):
    found = Signal(object, object)   # Media, Etikett-ID oder None
    failed = Signal(str)             # Meldung für das Papier-Panel


class MediaWorker(QRunnable):
    def __init__(self, model: str):
        super().__init__()
        self.model = model
        self.signals = MediaSignals()

    def run(self) -> None:
        try:
            printer = find_brother_lp()
            if printer is None:
                self.signals.failed.emit(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND)
                return
            media = read_media(printer)
        except MediaError as e:
            self.signals.failed.emit(str(e))
            return
        except Exception as e:  # kein Absturz des Threads; Meldung statt Traceback
            self.signals.failed.emit(f"Unerwarteter Fehler beim Prüfen der Rolle: {e}")
            return
        self.signals.found.emit(media, label_for_media(media, self.model))
```

`src/labelwerk/gui/panels/paper.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Panel „Papier“: Etikett, Länge (Endlosband), Ränder und Ausrichtung – wie im P-touch Editor."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout,
                               QLabel, QPushButton, QRadioButton, QWidget)

from ...document import MAX_MARGIN_MM, Document
from ...labels import DPI, get_label, labels_for_model, length_limits
from ...media import Media
from ...printer import DEFAULT_MODEL
from . import Panel

_GROUPS = (("endless", "Endlos"), ("die_cut", "Gestanzt"), ("round", "Rund"))


class PaperPanel(Panel):
    check_media_requested = Signal()

    def __init__(self, doc: Document, model: str = DEFAULT_MODEL):
        super().__init__(doc, "Papier")
        self.media: Media | None = None          # zuletzt erkannte Rolle
        self.media_label: str | None = None      # passendes Etikett dazu

        self.section("Etikett")
        self.combo = QComboBox()
        labels = labels_for_model(model)
        for shape, title in _GROUPS:
            group = [lbl for lbl in labels if lbl.shape == shape]
            if not group:
                continue
            self.combo.addItem(f"— {title} —")
            self.combo.model().item(self.combo.count() - 1).setEnabled(False)
            for lbl in group:
                self.combo.addItem(lbl.description, lbl.id)
        self.layout_.addWidget(self.combo)
        self.check = QPushButton("MEDIUM PRÜFEN")
        self.check.setToolTip("Eingelegte Rolle vom Drucker abfragen (druckt nichts)")
        self.check.clicked.connect(self.check_media_requested)
        self.layout_.addWidget(self.check)
        self.media_status = QLabel()
        self.media_status.setObjectName("mediaStatus")
        self.media_status.setWordWrap(True)
        self.media_status.hide()
        self.layout_.addWidget(self.media_status)

        self.length_title = self.section("Länge")
        self.length_box = QWidget()
        row = QHBoxLayout(self.length_box)
        row.setContentsMargins(0, 0, 0, 0)
        self.length_auto = QCheckBox("Automatisch")
        self.length = QDoubleSpinBox()
        self.length.setSuffix(" mm")
        self.length.setDecimals(1)
        self.length.setSingleStep(0.5)
        min_len, max_len = length_limits(model)
        self.length.setRange(round(min_len * 25.4 / DPI, 1), round(max_len * 25.4 / DPI, 1))
        self.length.setValue(50.0)
        row.addWidget(self.length_auto)
        row.addWidget(self.length)
        self.layout_.addWidget(self.length_box)

        self.fixed_size = QLabel()
        self.fixed_size.setObjectName("fixedSize")
        self.layout_.addWidget(self.fixed_size)

        self.section("Ränder")
        self.margin = QDoubleSpinBox()
        self.margin.setSuffix(" mm")
        self.margin.setDecimals(1)
        self.margin.setSingleStep(0.5)
        self.margin.setRange(0.0, MAX_MARGIN_MM)
        self.margin.setToolTip("Abstand vorne/hinten in Bandlaufrichtung")
        self.layout_.addWidget(self.margin)

        self.section("Ausrichtung")
        self.horizontal = QRadioButton("Horizontal")
        self.horizontal.setToolTip("Text längs zum Band – z. B. Versandetikett")
        self.vertical = QRadioButton("Vertikal")
        self.vertical.setToolTip("Text quer zum Band")
        self.orientation_group = QButtonGroup(self)
        for button in (self.horizontal, self.vertical):
            self.orientation_group.addButton(button)
            self.layout_.addWidget(button)
        self.layout_.addStretch()

        self.refresh()
        self.combo.currentIndexChanged.connect(self._apply)
        self.length_auto.toggled.connect(self._apply)
        self.length.valueChanged.connect(self._apply)
        self.margin.valueChanged.connect(self._apply)
        self.horizontal.toggled.connect(self._apply)

    def _widgets(self):
        return (self.combo, self.length_auto, self.length, self.margin, self.horizontal, self.vertical)

    def _apply(self) -> None:
        self.doc.label_id = self.combo.currentData()
        self.doc.length_mm = None if self.length_auto.isChecked() else self.length.value()
        self.doc.margin_mm = self.margin.value()
        self.doc.orientation = "horizontal" if self.horizontal.isChecked() else "vertical"
        self._update_visibility()
        self._update_media_status()
        self.changed.emit()

    def refresh(self) -> None:
        for w in self._widgets():
            w.blockSignals(True)
        self.combo.setCurrentIndex(self.combo.findData(self.doc.label_id))
        self.length_auto.setChecked(self.doc.length_mm is None)
        if self.doc.length_mm is not None:
            self.length.setValue(self.doc.length_mm)
        self.margin.setValue(self.doc.margin_mm)
        (self.horizontal if self.doc.orientation == "horizontal" else self.vertical).setChecked(True)
        for w in self._widgets():
            w.blockSignals(False)
        self._update_visibility()
        self._update_media_status()

    # --- Medium prüfen ----------------------------------------------------
    def set_checking(self, running: bool) -> None:
        self.check.setEnabled(not running)
        self.check.setText("PRÜFE …" if running else "MEDIUM PRÜFEN")

    def show_media(self, media: Media, label_id: str | None) -> None:
        self.media, self.media_label = media, label_id
        self._update_media_status()

    def show_media_error(self, message: str) -> None:
        self.media = self.media_label = None
        self._set_media_status(message.replace("\n", " "), "error")

    def clear_media(self) -> None:
        self.media = self.media_label = None
        self._set_media_status("", "")

    def _update_media_status(self) -> None:
        if self.media is None:
            return
        if self.media.kind == "none":
            self._set_media_status("Keine Rolle eingelegt.", "warn")
        elif self.media_label is None:
            self._set_media_status(f"Eingelegt: {self.media.describe()} – kein passendes Etikett.", "warn")
        elif self.media_label == self.doc.label_id:
            self._set_media_status(f"Eingelegt: {self.media.describe()} ✓", "ok")
        else:
            self._set_media_status(f"Eingelegt ist {self.media.describe()} – Auswahl passt nicht.",
                                   "warn")

    def _set_media_status(self, text: str, state: str) -> None:
        self.media_status.setProperty("state", state)
        self.media_status.style().polish(self.media_status)
        self.media_status.setText(text)
        self.media_status.setVisible(bool(text))

    def _update_visibility(self) -> None:
        label = get_label(self.doc.label_id)
        endless = label.shape == "endless"
        self.length_title.setVisible(endless)
        self.length_box.setVisible(endless)
        self.length.setEnabled(not self.length_auto.isChecked())
        self.fixed_size.setVisible(not endless)
        w, h = label.size_mm
        self.fixed_size.setText(f"Ø {w} mm · rund" if label.shape == "round"
                                else f"{w} × {h} mm · gestanzt")
```

`src/labelwerk/gui/main_window.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Hauptfenster: Werkzeugleiste, Panel-Stapel, Arbeitsfläche, Statusleiste."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox, QSizePolicy,
                               QStackedWidget, QToolBar, QToolButton, QWidget)

from ..desktop import APP_NAME
from ..detect import brother_busy, find_brother_lp
from ..document import Document
from ..labels import get_label
from ..printer import DEFAULT_MODEL
from ..render import render_document
from ..settings import Settings, load_settings, new_document
from .canvas import Canvas
from .media_worker import MediaWorker
from .print_worker import PrintWorker
from .tools import TOOLS, Tool

RENDER_DELAY_MS = 150
PRINTER_POLL_MS = 2000     # Druckererkennung: nur Blick in /sys, kein USB-Zugriff


class MainWindow(QMainWindow):
    def __init__(self, doc: Document | None = None, tools: list[Tool] = TOOLS,
                 model: str = DEFAULT_MODEL, settings: Settings | None = None):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)
        self.settings = settings if settings is not None else load_settings()
        self.doc = doc if doc is not None else new_document(self.settings)
        self.model = model
        self.image = None
        self._render_error: str | None = None
        self._print_signals = None
        self._media_signals = None
        self._printer_present = False

        # Werkzeugleiste + Panels aus der Registry
        toolbar = QToolBar("Werkzeuge")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)
        self.panels = QStackedWidget()
        self.panels.setObjectName("panels")
        self.panels.setFixedWidth(280)
        self.tool_actions: dict[str, QAction] = {}
        self._panel_by_key = {}
        group = QActionGroup(self)
        for index, tool in enumerate(tools):
            panel = tool.panel(self.doc)
            panel.changed.connect(self.schedule_render)
            self.panels.addWidget(panel)
            self._panel_by_key[tool.key] = panel
            action = QAction(QIcon.fromTheme(tool.icon), tool.title.upper(), self)
            action.setCheckable(True)
            action.triggered.connect(lambda _=False, i=index: self.panels.setCurrentIndex(i))
            group.addAction(action)
            toolbar.addAction(action)
            self.tool_actions[tool.key] = action
        next(iter(self.tool_actions.values())).setChecked(True)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.print_action = QAction(QIcon.fromTheme("document-print"), "DRUCKEN", self)
        self.print_action.triggered.connect(self.print_label)
        toolbar.addAction(self.print_action)
        toolbar.widgetForAction(self.print_action).setObjectName("print")

        # Arbeitsfläche
        self.canvas = Canvas(model)
        self.canvas.set_zoom(self.settings.start_zoom)
        self.canvas.length_changed.connect(self._on_length_dragged)
        self.canvas.drag_finished.connect(self.render_now)
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.panels)
        layout.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

        # Statusleiste: Drucker, Ergebnis, Zoom
        self.printer_status = QLabel()
        self.result = QLabel()
        self.statusBar().addWidget(self.printer_status)
        self.statusBar().addWidget(self.result, 1)
        self.zoom_label = QLabel()
        for text, delta in (("−", -10), ("+", 10)):
            button = QToolButton()
            button.setText(text)
            button.clicked.connect(lambda _=False, d=delta: self.canvas.set_zoom(self.canvas.zoom + d))
            self.statusBar().addPermanentWidget(button)
            if text == "−":
                self.statusBar().addPermanentWidget(self.zoom_label)
        self.canvas.zoom_changed.connect(lambda z: self.zoom_label.setText(f"{z} %"))
        self.zoom_label.setText(f"{self.canvas.zoom} %")

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(RENDER_DELAY_MS)
        self._timer.timeout.connect(self.render_now)
        self.panel("paper").check_media_requested.connect(self.check_media)
        self._printer_timer = QTimer(self)
        self._printer_timer.setInterval(PRINTER_POLL_MS)
        self._printer_timer.timeout.connect(self.refresh_printer)
        self._printer_timer.start()

        self.render_now()
        self.refresh_printer()
        if self.settings.warnings:
            self._set_result(" · ".join(self.settings.warnings), "error")

    def panel(self, key: str):
        return self._panel_by_key[key]

    # --- Rendern ----------------------------------------------------------
    def schedule_render(self) -> None:
        self._timer.start()

    def render_now(self) -> None:
        self._timer.stop()
        try:
            image = render_document(self.doc, self.model)
        except ValueError as e:
            # letztes gültiges Bild bleibt in der Vorschau, wird aber nicht gedruckt
            self._render_error = str(e)
            self.panel("text").show_error(self._render_error)
            self._set_result(self._render_error, "error")
            return
        if self._render_error is not None and self.result.text() == self._render_error:
            self._set_result("", "")   # nur den Renderfehler löschen, kein Druckergebnis
        self._render_error = None
        self.panel("text").show_error(None)
        self.image = image
        self.canvas.set_document(get_label(self.doc.label_id), image, self.doc.orientation)

    def _on_length_dragged(self, length_mm) -> None:
        self.doc.length_mm = length_mm
        self.panel("paper").refresh()
        if not self.canvas.is_dragging():   # beim Ziehen erst nach dem Loslassen rendern
            self.schedule_render()

    def _set_result(self, text: str, state: str) -> None:
        self.result.setProperty("state", state)
        self.result.style().polish(self.result)
        self.result.setText(text)

    # --- Drucken ----------------------------------------------------------
    def refresh_printer(self) -> None:
        """Statusleiste aktualisieren; beim Erscheinen des Druckers ggf. Medium prüfen."""
        try:
            printer = find_brother_lp()
            if printer:
                text = f"● {self.model} · {Path(printer).name}"
            elif brother_busy():
                text = "● Drucker belegt (andere Anwendung)"
            else:
                text = "○ kein Drucker"
        except OSError:
            printer, text = None, "○ Druckerstatus unbekannt"
        self.printer_status.setText(text)
        present = printer is not None
        if present and not self._printer_present and self.settings.check_media_on_start:
            self.check_media()
        if not present and self._printer_present:
            self.panel("paper").clear_media()
        self._printer_present = present

    # --- Medium prüfen ----------------------------------------------------
    def is_printing(self) -> bool:
        return not self.print_action.isEnabled()

    def is_checking_media(self) -> bool:
        return self._media_signals is not None

    def check_media(self) -> None:
        if self.is_printing() or self.is_checking_media():
            return
        worker = MediaWorker(self.model)
        self._media_signals = worker.signals
        worker.signals.found.connect(self._media_found)
        worker.signals.failed.connect(self._media_failed)
        self.panel("paper").set_checking(True)
        QThreadPool.globalInstance().start(worker)

    def _media_found(self, media, label_id) -> None:
        self._media_finished()
        if label_id is not None and label_id != self.doc.label_id:
            self.doc.label_id = label_id
            self.panel("paper").refresh()
            self.schedule_render()
        self.panel("paper").show_media(media, label_id)

    def _media_failed(self, message: str) -> None:
        self._media_finished()
        self.panel("paper").show_media_error(message)

    def _media_finished(self) -> None:
        self._media_signals = None
        self.panel("paper").set_checking(False)

    def confirm_empty(self) -> bool:
        answer = QMessageBox.question(
            self, "Leeres Etikett", "Das Etikett ist leer. Trotzdem drucken?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        return answer == QMessageBox.StandardButton.Yes

    def print_label(self) -> None:
        if self._timer.isActive():
            self.render_now()
        if self.image is None or self._render_error is not None:
            return   # Fehler steht bereits in der Statusleiste
        if self.is_checking_media():
            self._set_result("Rolle wird gerade geprüft – bitte gleich noch einmal drucken.", "error")
            return
        if self.doc.is_empty() and not self.confirm_empty():
            return
        self.print_action.setEnabled(False)
        self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
        self.result.style().polish(self.result)
        self.result.setText("Drucke …")
        worker = PrintWorker(self.image, self.doc.label_id, self.model)
        self._print_signals = worker.signals  # Referenz bis zum Ende des Drucks
        worker.signals.done.connect(self._print_done)
        worker.signals.failed.connect(self._print_failed)
        QThreadPool.globalInstance().start(worker)

    def _print_done(self, status: dict) -> None:
        ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
        self.result.setProperty("state", "ok" if ok else "error")
        self.result.setText("Gedruckt ✓" if ok else f"Status: {status.get('outcome')}")
        self._print_finished()

    def _print_failed(self, message: str) -> None:
        self.result.setProperty("state", "error")
        self.result.setText(message.replace("\n", " "))
        self._print_finished()

    def _print_finished(self) -> None:
        self._print_signals = None
        self.result.style().polish(self.result)
        self.print_action.setEnabled(True)
        self.refresh_printer()
```

`src/labelwerk/gui/theme/rawblock.qss` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```css
/* labelwerk – an RawBlock angelehnt: Schwarz/Weiß, kräftige Rahmen, eckig.
   Austauschbar: andere .qss-Datei laden oder ganz weglassen (System-Look). */

* {
    font-family: "Work Sans", "Inter", "DejaVu Sans", sans-serif;
    font-size: 14px;
    color: #000000;
}
QMainWindow, QWidget { background: #FFFFFF; }

QToolBar {
    background: #FFFFFF;
    border: none;
    border-bottom: 3px solid #000000;
    padding: 4px;
    spacing: 6px;
}
QToolBar QToolButton {
    background: #FFFFFF;
    border: 3px solid #000000;
    border-radius: 0;
    padding: 6px 14px;
    font-weight: 700;
    letter-spacing: 2px;
}
QToolBar QToolButton:hover, QToolBar QToolButton:checked {
    background: #000000;
    color: #FFFFFF;
}
QToolBar QToolButton#print { background: #000000; color: #FFFFFF; }
QToolBar QToolButton#print:hover { background: #FFFFFF; color: #000000; }
QToolBar QToolButton:disabled, QToolBar QToolButton#print:disabled {
    background: #F0F0F0;
    color: #999999;
    border-color: #CCCCCC;
}

#panels { border-right: 3px solid #000000; }
QLabel#panelTitle { font-size: 22px; font-weight: 900; padding: 4px 0 8px 0; }
QLabel[role="section"] { font-weight: 900; letter-spacing: 1px; padding-top: 10px; }
QLabel#fixedSize { font-family: "Space Mono", "DejaVu Sans Mono", monospace; }

QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #F0F0F0;
    border: 3px solid #000000;
    border-radius: 0;
    padding: 6px 8px;
    font-family: "Space Mono", "DejaVu Sans Mono", monospace;
}
QPlainTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { background: #E8E8E8; }
QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-width: 5px; }
QSpinBox:disabled, QDoubleSpinBox:disabled { border-color: #CCCCCC; background: #F5F5F5; color: #999999; }
QComboBox QAbstractItemView { border: 3px solid #000000; selection-background-color: #000000; selection-color: #FFFFFF; }

QCheckBox::indicator { width: 16px; height: 16px; border: 3px solid #000000; background: #FFFFFF; }
QCheckBox::indicator:checked { background: #000000; }

QLabel#error { color: #FF0000; border: 3px solid #FF0000; padding: 6px; }
QLabel#mediaStatus { border: 2px solid #000000; padding: 4px 6px; }
QLabel#mediaStatus[state="ok"] { color: #008000; border-color: #008000; }
QLabel#mediaStatus[state="warn"] { color: #CC7A00; border-color: #FFA500; }
QLabel#mediaStatus[state="error"] { color: #FF0000; border-color: #FF0000; }
QPushButton { background: #FFFFFF; border: 3px solid #000000; border-radius: 0; padding: 6px 10px; font-weight: 700; letter-spacing: 1px; }
QPushButton:hover { background: #000000; color: #FFFFFF; }
QPushButton:disabled { border-color: #CCCCCC; color: #999999; background: #F0F0F0; }

QStatusBar { border-top: 3px solid #000000; }
QStatusBar QLabel[state="ok"] { color: #008000; font-weight: 700; }
QStatusBar QLabel[state="error"] { color: #FF0000; font-weight: 700; }
QStatusBar QToolButton { border: 2px solid #000000; padding: 0 8px; font-weight: 700; }
QStatusBar QToolButton:hover { background: #000000; color: #FFFFFF; }

QGraphicsView { border: none; }
QToolTip { background: #000000; color: #FFFFFF; border: none; padding: 8px 12px; font-family: "Space Mono", "DejaVu Sans Mono", monospace; }
```

- [ ] **Step 4: Grün prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: `174 passed`, dreimal.

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/gui/media_worker.py src/labelwerk/gui/panels/paper.py src/labelwerk/gui/main_window.py src/labelwerk/gui/theme/rawblock.qss tests/gui/conftest.py tests/gui/test_gui_media.py
git commit -m "GUI: Medium prüfen und Live-Druckererkennung

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 7: GUI – Einstellungsdialog, deutsche Qt-Texte

**Files:** Create `src/labelwerk/gui/settings_dialog.py`, `tests/gui/test_gui_settings.py`; Modify `src/labelwerk/gui/app.py`, `src/labelwerk/gui/main_window.py`, `src/labelwerk/gui/theme/rawblock.qss` (je komplett)

**Interfaces:**
- Consumes: Task 2 (`Settings`, `save_settings`), `labels_for_model`, `MAX_MARGIN_MM`.
- Produces: `SettingsDialog(settings, path=None, model=..., parent=None)` mit `values() -> Settings`, `saved`, `error` (QLabel), Feldern `label`, `orientation`, `margin`, `font_auto`, `font_size`, `check_media`, `zoom`; `MainWindow.settings_action` („EINSTELLUNGEN“), `open_settings()`; `app.install_translations(app)` (qtbase_de).

- [ ] **Step 1: Failing tests**

`tests/gui/test_gui_settings.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
import json
import os
from pathlib import Path

from PySide6.QtWidgets import QDialog

from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.settings_dialog import SettingsDialog
from labelwerk.settings import Settings, load_settings


def test_dialog_shows_current_settings(qtbot):
    dialog = SettingsDialog(Settings(label_id="62x29", orientation="horizontal", margin_mm=3,
                                     font_size=80, check_media_on_start=False, start_zoom=150))
    qtbot.addWidget(dialog)
    assert dialog.values() == Settings(label_id="62x29", orientation="horizontal", margin_mm=3.0,
                                       font_size=80, check_media_on_start=False, start_zoom=150)


def test_dialog_saves_to_file(qtbot, tmp_path):
    path = tmp_path / "settings.json"
    dialog = SettingsDialog(Settings(), path=path)
    qtbot.addWidget(dialog)
    dialog.orientation.setCurrentIndex(dialog.orientation.findData("horizontal"))
    dialog.font_auto.setChecked(False)
    dialog.font_size.setValue(80)
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    saved = load_settings(path)
    assert (saved.orientation, saved.font_size) == ("horizontal", 80)
    assert dialog.saved == saved


def test_dialog_save_error_keeps_dialog_open(qtbot, tmp_path):
    blocker = tmp_path / "datei"
    blocker.write_text("x")
    dialog = SettingsDialog(Settings(), path=blocker / "settings.json")
    qtbot.addWidget(dialog)
    dialog.accept()
    assert dialog.saved is None
    assert not dialog.error.isHidden() and "nicht gespeichert" in dialog.error.text()


def test_window_opens_dialog_and_takes_new_settings(qtbot, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)

    def fake_exec(dialog):
        dialog.check_media.setChecked(False)
        dialog.accept()                       # speichert in XDG_CONFIG_HOME (Test-Ordner)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(SettingsDialog, "exec", fake_exec)
    win.settings_action.trigger()
    assert win.settings.check_media_on_start is False
    path = Path(os.environ["XDG_CONFIG_HOME"]) / "labelwerk" / "settings.json"
    assert json.loads(path.read_text())["check_media_on_start"] is False
    assert "gespeichert" in win.result.text()


def test_qt_dialog_buttons_are_german(qapp):
    from PySide6.QtWidgets import QDialogButtonBox
    from labelwerk.gui.app import install_translations
    install_translations(qapp)
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    assert sorted(b.text() for b in box.buttons()) == ["Abbrechen", "Speichern"]
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: `ModuleNotFoundError: No module named 'labelwerk.gui.settings_dialog'`

- [ ] **Step 3: Implementierung**

`src/labelwerk/gui/settings_dialog.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Dialog „Einstellungen“: Standardwerte für neue Etiketten, Drucker, Ansicht.

Neue Einstellung = Feld in settings.Settings + eine Zeile im passenden Abschnitt hier.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout)

from ..document import MAX_MARGIN_MM
from ..labels import labels_for_model
from ..printer import DEFAULT_MODEL
from ..settings import Settings, save_settings


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, path: str | Path | None = None,
                 model: str = DEFAULT_MODEL, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.path = path
        self.saved: Settings | None = None
        layout = QVBoxLayout(self)

        form = self._section(layout, "Neues Etikett")
        self.label = QComboBox()
        for lbl in labels_for_model(model):
            self.label.addItem(lbl.description, lbl.id)
        self.label.setCurrentIndex(max(0, self.label.findData(settings.label_id)))
        form.addRow("Etikett", self.label)
        self.orientation = QComboBox()
        self.orientation.addItem("Horizontal (Text längs zum Band)", "horizontal")
        self.orientation.addItem("Vertikal (Text quer zum Band)", "vertical")
        self.orientation.setCurrentIndex(self.orientation.findData(settings.orientation))
        form.addRow("Ausrichtung", self.orientation)
        self.margin = QDoubleSpinBox()
        self.margin.setSuffix(" mm")
        self.margin.setDecimals(1)
        self.margin.setSingleStep(0.5)
        self.margin.setRange(0.0, MAX_MARGIN_MM)
        self.margin.setValue(settings.margin_mm)
        form.addRow("Ränder", self.margin)
        row = QHBoxLayout()
        self.font_auto = QCheckBox("Automatisch")
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 400)
        self.font_size.setValue(settings.font_size or 80)
        self.font_auto.setChecked(settings.font_size is None)
        self.font_size.setEnabled(settings.font_size is not None)
        self.font_auto.toggled.connect(lambda auto: self.font_size.setEnabled(not auto))
        row.addWidget(self.font_auto)
        row.addWidget(self.font_size)
        form.addRow("Schriftgröße", row)

        form = self._section(layout, "Drucker")
        self.check_media = QCheckBox("Rolle beim Start und beim Einschalten prüfen")
        self.check_media.setChecked(settings.check_media_on_start)
        form.addRow(self.check_media)

        form = self._section(layout, "Ansicht")
        self.zoom = QSpinBox()
        self.zoom.setSuffix(" %")
        self.zoom.setRange(25, 400)
        self.zoom.setSingleStep(10)
        self.zoom.setValue(settings.start_zoom)
        form.addRow("Startzoom", self.zoom)

        hint = QLabel("Gilt für neue Etiketten bzw. ab dem nächsten Start.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _section(self, layout: QVBoxLayout, title: str) -> QFormLayout:
        box = QGroupBox(title.upper())
        form = QFormLayout(box)
        layout.addWidget(box)
        return form

    def values(self) -> Settings:
        return Settings(
            label_id=self.label.currentData(),
            orientation=self.orientation.currentData(),
            margin_mm=self.margin.value(),
            font_size=None if self.font_auto.isChecked() else self.font_size.value(),
            check_media_on_start=self.check_media.isChecked(),
            start_zoom=self.zoom.value(),
        )

    def accept(self) -> None:
        settings = self.values()
        try:
            save_settings(settings, self.path)
        except OSError as e:
            self.error.setText(str(e))
            self.error.show()
            return                                   # Dialog bleibt offen
        self.saved = settings
        super().accept()
```

`src/labelwerk/gui/app.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Einstiegspunkt labelwerk-gui."""
from __future__ import annotations

import sys
from importlib import resources

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ..desktop import APP_ID, APP_NAME

from .main_window import MainWindow


def load_theme(name: str = "rawblock") -> str:
    """Stylesheet aus labelwerk/gui/theme/<name>.qss."""
    return (resources.files("labelwerk.gui") / "theme" / f"{name}.qss").read_text(encoding="utf-8")


def apply_identity(app: QApplication) -> None:
    """Name, App-ID (Wayland: Zuordnung zum Starter-Eintrag) und Fenstersymbol setzen."""
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    icon = resources.files("labelwerk.gui") / "icons" / f"{APP_ID}.svg"
    app.setWindowIcon(QIcon(str(icon)))


def install_translations(app: QApplication) -> None:
    """Qt-eigene Texte (Speichern, Abbrechen, Ja …) auf Deutsch – passend zu labelwerk."""
    translator = QTranslator(app)
    if translator.load(QLocale(QLocale.Language.German, QLocale.Country.Germany), "qtbase", "_",
                       QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)


def main() -> int:
    app = QApplication(sys.argv)
    apply_identity(app)
    install_translations(app)
    app.setStyleSheet(load_theme())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

`src/labelwerk/gui/main_window.py` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```python
"""Hauptfenster: Werkzeugleiste, Panel-Stapel, Arbeitsfläche, Statusleiste."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox, QSizePolicy,
                               QStackedWidget, QToolBar, QToolButton, QWidget)

from ..desktop import APP_NAME
from ..detect import brother_busy, find_brother_lp
from ..document import Document
from ..labels import get_label
from ..printer import DEFAULT_MODEL
from ..render import render_document
from ..settings import Settings, load_settings, new_document
from .canvas import Canvas
from .media_worker import MediaWorker
from .print_worker import PrintWorker
from .settings_dialog import SettingsDialog
from .tools import TOOLS, Tool

RENDER_DELAY_MS = 150
PRINTER_POLL_MS = 2000     # Druckererkennung: nur Blick in /sys, kein USB-Zugriff


class MainWindow(QMainWindow):
    def __init__(self, doc: Document | None = None, tools: list[Tool] = TOOLS,
                 model: str = DEFAULT_MODEL, settings: Settings | None = None):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)
        self.settings = settings if settings is not None else load_settings()
        self.doc = doc if doc is not None else new_document(self.settings)
        self.model = model
        self.image = None
        self._render_error: str | None = None
        self._print_signals = None
        self._media_signals = None
        self._printer_present = False

        # Werkzeugleiste + Panels aus der Registry
        toolbar = QToolBar("Werkzeuge")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)
        self.panels = QStackedWidget()
        self.panels.setObjectName("panels")
        self.panels.setFixedWidth(280)
        self.tool_actions: dict[str, QAction] = {}
        self._panel_by_key = {}
        group = QActionGroup(self)
        for index, tool in enumerate(tools):
            panel = tool.panel(self.doc)
            panel.changed.connect(self.schedule_render)
            self.panels.addWidget(panel)
            self._panel_by_key[tool.key] = panel
            action = QAction(QIcon.fromTheme(tool.icon), tool.title.upper(), self)
            action.setCheckable(True)
            action.triggered.connect(lambda _=False, i=index: self.panels.setCurrentIndex(i))
            group.addAction(action)
            toolbar.addAction(action)
            self.tool_actions[tool.key] = action
        next(iter(self.tool_actions.values())).setChecked(True)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.settings_action = QAction(QIcon.fromTheme("preferences-system"), "EINSTELLUNGEN", self)
        self.settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(self.settings_action)
        self.print_action = QAction(QIcon.fromTheme("document-print"), "DRUCKEN", self)
        self.print_action.triggered.connect(self.print_label)
        toolbar.addAction(self.print_action)
        toolbar.widgetForAction(self.print_action).setObjectName("print")

        # Arbeitsfläche
        self.canvas = Canvas(model)
        self.canvas.set_zoom(self.settings.start_zoom)
        self.canvas.length_changed.connect(self._on_length_dragged)
        self.canvas.drag_finished.connect(self.render_now)
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.panels)
        layout.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

        # Statusleiste: Drucker, Ergebnis, Zoom
        self.printer_status = QLabel()
        self.result = QLabel()
        self.statusBar().addWidget(self.printer_status)
        self.statusBar().addWidget(self.result, 1)
        self.zoom_label = QLabel()
        for text, delta in (("−", -10), ("+", 10)):
            button = QToolButton()
            button.setText(text)
            button.clicked.connect(lambda _=False, d=delta: self.canvas.set_zoom(self.canvas.zoom + d))
            self.statusBar().addPermanentWidget(button)
            if text == "−":
                self.statusBar().addPermanentWidget(self.zoom_label)
        self.canvas.zoom_changed.connect(lambda z: self.zoom_label.setText(f"{z} %"))
        self.zoom_label.setText(f"{self.canvas.zoom} %")

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(RENDER_DELAY_MS)
        self._timer.timeout.connect(self.render_now)
        self.panel("paper").check_media_requested.connect(self.check_media)
        self._printer_timer = QTimer(self)
        self._printer_timer.setInterval(PRINTER_POLL_MS)
        self._printer_timer.timeout.connect(self.refresh_printer)
        self._printer_timer.start()

        self.render_now()
        self.refresh_printer()
        if self.settings.warnings:
            self._set_result(" · ".join(self.settings.warnings), "error")

    def panel(self, key: str):
        return self._panel_by_key[key]

    # --- Rendern ----------------------------------------------------------
    def schedule_render(self) -> None:
        self._timer.start()

    def render_now(self) -> None:
        self._timer.stop()
        try:
            image = render_document(self.doc, self.model)
        except ValueError as e:
            # letztes gültiges Bild bleibt in der Vorschau, wird aber nicht gedruckt
            self._render_error = str(e)
            self.panel("text").show_error(self._render_error)
            self._set_result(self._render_error, "error")
            return
        if self._render_error is not None and self.result.text() == self._render_error:
            self._set_result("", "")   # nur den Renderfehler löschen, kein Druckergebnis
        self._render_error = None
        self.panel("text").show_error(None)
        self.image = image
        self.canvas.set_document(get_label(self.doc.label_id), image, self.doc.orientation)

    def _on_length_dragged(self, length_mm) -> None:
        self.doc.length_mm = length_mm
        self.panel("paper").refresh()
        if not self.canvas.is_dragging():   # beim Ziehen erst nach dem Loslassen rendern
            self.schedule_render()

    def _set_result(self, text: str, state: str) -> None:
        self.result.setProperty("state", state)
        self.result.style().polish(self.result)
        self.result.setText(text)

    # --- Drucken ----------------------------------------------------------
    def refresh_printer(self) -> None:
        """Statusleiste aktualisieren; beim Erscheinen des Druckers ggf. Medium prüfen."""
        try:
            printer = find_brother_lp()
            if printer:
                text = f"● {self.model} · {Path(printer).name}"
            elif brother_busy():
                text = "● Drucker belegt (andere Anwendung)"
            else:
                text = "○ kein Drucker"
        except OSError:
            printer, text = None, "○ Druckerstatus unbekannt"
        self.printer_status.setText(text)
        present = printer is not None
        if present and not self._printer_present and self.settings.check_media_on_start:
            self.check_media()
        if not present and self._printer_present:
            self.panel("paper").clear_media()
        self._printer_present = present

    # --- Einstellungen ----------------------------------------------------
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, model=self.model, parent=self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted and dialog.saved is not None:
            self.settings = dialog.saved
            self._set_result("Einstellungen gespeichert – gelten für neue Etiketten.", "ok")

    # --- Medium prüfen ----------------------------------------------------
    def is_printing(self) -> bool:
        return not self.print_action.isEnabled()

    def is_checking_media(self) -> bool:
        return self._media_signals is not None

    def check_media(self) -> None:
        if self.is_printing() or self.is_checking_media():
            return
        worker = MediaWorker(self.model)
        self._media_signals = worker.signals
        worker.signals.found.connect(self._media_found)
        worker.signals.failed.connect(self._media_failed)
        self.panel("paper").set_checking(True)
        QThreadPool.globalInstance().start(worker)

    def _media_found(self, media, label_id) -> None:
        self._media_finished()
        if label_id is not None and label_id != self.doc.label_id:
            self.doc.label_id = label_id
            self.panel("paper").refresh()
            self.schedule_render()
        self.panel("paper").show_media(media, label_id)

    def _media_failed(self, message: str) -> None:
        self._media_finished()
        self.panel("paper").show_media_error(message)

    def _media_finished(self) -> None:
        self._media_signals = None
        self.panel("paper").set_checking(False)

    def confirm_empty(self) -> bool:
        answer = QMessageBox.question(
            self, "Leeres Etikett", "Das Etikett ist leer. Trotzdem drucken?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        return answer == QMessageBox.StandardButton.Yes

    def print_label(self) -> None:
        if self._timer.isActive():
            self.render_now()
        if self.image is None or self._render_error is not None:
            return   # Fehler steht bereits in der Statusleiste
        if self.is_checking_media():
            self._set_result("Rolle wird gerade geprüft – bitte gleich noch einmal drucken.", "error")
            return
        if self.doc.is_empty() and not self.confirm_empty():
            return
        self.print_action.setEnabled(False)
        self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
        self.result.style().polish(self.result)
        self.result.setText("Drucke …")
        worker = PrintWorker(self.image, self.doc.label_id, self.model)
        self._print_signals = worker.signals  # Referenz bis zum Ende des Drucks
        worker.signals.done.connect(self._print_done)
        worker.signals.failed.connect(self._print_failed)
        QThreadPool.globalInstance().start(worker)

    def _print_done(self, status: dict) -> None:
        ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
        self.result.setProperty("state", "ok" if ok else "error")
        self.result.setText("Gedruckt ✓" if ok else f"Status: {status.get('outcome')}")
        self._print_finished()

    def _print_failed(self, message: str) -> None:
        self.result.setProperty("state", "error")
        self.result.setText(message.replace("\n", " "))
        self._print_finished()

    def _print_finished(self) -> None:
        self._print_signals = None
        self.result.style().polish(self.result)
        self.print_action.setEnabled(True)
        self.refresh_printer()
```

`src/labelwerk/gui/theme/rawblock.qss` – **vollständiger Inhalt** (Datei anlegen bzw. komplett ersetzen):

```css
/* labelwerk – an RawBlock angelehnt: Schwarz/Weiß, kräftige Rahmen, eckig.
   Austauschbar: andere .qss-Datei laden oder ganz weglassen (System-Look). */

* {
    font-family: "Work Sans", "Inter", "DejaVu Sans", sans-serif;
    font-size: 14px;
    color: #000000;
}
QMainWindow, QWidget { background: #FFFFFF; }

QToolBar {
    background: #FFFFFF;
    border: none;
    border-bottom: 3px solid #000000;
    padding: 4px;
    spacing: 6px;
}
QToolBar QToolButton {
    background: #FFFFFF;
    border: 3px solid #000000;
    border-radius: 0;
    padding: 6px 14px;
    font-weight: 700;
    letter-spacing: 2px;
}
QToolBar QToolButton:hover, QToolBar QToolButton:checked {
    background: #000000;
    color: #FFFFFF;
}
QToolBar QToolButton#print { background: #000000; color: #FFFFFF; }
QToolBar QToolButton#print:hover { background: #FFFFFF; color: #000000; }
QToolBar QToolButton:disabled, QToolBar QToolButton#print:disabled {
    background: #F0F0F0;
    color: #999999;
    border-color: #CCCCCC;
}

#panels { border-right: 3px solid #000000; }
QLabel#panelTitle { font-size: 22px; font-weight: 900; padding: 4px 0 8px 0; }
QLabel[role="section"] { font-weight: 900; letter-spacing: 1px; padding-top: 10px; }
QLabel#fixedSize { font-family: "Space Mono", "DejaVu Sans Mono", monospace; }

QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #F0F0F0;
    border: 3px solid #000000;
    border-radius: 0;
    padding: 6px 8px;
    font-family: "Space Mono", "DejaVu Sans Mono", monospace;
}
QPlainTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { background: #E8E8E8; }
QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-width: 5px; }
QSpinBox, QDoubleSpinBox { padding-left: 12px; }
QSpinBox:disabled, QDoubleSpinBox:disabled { border-color: #CCCCCC; background: #F5F5F5; color: #999999; }
QComboBox QAbstractItemView { border: 3px solid #000000; selection-background-color: #000000; selection-color: #FFFFFF; }

QCheckBox::indicator { width: 16px; height: 16px; border: 3px solid #000000; background: #FFFFFF; }
QCheckBox::indicator:checked { background: #000000; }

QLabel#error { color: #FF0000; border: 3px solid #FF0000; padding: 6px; }
QLabel#mediaStatus { border: 2px solid #000000; padding: 4px 6px; }
QLabel#mediaStatus[state="ok"] { color: #008000; border-color: #008000; }
QLabel#mediaStatus[state="warn"] { color: #CC7A00; border-color: #FFA500; }
QLabel#mediaStatus[state="error"] { color: #FF0000; border-color: #FF0000; }
QPushButton { background: #FFFFFF; border: 3px solid #000000; border-radius: 0; padding: 6px 10px; font-weight: 700; letter-spacing: 1px; }
QPushButton:hover { background: #000000; color: #FFFFFF; }
QPushButton:disabled { border-color: #CCCCCC; color: #999999; background: #F0F0F0; }

QStatusBar { border-top: 3px solid #000000; }
QStatusBar QLabel[state="ok"] { color: #008000; font-weight: 700; }
QStatusBar QLabel[state="error"] { color: #FF0000; font-weight: 700; }
QStatusBar QToolButton { border: 2px solid #000000; padding: 0 8px; font-weight: 700; }
QStatusBar QToolButton:hover { background: #000000; color: #FFFFFF; }

QGraphicsView { border: none; }
QToolTip { background: #000000; color: #FFFFFF; border: none; padding: 8px 12px; font-family: "Space Mono", "DejaVu Sans Mono", monospace; }
```

- [ ] **Step 4: Grün prüfen** – Run: `.venv/bin/python -m pytest -q`
Expected: `179 passed`, dreimal.

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/gui/settings_dialog.py src/labelwerk/gui/app.py src/labelwerk/gui/main_window.py src/labelwerk/gui/theme/rawblock.qss tests/gui/test_gui_settings.py
git commit -m "GUI: Einstellungsdialog, Qt-Standardtexte auf Deutsch

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 8: Doku

**Files:** Modify `README.md`, `CLAUDE.md`

- [ ] **Step 1: README** – Abschnitt „Benutzung“ um folgende Zeilen im Codeblock ergänzen:

```bash
labelwerk media                                            # eingelegte Rolle anzeigen (druckt nichts)
labelwerk print "Max Mustermann\nMusterstr. 5\n12345 Musterstadt" --orientation horizontal -s 80
```

und unter „Grafische Oberfläche“ einen Absatz ergänzen:

```markdown
Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI); gespeichert in `~/.config/labelwerk/settings.json`.
```

- [ ] **Step 2: CLAUDE.md**
  - „Stand (funktioniert)“: diese Zeile ergänzen und die Testzahl auf `179 Tests grün` setzen:
    ```
    - Papier: Ausrichtung H/V, Ränder, Medium prüfen (GUI + `labelwerk media`), Einstellungen (`settings.json`, GUI-Dialog), Live-Druckererkennung.
    ```
  - „Architektur“: Zeilen ergänzen
    - `settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings)`
    - `media.py    Medium prüfen: Statusabfrage ESC i S (nicht blockierend, 2 s), Media, label_for_media`
    - unter `gui/`: `media_worker.py  Medium prüfen im Hintergrund` und `settings_dialog.py Einstellungen`
  - `cli.py`-Zeile um `labelwerk media` und `print … [--orientation horizontal|vertical] [--margin MM]` ergänzen.
  - „Hardware-Wissen“: `- Statusabfrage (Medium prüfen): Invalidate (200 × 0x00) + ESC @ + ESC i S, Antwort 32 Bytes sofort; brother_ql-Lesen nicht verwenden (kann ohne Zeitlimit blockieren).`
  - Unter „Roadmap danach“ als neuen Punkt 0 einfügen: `0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart (P-touch-Vorlagen recherchieren) · 3 Funktionsliste P-touch → labelwerk (Text-Formatierung, Rahmen, Bild, Favoriten, Layout/freies Platzieren, Speichern/Neu).`
  - Roadmap-Punkt 1 („Text 90° drehen“) und 2 („Rolle automatisch auslesen“) als erledigt markieren (`~~…~~ erledigt in Etappe 1`).

- [ ] **Step 3: Prüfen und Commit** – Run: `.venv/bin/python -m pytest -q` – Expected: `179 passed`

```bash
git add README.md CLAUDE.md
git commit -m "Doku: Papier, Medium prüfen, Einstellungen

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Abnahme (manuell, durch den Nutzer)

- [ ] `labelwerk media` → „Eingelegt: 62 mm endlos (Etikett 62)“.
- [ ] GUI starten: Statusleiste „● QL-600 · lp1“, Papier „Eingelegt: 62 mm endlos ✓“; Drucker aus/an → Status wechselt innerhalb ~2 s.
- [ ] Adresse eingeben, Ausrichtung **Horizontal**, Schrift 80 → Vorschau quer, ca. 75 mm; drucken → Etikett entspricht der Vorschau.
- [ ] Ränder auf 3 mm → Etikett wird länger.
- [ ] Einstellungen: Ausrichtung Horizontal + Schrift 80 speichern, GUI neu starten → startet so.
