"""Drucker über CUPS (das Drucksystem von Linux) – ohne Qt und ohne zusätzliche Bibliothek: nur die
Befehle ``lpstat``, ``lpoptions`` und ``lp``.

Etikettengrößen und Auflösung kommen aus dem Treiber (PPD: ``*PaperDimension``,
``*DefaultResolution``), sonst aus den Namen der Größen (``lpoptions -l``: „62x29mm“, „w288h432“
in Punkt), sonst aus einer Liste je Hersteller (Dymo, Zebra). Schnitt-Optionen sind die
Treiber-Optionen mit „Cut“ im Namen. Jeder Aufruf hat ein Zeitlimit, Meldungen kommen englisch
(``LC_MESSAGES=C``, Namen bleiben UTF-8); Fehler werden zur übersetzten ``CupsError``. Die Liste
der Warteschlangen fragt ein Hintergrund-Thread ab – die Oberfläche wartet nie auf CUPS.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from PIL import Image

from .i18n import _
from .labels import DPI, DPI_RANGE, SIZE_MM, sized_id

PREFIX = "cups:"
PPD_DIR = Path("/etc/cups/ppd")            # Tests setzen ein leeres Verzeichnis
TIMEOUT_S = 5
PRINT_TIMEOUT_S = 120                      # lp lädt eine ganze Serie hoch
QUEUE_MAX_AGE_S = 30                       # Liste der Warteschlangen so lange wiederverwenden
INFO_MAX_AGE_S = 300                       # Treiber-Angaben einer Warteschlange ebenso
FAILED_MAX_AGE_S = 30                      # … ohne Antwort von CUPS nur kurz (nicht jedes Mal warten)
BACKGROUND = True                          # Liste im Hintergrund lesen (Tests: sofort)
# Name einer Warteschlange (CUPS: druckbar, ohne Leerzeichen, /, \, #, Anführungszeichen)
_QUEUE_NAME = re.compile(r"[^\s/\\#'\"-][^\s/\\#'\"]{0,126}")
# Schnitt-Option: „Cut…“ als Wort oder in CamelCase („DymoCutOptions“), „Schneiden“/„Schnitt…“ –
# nicht „Execute“, nicht „Schnittstelle“
_CUT = re.compile(r"(?:\b[Cc]ut|(?<=[a-z])Cut|\b[Ss]chn(?:itt|eid))(?!stelle)")
PT_MM = 25.4 / 72
# Rückfall: gängige Etiketten je Hersteller (Breite, Höhe in mm)
MEDIA_LISTS = {
    "dymo": ((89, 28), (89, 36), (54, 25), (54, 101), (57, 32), (59, 102), (25, 25), (19, 51),
             (32, 57), (36, 89)),
    "zebra": ((51, 25), (57, 32), (76, 51), (102, 51), (102, 76), (102, 102), (102, 152),
              (38, 25), (60, 40)),
}
COMMON = ((57, 32), (54, 25), (89, 36), (102, 51), (102, 152), (51, 25))   # unbekannter Hersteller


class CupsError(Exception):
    """CUPS-Befehl gescheitert (Meldung für Nutzer)."""


@dataclass(frozen=True)
class Queue:
    """Eine Warteschlange: Name und Geräte-URI (z. B. usb://DYMO/LabelWriter%20450)."""
    name: str
    device: str = ""


@dataclass(frozen=True)
class CutOption:
    """Schnitt-Option des Treibers: Schlüssel, Titel und Werte (wie ``lpoptions -l``);
    ``labels``: Anzeige der Werte (sonst die Werte selbst)."""
    key: str
    title: str
    choices: tuple[str, ...]
    default: str
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueueInfo:
    """Was der Treiber über Etiketten sagt: Größen (Schlüssel für ``lp``, Breite, Höhe in mm),
    Auflösung, Schnitt-Optionen; ``source`` woher die Größen stammen (ppd, options, list)."""
    media: tuple[tuple[str, float, float], ...]
    dpi: int
    cut_options: tuple[CutOption, ...] = ()
    source: str = "ppd"

    def label_ids(self) -> list[str]:
        ids = []
        for __, w, h in self.media:
            label_id = sized_id(w, h, self.dpi)
            if label_id not in ids:
                ids.append(label_id)
        return ids

    def media_key(self, w_mm: float, h_mm: float) -> str:
        """Größen-Schlüssel des Treibers zu einem Etikett, sonst eine eigene Größe."""
        for key, w, h in self.media:
            if abs(w - w_mm) <= 0.15 and abs(h - h_mm) <= 0.15:
                return key
        return f"Custom.{w_mm:g}x{h_mm:g}mm"


def valid_name(name) -> bool:
    """Gültiger Name einer Warteschlange (auch Schutz vor Pfaden und Optionen in Aufrufen)."""
    return isinstance(name, str) and _QUEUE_NAME.fullmatch(name) is not None


def _environment() -> dict[str, str]:
    """Umgebung für CUPS-Befehle: Meldungen englisch (gleich zu lesen), Zeichensatz bleibt."""
    env = {k: v for k, v in os.environ.items() if k not in ("LC_ALL", "LANGUAGE")}
    if "UTF-8" not in (env.get("LC_CTYPE") or env.get("LANG") or "").upper().replace("UTF8", "UTF-8"):
        env["LC_CTYPE"] = "C.UTF-8"
    env["LC_MESSAGES"] = "C"
    return env


def _run(*args: str, timeout: float = TIMEOUT_S) -> str:
    """CUPS-Befehl mit Zeitlimit; Ausgabe als Text."""
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                              check=False, env=_environment())
    except FileNotFoundError:
        raise CupsError(_("CUPS commands missing (install the package cups-client)")) from None
    except subprocess.TimeoutExpired:
        raise CupsError(_("CUPS does not answer ({command})").format(command=args[0])) from None
    if done.returncode != 0:
        reason = (done.stderr or done.stdout).strip().splitlines()
        raise CupsError(_("CUPS: {reason}").format(reason=reason[-1]) if reason
                        else _("CUPS: {command} failed").format(command=args[0]))
    return done.stdout


