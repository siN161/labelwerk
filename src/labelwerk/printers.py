"""Drucker: Beschreibung, Erkennung und Fähigkeiten – ohne Qt und ohne Druckcode.

Ein ``Printer`` beschreibt, wohin gedruckt wird (URI wie für ``printer.print_image``) und welches
Modell es ist; die Fähigkeiten (Etikettenbreite, Abschneider, Zweifarbdruck, Längen) kommen aus
brother_ql (``capabilities``). Erkannt wird über sysfs ohne USB-Zugriff: Modell aus der
IEEE-1284-Kennung des Druckers, sonst aus dem USB-Produktnamen, sonst aus der Produkt-ID.
Netzwerkdrucker stehen in den Einstellungen; erkannt wird dort nichts (kein Netzverkehr).
Andere Hersteller: CUPS-Warteschlangen (``cups:NAME``) und Zebra direkt (ZPL, ``zpl:203``).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brother_ql.models import ModelsManager

from .i18n import N_, _

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
UNTESTED_HINT = N_("untested – feedback welcome")   # beim Anzeigen mit _() übersetzen


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


CUPS = "cups:"                              # Modell-ID bzw. URI einer CUPS-Warteschlange
GENERIC_LENGTH = (150, 11811)               # Endlosband gibt es bei anderen Druckern nicht


def is_model(model) -> bool:
    """Bekanntes Modell: Brother-QL, eine CUPS-Warteschlange („cups:NAME“) oder Zebra
    („zpl:203“)."""
    from . import cups, zpl
    return isinstance(model, str) and (model in SUPPORTED_MODELS or zpl.is_model(model)
                                       or model.startswith(CUPS)
                                       and cups.valid_name(model[len(CUPS):]))


def brother_model(model) -> bool:
    """Brother-QL (nicht CUPS, nicht Zebra)."""
    return model in SUPPORTED_MODELS


def route_fits(backend: str, model: str) -> bool:
    """Passt der Weg zum Drucker (``backend_for``) zum Modell? CUPS nur mit „cups:NAME“, Zebra nur
    mit „zpl:…“, die Brother-Wege nur mit einem QL."""
    from . import zpl
    if backend == "cups":
        return isinstance(model, str) and model.startswith(CUPS)
    if backend == "zpl":
        return zpl.is_model(model)
    return brother_model(model)


def capabilities(model: str) -> Capabilities:
    if isinstance(model, str) and model.startswith(CUPS) and is_model(model):
        # Schneiden bestimmt der Treiber (Reiter SERIE) – ohne CUPS zu fragen
        return Capabilities(model, False, False, 300, GENERIC_LENGTH, False)
    from . import zpl
    if zpl.is_model(model):                 # Schneiden: der Modus im Reiter SERIE
        return Capabilities(model, False, False, 104, GENERIC_LENGTH, False)
    m = _models().get(model)
    if m is None:
        raise ValueError(_("Unknown printer model: {model!r}").format(model=model))
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
    ``usb`` | ``network`` (Brother) | ``cups`` | ``zebra``."""
    uri: str
    model: str | None
    name: str
    source: str = "usb"


def backend_for(uri: str) -> str:
    """Weg zum Drucker: brother_ql-Backend zur URI bzw. „cups“."""
    if uri.startswith(CUPS):
        return "cups"
    if uri.startswith(("zpl+file://", "zpl+tcp://")):
        return "zpl"
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
        key, __, value = part.partition(":")
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
                                     f"{model or _('Brother printer')} · {entry.name}"))
            break
    return found


