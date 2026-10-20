"""Printers: description, detection and capabilities – without Qt and without print code.

A ``Printer`` describes where printing goes (URI as for ``printer.print_image``) and which
model it is; the capabilities (label width, cutter, two-colour printing, lengths) come from
brother_ql (``capabilities``). Detection works via sysfs without USB access: the model from the
printer's IEEE-1284 ID, otherwise from the USB product name, otherwise from the product ID.
Network printers are entered in the settings; nothing is detected there (no network traffic).
Other manufacturers: CUPS queues (``cups:NAME``) and Zebra direct (ZPL, ``zpl:203``).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brother_ql.models import ModelsManager

from .i18n import N_, _

BROTHER_VENDOR_ID = "04f9"
SYS_ROOT = "/sys/class/usbmisc"             # tests set an empty directory
DEFAULT_MODEL = "QL-600"
NETWORK_PORT = 9100
TESTED_MODELS = frozenset({"QL-600"})       # tested on real hardware (README table)
# USB product IDs (vendor 04f9) – last fallback if the printer supplies neither an IEEE-1284 ID
# nor a product name
PRODUCT_IDS = {
    "2015": "QL-500", "2016": "QL-550", "2027": "QL-560", "2028": "QL-570", "2029": "QL-580N",
    "201b": "QL-650TD", "20c0": "QL-600", "2042": "QL-700", "2043": "QL-710W", "2044": "QL-720NW",
    "209b": "QL-800", "209c": "QL-810W", "209d": "QL-820NWB", "2020": "QL-1050",
    "202a": "QL-1060N", "20a7": "QL-1100", "20a8": "QL-1110NWB", "20ab": "QL-1115NWB",
}
UNTESTED_HINT = N_("untested – feedback welcome")   # translate with _() when displaying


def _models() -> dict:
    """brother_ql models of the QL series (P-touch tape devices stay out)."""
    return {m.identifier: m for m in ModelsManager().iter_elements()
            if m.identifier.startswith("QL-")}


SUPPORTED_MODELS = tuple(_models())


@dataclass(frozen=True)
class Capabilities:
    """What a model can do (from brother_ql)."""
    model: str
    cutter: bool                 # cutter
    two_color: bool              # red/black (label 62red)
    max_tape_mm: int             # widest roll
    length_limits: tuple[int, int]   # continuous tape: shortest/longest length in dots
    tested: bool                 # tested on real hardware


CUPS = "cups:"                              # model ID or URI of a CUPS queue
GENERIC_LENGTH = (150, 11811)               # other printers have no continuous tape


def is_model(model) -> bool:
    """Known model: Brother QL, a CUPS queue ("cups:NAME") or Zebra
    ("zpl:203")."""
    from . import cups, zpl
    return isinstance(model, str) and (model in SUPPORTED_MODELS or zpl.is_model(model)
                                       or model.startswith(CUPS)
                                       and cups.valid_name(model[len(CUPS):]))


def brother_model(model) -> bool:
    """Brother QL (not CUPS, not Zebra)."""
    return model in SUPPORTED_MODELS


def route_fits(backend: str, model: str) -> bool:
    """Does the route to the printer (``backend_for``) fit the model? CUPS only with "cups:NAME", Zebra only
    with "zpl:…", the Brother routes only with a QL."""
    from . import zpl
    if backend == "cups":
        return isinstance(model, str) and model.startswith(CUPS)
    if backend == "zpl":
        return zpl.is_model(model)
    return brother_model(model)


def capabilities(model: str) -> Capabilities:
    if isinstance(model, str) and model.startswith(CUPS) and is_model(model):
        # the driver decides on cutting (SERIES tab) – without asking CUPS
        return Capabilities(model, False, False, 300, GENERIC_LENGTH, False)
    from . import zpl
    if zpl.is_model(model):                 # cutting: the mode in the SERIES tab
        return Capabilities(model, False, False, 104, GENERIC_LENGTH, False)
    m = _models().get(model)
    if m is None:
        raise ValueError(_("Unknown printer model: {model!r}").format(model=model))
    return Capabilities(model, bool(m.cutting), bool(m.two_color),
                        104 if m.number_bytes_per_row >= 162 else 62,
                        tuple(m.min_max_length_dots), model in TESTED_MODELS)


def known_model(name: str | None) -> str | None:
    """Model name as the printer reports it ("QL-600", "QL-600G", "Brother QL-720NW"), as a
    supported model – otherwise None. Suffixes after the model (country code) do not count."""
    if not name:
        return None
    name = name.strip().upper().replace("BROTHER ", "")
    if name in SUPPORTED_MODELS:
        return name
    matches = [m for m in SUPPORTED_MODELS if name.startswith(m)]
    return max(matches, key=len) if matches else None


@dataclass(frozen=True)
class Printer:
    """A printer: ``uri`` as for ``printer.print_image`` (``file:///dev/usb/lp1`` or
    ``tcp://host:9100``), ``model`` (None = not detected), ``name`` for display, ``source``
    ``usb`` | ``network`` (Brother) | ``cups`` | ``zebra``."""
    uri: str
    model: str | None
    name: str
    source: str = "usb"


def backend_for(uri: str) -> str:
    """Route to the printer: brother_ql backend for the URI or "cups"."""
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
    """"MFG:Brother;CMD:PT-CBP;MDL:QL-600;CLS:PRINTER;" → "QL-600"."""
    for part in text.split(";"):
        key, __, value = part.partition(":")
        if key.strip().upper() in ("MDL", "MODEL"):
            return value.strip()
    return None


def usb_printers(sys_root: str | Path | None = None,
                 dev_root: str = "/dev/usb") -> list[Printer]:
    """All Brother printers under ``/dev/usb/lp*`` (sysfs, no USB access), sorted by name."""
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
    """Zebra printers under ``/dev/usb/lp*`` (vendor 0a5f) that speak ZPL (not EPL devices and
    card printers); resolution ``dpi`` (setting), otherwise from the IEEE-1284 ID or
    the product name, otherwise 203 dpi."""
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
    """Network printers from the settings."""
    name: str
    host: str
    model: str


def network_printers(entries: list[NetworkEntry]) -> list[Printer]:
    """Entered network printers: Brother (``tcp://``) or Zebra (model "zpl:…",
    ``zpl+tcp://``)."""
    from . import zpl
    return [Printer(f"zpl+tcp://{e.host}:{NETWORK_PORT}", e.model, _network_name(e), "zebra")
            if zpl.is_model(e.model) else
            Printer(f"tcp://{e.host}:{NETWORK_PORT}", e.model, _network_name(e), "network")
            for e in entries]


def _network_name(entry: NetworkEntry) -> str:
    return _("{name} · Network").format(name=entry.name or entry.host)


def choose(printers: list[Printer], wanted: str = "") -> Printer | None:
    """The chosen printer (URI from the settings) – if it is missing, None: nothing is printed on
    a printer other than the chosen one. Automatic (""): the first USB printer found with a detected
    model (a Brother laser on lp0 must not get QL data), then the first USB printer,
    otherwise the first other one – CUPS queues never (office printers on the network are among them), only
    when chosen; None = none."""
    if wanted:
        return next((p for p in printers if p.uri == wanted), None)
    usb = [p for p in printers if p.source == "usb"]
    known = [p for p in usb if p.model is not None]
    others = [p for p in printers if p.source != "cups"]
    return (known or usb or others or [None])[0]


def printer_for(uri: str, found: list[Printer]) -> Printer:
    """Printer for a given URI: a found one with this URI, otherwise newly described –
    for ``usb://0x04f9:0xPID`` with the model for the product ID."""
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
    """Model that labels and capabilities follow: the detected one, otherwise the fallback model
    from the settings, otherwise the last detected one, otherwise ``DEFAULT_MODEL``."""
    for model in (printer.model if printer else None, fallback, last):
        if is_model(model):
            return model
    return DEFAULT_MODEL


def cups_printers(direct: list[Printer], keep: str = "", wait: bool = False,
                  office: bool = False, hidden: list[str] | None = None) -> list[Printer]:
    """Queues of CUPS as printers; a Brother QL or Zebra that labelwerk finds directly via USB
    does not appear a second time through its queue, office printers (A4/Letter) only with
    ``office`` – unless the queue is chosen (``keep``). ``wait``: wait for CUPS (CLI;
    classification happens only without ``office``), otherwise the last read list (``cups.queues``).
    ``hidden``: collects the names of hidden office printers."""
    from . import cups
    doubles = tuple(prefix for prefix, here in (
        ("usb://brother/ql", any(p.source == "usb" and p.model in SUPPORTED_MODELS for p in direct)),
        ("usb://zebra", any(p.source == "zebra" and p.uri.startswith("zpl+file://")
                            for p in direct))) if here)
    found = []
    for q in cups.queues(wait=wait, classify=not office):
        if CUPS + q.name != keep:
            if doubles and q.device.lower().startswith(doubles):
                continue
            if q.office and not office:
                if hidden is not None:
                    hidden.append(q.name)
                continue
        found.append(Printer(CUPS + q.name, CUPS + q.name, f"{q.name} · CUPS", "cups"))
    return found