_lock = threading.Lock()
_queues_cache: tuple[float | None, list[Queue]] = (None, [])
_queues_thread: threading.Thread | None = None
_info_cache: dict[str, tuple[float, QueueInfo]] = {}


def read_queues() -> list[Queue]:
    """Eingerichtete Warteschlangen (``lpstat -e``, Geräte aus ``lpstat -v``) – wartet auf CUPS;
    ohne CUPS keine, ohne Geräteliste ohne Geräte."""
    try:
        names = [n.strip() for n in _run("lpstat", "-e").splitlines() if valid_name(n.strip())]
    except CupsError:
        return []
    devices = {}
    try:
        for line in _run("lpstat", "-v").splitlines():
            m = re.search(r"(\S+):\s+(\S+:/\S*)\s*$", line)      # „device for X:“, „Gerät für X:“
            if m:
                devices[m[1]] = m[2]
    except CupsError:
        pass
    return [Queue(n, devices.get(n, "")) for n in names]


def queues(max_age: float = QUEUE_MAX_AGE_S, wait: bool = False) -> list[Queue]:
    """Warteschlangen, wie zuletzt gelesen (höchstens ``max_age`` Sekunden alt); ist die Liste
    älter, liest ein Hintergrund-Thread sie neu – ``queues()`` wartet nicht (die GUI fragt alle
    2 s; der erste Aufruf liefert noch keine). ``wait``: neu lesen und warten (CLI)."""
    global _queues_cache, _queues_thread
    if wait or not BACKGROUND:
        found = read_queues()
        with _lock:
            _queues_cache = (time.monotonic(), found)
        return list(found)
    with _lock:
        stamp, cached = _queues_cache
        stale = stamp is None or time.monotonic() - stamp >= max_age
        if stale and (_queues_thread is None or not _queues_thread.is_alive()):
            _queues_thread = threading.Thread(target=_refresh_queues, daemon=True)
            _queues_thread.start()
        return list(cached)