def zebra_printers(sys_root: str | Path | None = None, dev_root: str = "/dev/usb",
                   dpi: int = 0) -> list[Printer]:
    """Zebra-Drucker unter ``/dev/usb/lp*`` (Hersteller 0a5f), die ZPL sprechen (EPL-Geräte und
    Kartendrucker nicht); Auflösung ``dpi`` (Einstellung), sonst aus der IEEE-1284-Kennung bzw.
    dem Produktnamen, sonst 203 dpi."""
    from . import zpl
    found = []
    for entry in sorted(Path(sys_root or SYS_ROOT).glob("lp*")):
        iface = (entry / "device").resolve()
        for node in (iface, *iface.parents):
            if not (node / "idVendor").exists():
                continue
            ieee = _read(iface / "ieee1284_id")
            if _read(node / "idVendor") == zpl.VENDOR_ID and zpl.speaks_zpl(ieee):
                name = _ieee1284_model(ieee) or _read(node / "product") or "Zebra"
                found_dpi = (dpi if dpi in zpl.RESOLUTIONS else None) or zpl.dpi_from_id(ieee) \
                    or zpl.dpi_from_id(name) or zpl.DEFAULT_DPI
                found.append(Printer(f"zpl+file://{dev_root}/{entry.name}",
                                     zpl.model_for(found_dpi), f"{name} · {entry.name}", "zebra"))
            break
    return found


@dataclass(frozen=True)
class NetworkEntry:
    """Netzwerkdrucker aus den Einstellungen."""
    name: str
    host: str
    model: str


def network_printers(entries: list[NetworkEntry]) -> list[Printer]:
    """Eingetragene Netzwerkdrucker: Brother (``tcp://``) bzw. Zebra (Modell „zpl:…“,
    ``zpl+tcp://``)."""
    from . import zpl
    return [Printer(f"zpl+tcp://{e.host}:{NETWORK_PORT}", e.model, _network_name(e), "zebra")
            if zpl.is_model(e.model) else
            Printer(f"tcp://{e.host}:{NETWORK_PORT}", e.model, _network_name(e), "network")
            for e in entries]


def _network_name(entry: NetworkEntry) -> str:
    return _("{name} · Network").format(name=entry.name or entry.host)


def choose(printers: list[Printer], wanted: str = "") -> Printer | None:
    """Der gewählte Drucker (URI aus den Einstellungen) – fehlt er, None: gedruckt wird nicht auf
    einem anderen als dem gewählten. Automatisch (""): der erste gefundene USB-Drucker mit erkanntem
    Modell (ein Brother-Laser auf lp0 soll keine QL-Daten bekommen), dann der erste USB-Drucker,
    sonst der erste andere – CUPS-Warteschlangen nie (darunter sind Bürodrucker im Netz), nur
    gewählt; None = keiner."""
    if wanted:
        return next((p for p in printers if p.uri == wanted), None)
    usb = [p for p in printers if p.source == "usb"]
    known = [p for p in usb if p.model is not None]
    others = [p for p in printers if p.source != "cups"]
    return (known or usb or others or [None])[0]


def printer_for(uri: str, found: list[Printer]) -> Printer:
    """Drucker zu einer angegebenen URI: ein gefundener mit dieser URI, sonst neu beschrieben –
    bei ``usb://0x04f9:0xPID`` mit dem Modell zur Produkt-ID."""
    for p in found:
        if p.uri == uri:
            return p
    if uri.startswith(CUPS):
        return Printer(uri, uri, f"{uri[len(CUPS):]} · CUPS", "cups")
    if uri.startswith(("zpl+file://", "zpl+tcp://")):
        from . import zpl
        return Printer(uri, zpl.model_for(zpl.DEFAULT_DPI), uri, "zebra")
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
        if is_model(model):
            return model
    return DEFAULT_MODEL


def cups_printers(direct: list[Printer], keep: str = "", wait: bool = False) -> list[Printer]:
    """Warteschlangen von CUPS als Drucker; ein Brother-QL bzw. Zebra, den labelwerk direkt per USB
    findet, erscheint nicht noch einmal über seine Warteschlange – außer sie ist gewählt (``keep``).
    ``wait``: auf CUPS warten (CLI), sonst die zuletzt gelesene Liste (``cups.queues``)."""
    from . import cups
    doubles = tuple(prefix for prefix, here in (
        ("usb://brother/ql", any(p.source == "usb" and p.model in SUPPORTED_MODELS for p in direct)),
        ("usb://zebra", any(p.source == "zebra" and p.uri.startswith("zpl+file://")
                            for p in direct))) if here)
    return [Printer(CUPS + q.name, CUPS + q.name, f"{q.name} · CUPS", "cups")
            for q in cups.queues(wait=wait)
            if CUPS + q.name == keep or not (doubles and q.device.lower().startswith(doubles))]
