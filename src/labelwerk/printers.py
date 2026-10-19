"""Drucker: Beschreibung, Erkennung und Fähigkeiten – ohne Qt und ohne Druckcode.

Ein ``Printer`` beschreibt, wohin gedruckt wird (URI wie für ``printer.print_image``) und welches
Modell es ist; die Fähigkeiten (Etikettenbreite, Abschneider, Zweifarbdruck, Längen) kommen aus
brother_ql (``capabilities``). Erkannt wird über sysfs ohne USB-Zugriff: Modell aus der
IEEE-1284-Kennung des Druckers, sonst aus dem USB-Produktnamen, sonst aus der Produkt-ID.
Netzwerkdrucker stehen in den Einstellungen; erkannt wird dort nichts (kein Netzverkehr).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brother_ql.models import ModelsManager

BROTHER_VENDOR_ID = "04f9"
SYS_ROOT = "/sys/class/usbmisc"             # Tests setzen ein leeres Verzeichnis
DEFAULT_MODEL = "QL-600"
NETWORK_PORT = 9100
TESTED_MODELS = frozenset({"QL-600"})       # auf echter Hardware geprüft (README-Tabelle)
# USB-Produkt-IDs (Vendor 04f9) – letzte Rückfallebene, wenn der Drucker weder IEEE-1284-Kennung
# noch Produktnamen liefert
PRODUCT_IDS = {
    "2015": "QL-500", "2016": "QL-550", "2027": "QL-560", "2028": "QL-570", "2029": "QL-580N",
    "201b": "QL-650TD", "20c0": "QL-600", "2042": "QL-700", "2043": "QL-710W", "2044": "QL-720NW",
    "209b": "QL-800", "209c": "QL-810W", "209d": "QL-820NWB", "2020": "QL-1050",
    "202a": "QL-1060N", "20a7": "QL-1100", "20a8": "QL-1110NWB", "20ab": "QL-1115NWB",
}
UNTESTED_HINT = "ungeprüft – Rückmeldung erwünscht"


def _models() -> dict:
    """brother_ql-Modelle der QL-Reihe (P-touch-Bandgeräte bleiben draußen)."""
    return {m.identifier: m for m in ModelsManager().iter_elements()
            if m.identifier.startswith("QL-")}


SUPPORTED_MODELS = tuple(_models())


@dataclass(frozen=True)
class Capabilities:
    """Was ein Modell kann (aus brother_ql)."""
    model: str
    cutter: bool                 # Abschneider
    two_color: bool              # Rot/Schwarz (Etikett 62red)
    max_tape_mm: int             # breiteste Rolle
    length_limits: tuple[int, int]   # Endlosband: kürzeste/längste Länge in Druckpunkten
    tested: bool                 # auf echter Hardware geprüft


def capabilities(model: str) -> Capabilities:
    m = _models().get(model)
    if m is None:
        raise ValueError(f"Unbekanntes Druckermodell: {model!r}")
    return Capabilities(model, bool(m.cutting), bool(m.two_color),
                        104 if m.number_bytes_per_row >= 162 else 62,
                        tuple(m.min_max_length_dots), model in TESTED_MODELS)


def known_model(name: str | None) -> str | None:
    """Modellname, wie ihn der Drucker meldet („QL-600“, „QL-600G“, „Brother QL-720NW“), als
    unterstütztes Modell – sonst None. Zusätze nach dem Modell (Länderkürzel) zählen nicht."""
    if not name:
        return None
    name = name.strip().upper().replace("BROTHER ", "")
    if name in SUPPORTED_MODELS:
        return name
    matches = [m for m in SUPPORTED_MODELS if name.startswith(m)]
    return max(matches, key=len) if matches else None


@dataclass(frozen=True)
class Printer:
    """Ein Drucker: ``uri`` wie für ``printer.print_image`` (``file:///dev/usb/lp1`` bzw.
    ``tcp://host:9100``), ``model`` (None = nicht erkannt), ``name`` zur Anzeige, ``source``
    ``usb`` | ``network``."""
    uri: str
    model: str | None
    name: str
    source: str = "usb"


def backend_for(uri: str) -> str:
    """brother_ql-Backend zur URI."""
    if uri.startswith("tcp://"):
        return "network"
    if uri.startswith("usb://"):
        return "pyusb"
    return "linux_kernel"


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="replace").strip()
    except OSError:
        return ""


def _ieee1284_model(text: str) -> str | None:
    """„MFG:Brother;CMD:PT-CBP;MDL:QL-600;CLS:PRINTER;“ → „QL-600“."""
    for part in text.split(";"):
        key, _, value = part.partition(":")
        if key.strip().upper() in ("MDL", "MODEL"):
            return value.strip()
    return None


def usb_printers(sys_root: str | Path | None = None,
                 dev_root: str = "/dev/usb") -> list[Printer]:
    """Alle Brother-Drucker unter ``/dev/usb/lp*`` (sysfs, ohne USB-Zugriff), nach Name sortiert."""
    found = []
    for entry in sorted(Path(sys_root or SYS_ROOT).glob("lp*")):
        iface = (entry / "device").resolve()
        for node in (iface, *iface.parents):
            if not (node / "idVendor").exists():
                continue
            if _read(node / "idVendor") == BROTHER_VENDOR_ID:
                model = (known_model(_ieee1284_model(_read(iface / "ieee1284_id")))
                         or known_model(_read(node / "product"))
                         or PRODUCT_IDS.get(_read(node / "idProduct").lower()))
                found.append(Printer(f"file://{dev_root}/{entry.name}", model,
                                     f"{model or 'Brother-Drucker'} · {entry.name}"))
            break
    return found


@dataclass(frozen=True)
class NetworkEntry:
    """Netzwerkdrucker aus den Einstellungen."""
    name: str
    host: str
    model: str


def network_printers(entries: list[NetworkEntry]) -> list[Printer]:
    return [Printer(f"tcp://{e.host}:{NETWORK_PORT}", e.model, f"{e.name or e.host} · Netzwerk",
                    "network") for e in entries]


def choose(printers: list[Printer], wanted: str = "") -> Printer | None:
    """Der gewählte Drucker (URI aus den Einstellungen; "" = automatisch) bzw. der erste gefundene
    USB-Drucker mit erkanntem Modell (ein Brother-Laser auf lp0 soll keine QL-Daten bekommen), dann
    der erste USB-Drucker, sonst der erste überhaupt; None = keiner."""
    for p in printers:
        if wanted and p.uri == wanted:
            return p
    usb = [p for p in printers if p.source == "usb"]
    known = [p for p in usb if p.model is not None]
    return (known or usb or printers or [None])[0]


def printer_for(uri: str, found: list[Printer]) -> Printer:
    """Drucker zu einer angegebenen URI: ein gefundener mit dieser URI, sonst neu beschrieben –
    bei ``usb://0x04f9:0xPID`` mit dem Modell zur Produkt-ID."""
    for p in found:
        if p.uri == uri:
            return p
    model = None
    if uri.startswith("usb://"):
        pid = uri[len("usb://"):].split("/")[0].split(":")[-1].lower().removeprefix("0x")
        model = PRODUCT_IDS.get(pid.zfill(4))
    source = "network" if uri.startswith("tcp://") else "usb"
    return Printer(uri, model, uri, source)


def effective_model(printer: Printer | None, fallback: str = "", last: str = "") -> str:
    """Modell, nach dem sich Etiketten und Fähigkeiten richten: das erkannte, sonst das Ersatzmodell
    aus den Einstellungen, sonst das zuletzt erkannte, sonst ``DEFAULT_MODEL``."""
    for model in (printer.model if printer else None, fallback, last):
        if model in SUPPORTED_MODELS:
            return model
    return DEFAULT_MODEL