def _refresh_queues() -> None:
    global _queues_cache
    found = read_queues()
    with _lock:
        _queues_cache = (time.monotonic(), found)


def forget() -> None:
    """Gemerkte Warteschlangen und Treiber-Angaben verwerfen (z. B. neue Warteschlange)."""
    global _queues_cache
    with _lock:
        _queues_cache = (None, [])
        _info_cache.clear()


def queue_info(name: str) -> QueueInfo:
    """Etiketten, Auflösung und Schnitt-Optionen einer Warteschlange; gemerkt (``INFO_MAX_AGE_S``),
    hat CUPS nicht geantwortet, gilt die Liste je Hersteller ``FAILED_MAX_AGE_S`` lang, dann wird
    neu gefragt. Wartet auf CUPS – nur beim Wählen des Druckers."""
    with _lock:
        stamp, info = _info_cache.get(name, (None, None))
    if info is not None and time.monotonic() - stamp < (
            INFO_MAX_AGE_S if info.source != "failed" else FAILED_MAX_AGE_S):
        return info if info.source != "failed" else replace(info, source="list")
    try:
        options = _options(name) if valid_name(name) else {}
        answered = valid_name(name)
    except CupsError:
        options, answered = {}, False
    info = _queue_info(name, options)
    with _lock:                             # ohne Antwort: kurz merken, dann neu fragen
        _info_cache[name] = (time.monotonic(), info if answered else replace(info, source="failed"))
    return info


def _queue_info(name: str, options: dict) -> QueueInfo:
    dpi, media, source = DPI, (), "list"
    try:
        if not valid_name(name):
            raise OSError("invalid queue name")      # intern, nie angezeigt
        dpi, media = _parse_ppd((PPD_DIR / f"{name}.ppd").read_text(errors="replace"))
        source = "ppd"
    except OSError:                        # nicht lesbar (Rechte) oder ohne PPD
        dpi = _option_dpi(options) or DPI
        media = tuple(m for m in (_media_from_key(k) for k in _choices(options, "PageSize")) if m)
        source = "options" if media else "list"
    if not media:
        maker = next((m for m in MEDIA_LISTS if m in name.lower()), None)
        media = tuple((f"Custom.{w}x{h}mm", float(w), float(h))
                      for w, h in MEDIA_LISTS.get(maker, COMMON))
        source = "list"
    cuts = tuple(_cut_options(options))
    return QueueInfo(media, dpi, cuts, source)


def _options(name: str) -> dict[str, tuple[str, list[str], str]]:
    """``lpoptions -p NAME -l``: Schlüssel → (Titel, Werte, Standard); CUPS antwortet nicht →
    ``CupsError``."""
    text = _run("lpoptions", "-p", name, "-l")
    out = {}
    for line in text.splitlines():
        head, sep, values = line.partition(":")
        if not sep:
            continue
        key, __, title = head.partition("/")
        choices = values.split()
        default = next((c[1:] for c in choices if c.startswith("*")), choices[0] if choices else "")
        out[key.strip()] = (title.strip() or key.strip(), [c.lstrip("*") for c in choices], default)
    return out


def _choices(options: dict, key: str) -> list[str]:
    return options.get(key, ("", [], ""))[1]


def _option_dpi(options: dict) -> int | None:
    entry = options.get("Resolution")
    if entry is None:
        return None
    return _dpi(entry[2])


def _dpi(text: str) -> int | None:
    m = re.match(r"\s*(\d+)(?:x\d+)?\s*dpi", text)
    if not m:
        return None
    value = int(m[1])
    return value if DPI_RANGE[0] <= value <= DPI_RANGE[1] else None


def _parse_ppd(text: str) -> tuple[int, tuple[tuple[str, float, float], ...]]:
    """Auflösung (``*DefaultResolution``) und Größen (``*PaperDimension Name/Text: "w h"`` in Punkt)
    einer PPD; nur feste Etiketten innerhalb der Grenzen."""
    dpi = DPI
    m = re.search(r'^\*DefaultResolution:\s*(\S+)', text, re.M)
    if m:
        dpi = _dpi(m[1]) or DPI
    media = []
    for key, w, h in re.findall(r'^\*PaperDimension\s+([^/:\s]+)[^:]*:\s*"\s*([\d.]+)\s+([\d.]+)\s*"',
                                text, re.M):
        w_mm, h_mm = round(float(w) * PT_MM, 1), round(float(h) * PT_MM, 1)
        if SIZE_MM[0] <= w_mm <= SIZE_MM[1] and SIZE_MM[0] <= h_mm <= SIZE_MM[1]:
            media.append((key, w_mm, h_mm))
    return dpi, tuple(media)


def _media_from_key(key: str) -> tuple[str, float, float] | None:
    """Größe aus einem Namen: „62x29mm“, „w288h432“ (Punkt), „4x6in“; sonst None."""
    if (m := re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm", key)):
        w, h = float(m[1]), float(m[2])
    elif (m := re.fullmatch(r"w(\d+(?:\.\d+)?)h(\d+(?:\.\d+)?)", key)):
        w, h = float(m[1]) * PT_MM, float(m[2]) * PT_MM
    elif (m := re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)in", key)):
        w, h = float(m[1]) * 25.4, float(m[2]) * 25.4
    else:
        return None
    w, h = round(w, 1), round(h, 1)
    if not (SIZE_MM[0] <= w <= SIZE_MM[1] and SIZE_MM[0] <= h <= SIZE_MM[1]):
        return None
    return key, w, h


def _cut_options(options: dict) -> list[CutOption]:
    """Treiber-Optionen zum Schneiden (Name oder Titel enthält „cut“/„schnitt“)."""
    return [CutOption(key, title, tuple(choices), default)
            for key, (title, choices, default) in options.items()
            if key != "PageSize" and _CUT.search(f"{key} {title}") and choices]


@dataclass
class Job:
    """Übergebener Auftrag (``lp``): Kennung wie „Dymo-12“, Seiten (Etiketten)."""
    id: str
    pages: int = field(default=1)


def print_images(name: str, images: list[Image.Image], w_mm: float, h_mm: float, dpi: int,
                 options: dict[str, str] | None = None) -> Job:
    """Etiketten als ein Auftrag an die Warteschlange ``name``: ein PDF mit einer Seite je Etikett
    in ``dpi`` (Seite = Etikett, 1:1 – ohne Einpassen und Drehen), Größe des Treibers bzw.
    eigene, dazu ``options`` (z. B. Schnitt). Zurück kommt die Auftrags-Kennung."""
    if not valid_name(name):
        raise CupsError(_("Invalid queue name: {name!r}").format(name=name))
    info = queue_info(name)
    key = info.media_key(w_mm, h_mm)
    with tempfile.TemporaryDirectory(prefix="labelwerk-") as folder:
        path = Path(folder) / "etiketten.pdf"
        first, *rest = [image.convert("1") for image in images]
        first.save(path, "PDF", resolution=dpi, save_all=True, append_images=rest)
        args = ["lp", "-d", name, "-o", f"media={key}", "-o", "print-scaling=none",
                "-o", "orientation-requested=3", "-o", "fit-to-page=false"]
        if not key.startswith("Custom."):                # Größe des Treibers: auch als PageSize
            args += ["-o", f"PageSize={key}"]
        for option, value in (options or {}).items():
            args += ["-o", f"{option}={value}"]
        answer = _run(*args, "--", str(path), timeout=PRINT_TIMEOUT_S)
    m = re.search(r"\b(\S+-\d+)\b", answer)                   # „request id is X-12“, „Anfrage-ID ist X-12“
    return Job(m[1] if m else name, len(images))
