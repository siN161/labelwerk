"""Kommandozeile: labelwerk labels | print "Text" | print-file datei.pdf | media | printers | fonts |
install-desktop"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from . import desktop, i18n
from . import printer as prn
from . import printers
from .detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp, find_brother_usb
from .files import crop, fit_to_label, load_file
from .fonts import DEFAULT_FAMILY, families
from .i18n import NP_, N_, _, ngettext, pgettext
from .document import ALIGNMENTS, MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
from .labels import format_mm, get_label, labels_for_model
from .media import MediaError, label_for_media, read_media
from .render import font_warnings, render_document
from .settings import configured_language, load_settings, network_entries
from .storage import os_reason


def _font_size(value: str) -> float | None:
    """'auto' (= None) oder Größe in pt, 4–100."""
    if value.lower() == "auto":
        return None
    try:
        size = i18n.parse_number(value)
    except ValueError:
        size = 0.0
    if not MIN_PT <= size <= MAX_PT:
        raise argparse.ArgumentTypeError(_("Font size: 'auto' or 4–100 (pt)"))
    return size


def _margin(value: str) -> float:
    try:
        mm = i18n.parse_number(value)                  # Komma und Punkt
    except ValueError:
        mm = float("nan")
    if not 0 <= mm <= MAX_MARGIN_MM:      # nan fällt hier ebenfalls durch
        raise argparse.ArgumentTypeError(_("Margin: number from 0 to {max} mm").format(
            max=i18n.number(MAX_MARGIN_MM)))
    return mm


def _add_output_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-l", "--label", help=_("label, e.g. 62, or auto (roll loaded in the "
                                           "printer); default from the settings"))
    p.add_argument("-p", "--printer", default="auto",
                   help=_("auto (default), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, "
                          "cups:NAME (queue, see 'labelwerk printers'), "
                          "zpl+file:///dev/usb/lpN or zpl+tcp://IP "
                          "(Zebra, with -m zpl:203/300/600)"))
    p.add_argument("-b", "--backend", choices=["linux_kernel", "pyusb", "network", "cups", "zebra"],
                   help=_("default: from the printer (tcp:// → network)"))
    p.add_argument("--no-cut", action="store_true",
                   help=_("do not cut (Brother; for CUPS/Zebra the driver or the mode in the "
                          "GUI settings decides)"))
    p.add_argument("--preview", metavar="PNG", help=_("only save a preview, do not print"))


_UNSET = object()   # -s nicht angegeben (None bedeutet „auto“)


# Texte von argparse selbst (Python übersetzt sie nicht): markiert für die Übersetzung, eingesetzt
# über ``argparse._`` – fehlt eine (andere Python-Version), bleibt sie englisch
ARGPARSE_TEXTS = (NP_("argparse", "usage: "), NP_("argparse", "positional arguments"),
                  NP_("argparse", "options"), NP_("argparse", "show this help message and exit"),
                  NP_("argparse", "%(prog)s: error: %(message)s\n"),
                  NP_("argparse", "the following arguments are required: %s"),
                  NP_("argparse", "unrecognized arguments: %s"),
                  NP_("argparse", "invalid choice: %(value)r (choose from %(choices)s)"),
                  NP_("argparse", "argument %(argument_name)s: %(message)s"),
                  NP_("argparse", "expected one argument"),
                  NP_("argparse", "invalid %(type)s value: %(value)r"))


def _translate_argparse() -> None:
    argparse._ = lambda text: pgettext("argparse", text)


def _language(argv: list[str]) -> str:
    """``--lang de|en`` (vor dem Bau des Parsers: seine Hilfe ist schon übersetzt), sonst die
    Einstellung, sonst die Sprache des Systems."""
    for i, arg in enumerate(argv):
        if arg == "--" or not arg.startswith("-") and argv[i - 1:i] != ["-m"] \
                and argv[i - 1:i] != ["--model"] and argv[i - 1:i] != ["--lang"]:
            break                                       # Unterbefehl bzw. Ende der Optionen
        if arg == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--lang="):
            return arg.split("=", 1)[1]
    return configured_language()


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=desktop.APP_NAME)
    p.add_argument("--lang", choices=i18n.available(),
                   help=_("language of the output (default: setting, otherwise the system)"))
    p.add_argument("-m", "--model", default="auto",
                   help=_("auto (default: detected, otherwise from the settings) or e.g. QL-700, "
                          "zpl:300 (Zebra), cups:NAME; see 'labelwerk printers'"))
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("labels", help=_("list the labels for the model"))

    pr = sub.add_parser("print", help=_("print text"))
    pr.add_argument("text", help=_("text, line break with \\n"))
    pr.add_argument("-s", "--font-size", type=_font_size, default=_UNSET, metavar="PT",
                    help=_("'auto' or 4–100 pt (default from the settings)"))
    pr.add_argument("--font", help=_("path to a .ttf file"))
    pr.add_argument("--font-family", metavar="NAME",
                    help=_("font family, e.g. 'Liberation Sans' (see 'labelwerk fonts')"))
    pr.add_argument("--align", choices=ALIGNMENTS, default="center",
                    help=_("text position: left, center (default), right, justify"))
    pr.add_argument("--bold", action=argparse.BooleanOptionalAction, default=True,
                    help=_("bold (default) or --no-bold"))
    pr.add_argument("--italic", action="store_true", help=_("italic"))
    pr.add_argument("--underline", action="store_true", help=_("underlined"))
    pr.add_argument("--orientation", choices=ORIENTATIONS,
                    help=_("vertical: portrait (reading direction across the tape), horizontal: "
                           "landscape (along the tape); default from the settings"))
    pr.add_argument("--margin", type=_margin, metavar="MM",
                    help=_("margin all around from the paper edge in mm – the strips the printer "
                           "leaves free count (about 1.5 mm across, 3 mm along a continuous "
                           "tape; default from the settings)"))
    _add_output_options(pr)

    pf = sub.add_parser("print-file", help=_("print a PDF/image 1:1"))
    pf.add_argument("file", help=_("PDF, PNG or JPG"))
    pf.add_argument("--page", type=int, default=1, help=_("PDF page (default 1)"))
    pf.add_argument("--fit", action="store_true",
                    help=_("shrink if too large (codes may no longer be readable)"))
    pf.add_argument("--rotate", default="auto", choices=["auto", "0", "90", "180", "270"],
                    help=_("auto (default: rotate only if needed) or degrees clockwise"))
    _add_output_options(pf)

    sub.add_parser("media", help=_("query the roll loaded in the printer (prints nothing)"))
    pp = sub.add_parser("printers", help=_("list found printers and supported models"))
    pp.add_argument("--all", dest="show_all", action="store_true",
                    help=_("also list office printers (CUPS queues with A4/Letter paper)"))
    fo = sub.add_parser("fonts", help=_("list installed font families with German characters"))
    fo.add_argument("--all", action="store_true",
                    help=_("all font families, also copies, symbol fonts and other scripts"))

    di = sub.add_parser("install-desktop",
                        help=_("add labelwerk-gui to the launcher (Super key)"))
    di.add_argument("--remove", action="store_true", help=_("remove the entry and icon again"))
    return p


# kein Drucker gefunden, je Backend – übersetzt beim Melden (``{not_found}``: PRINTER_NOT_FOUND)
_NOT_DETECTED = {
    "linux_kernel": N_("{not_found}\nSpecify manually with -p file:///dev/usb/lpN"),
    "pyusb": N_("Brother printer not found via USB (pyusb).\n"
                "Check: switched on, Editor Lite LED off, 'lsusb', access to the USB bus "
                "(udev rule).\n"
                "Specify manually with -p usb://0x04f9:0xPID"),
    "network": N_("No network printer configured (GUI settings).\n"
                  "Specify the address with -p tcp://IP"),
    "cups": N_("No CUPS queue found (set up the printer in the printer settings).\n"
               "Specify with -p cups:NAME"),
    "zebra": N_("No Zebra printer found.\n"
                "Specify with -p zpl+file:///dev/usb/lpN or -p zpl+tcp://IP and -m zpl:203"),
}


def _target(args: argparse.Namespace, settings) -> printers.Printer | None:
    """Drucker, auf den sich der Befehl bezieht: ``-p`` (gefunden oder aus der URI beschrieben),
    bei ``-p auto`` per pyusb bzw. der gewählte/erste aus sysfs und den eingetragenen
    Netzwerkdruckern (``-b`` grenzt ein); None = keiner."""
    wanted = getattr(args, "printer", "auto")
    backend = getattr(args, "backend", None)
    if backend == "pyusb" and wanted == "auto":
        uri = find_brother_usb()
        return printers.printer_for(uri, []) if uri else None
    # CUPS nur fragen, wenn es darum geht (lpstat kann dauern)
    with_cups = (wanted.startswith("cups:") or backend == "cups"
                 or wanted == "auto" and settings.printer.startswith("cups:"))
    if wanted != "auto":                            # angegeben: nichts einzuordnen
        return printers.printer_for(wanted, _all_printers(settings, cups=with_cups, office=True))
    args.hidden_office = []                         # ausgeblendete Bürodrucker (Meldung)
    found = _all_printers(settings, cups=with_cups, hidden=args.hidden_office)
    if backend in ("network", "cups", "zebra"):
        found = [p for p in found if p.source == backend]
        if backend == "cups" and not settings.printer.startswith("cups:"):
            return found[0] if found else None      # ausdrücklich CUPS: die erste Warteschlange
    elif backend == "linux_kernel":
        found = [p for p in found if p.source == "usb"]
    return printers.choose(found, settings.printer)


def _all_printers(settings, cups: bool = True, office: bool | None = None,
                  hidden: list[str] | None = None) -> list[printers.Printer]:
    """Direkt per USB, eingetragene Netzwerkdrucker und (``cups``) Warteschlangen von CUPS;
    Bürodrucker nur mit ``office`` (None = Einstellung ``cups_all``), ausgeblendete sammelt
    ``hidden``."""
    direct = (printers.usb_printers() + printers.zebra_printers(dpi=settings.zebra_dpi)
              + printers.network_printers(network_entries(settings)))
    office = settings.cups_all if office is None else office
    return direct + (printers.cups_printers(direct, keep=settings.printer, wait=True,
                                            office=office, hidden=hidden) if cups else [])


def _resolve_model(model: str, target: printers.Printer | None, settings) -> str:
    """``-m auto``: Modell des Zieldruckers, sonst Ersatzmodell bzw. zuletzt erkanntes aus den
    Einstellungen; ein angegebenes muss bekannt sein."""
    if model != "auto":
        if not printers.is_model(model):
            raise ValueError(_("Unknown printer model {model!r} – allowed: {models}, "
                               "zpl:203/300/600 or cups:NAME").format(
                model=model, models=", ".join(printers.SUPPORTED_MODELS)))
        return model
    return printers.effective_model(target, settings.printer_model, settings.last_model)


def _auto_label(model: str, target: printers.Printer | None) -> str:
    """``-l auto``: Etikett zur eingelegten Rolle (Statusabfrage per USB beim Zieldrucker) – sonst
    ValueError."""
    if target is not None and target.source != "usb":
        raise ValueError(_("-l auto (query the roll) only works with printers via USB."))
    printer = target.uri if target is not None and target.uri.startswith("file://") \
        else find_brother_lp()
    if printer is None:
        raise ValueError(_(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND))
    media = read_media(printer)
    if media.kind == "none":
        raise ValueError(_("No roll loaded."))
    label = label_for_media(media, model)
    if label is None:
        raise ValueError(_("No label for the loaded roll ({media}) on the {model}.").format(
            media=media.describe(), model=model))
    return label


def _make_image(args: argparse.Namespace) -> Image.Image:
    if args.cmd == "print-file":
        dpi = get_label(args.label).dpi                # PDF gleich in der Auflösung des Druckers
        img = crop(load_file(args.file, page=args.page, dpi=dpi), dpi)
        rotate = args.rotate if args.rotate == "auto" else int(args.rotate)
        return fit_to_label(img, args.label, fit=args.fit, model=args.model, rotate=rotate,
                            dpi=dpi)
    text = args.text.replace("\\n", "\n")
    obj = TextObject.plain(text, size_pt=args.font_size, align=args.align,
                           family=args.font_family, bold=args.bold, italic=args.italic,
                           underline=args.underline, font_path=args.font)
    doc = Document(args.label, orientation=args.orientation, margin_mm=args.margin, objects=[obj])
    for warning in font_warnings(doc):
        print(warning, file=sys.stderr)
    return render_document(doc, args.model)


def _send(img: Image.Image, args: argparse.Namespace) -> int:
    if args.printer == "auto":
        args.printer = args.target.uri if args.target is not None else None
        if args.printer is None and args.settings.printer:
            print(_("Chosen printer {printer} not found – switch it on or specify it with -p.")
                  .format(printer=args.settings.printer), file=sys.stderr)
            return 2
        if args.printer is None:
            busy = args.backend in (None, "linux_kernel") and brother_busy()
            print(_(BUSY_MESSAGE) if busy else _(_NOT_DETECTED[args.backend or "linux_kernel"])
                  .format(not_found=_(PRINTER_NOT_FOUND)), file=sys.stderr)
            if args.backend == "cups" and getattr(args, "hidden_office", None):
                print(_("Office printers hidden: {names} – print with -p cups:NAME").format(
                    names=", ".join(args.hidden_office)), file=sys.stderr)
            return 2

    try:
        status = prn.print_image(img, args.label, model=args.model, printer=args.printer,
                                 backend={"zebra": "zpl"}.get(args.backend, args.backend),
                                 cut=not args.no_cut,
                                 options=load_settings().printer_options.get(args.model, {}))
    except prn.PrintError as e:
        print(e, file=sys.stderr)
        return 2
    ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
    if status.get("job"):
        print(_("Handed over to CUPS (job {job})").format(job=status["job"]))
    else:
        print(_("Status: {outcome}").format(outcome=status.get("outcome")))
    return 0 if ok else 1


def _show_printers(model: str, show_all: bool = False) -> int:
    """Gefundene Drucker (USB, eingetragene Netzwerkdrucker, CUPS-Warteschlangen – Bürodrucker nur
    mit ``show_all`` bzw. Einstellung ``cups_all``) und unterstützte Modelle."""
    hidden = []
    found = _all_printers(load_settings(), office=True if show_all else None, hidden=hidden)
    for p in found:
        caps = printers.capabilities(p.model) if p.model else None
        state = (_("model not detected") if caps is None else
                 _("tested") if caps.tested else _(printers.UNTESTED_HINT))
        print(f"{p.name:<28} {p.uri:<30} {state}")
    if not found:
        print(_("No printer found."))
    if hidden:
        print(ngettext("{count} office printer hidden – “labelwerk printers --all” shows it, "
                       "print with -p cups:NAME",
                       "{count} office printers hidden – “labelwerk printers --all” shows them, "
                       "print with -p cups:NAME", len(hidden)).format(count=len(hidden)))
    print(_("Effective model: {model}").format(model=model))
    models = ", ".join(m if printers.capabilities(m).tested
                       else _("{model} (untested)").format(model=m)
                       for m in printers.SUPPORTED_MODELS)
    print(_("Supported: {models}, Zebra zpl:203/300/600 (untested), CUPS queues cups:NAME "
            "(untested)").format(models=models))
    return 0


def _show_media(model: str, target: printers.Printer | None) -> int:
    if target is not None and target.source != "usb":
        print(_("Querying the roll only works with printers via USB."), file=sys.stderr)
        return 2
    printer = target.uri if target is not None and target.uri.startswith("file://") \
        else find_brother_lp()
    if printer is None:
        print(_(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND), file=sys.stderr)
        return 2
    try:
        media = read_media(printer)
    except MediaError as e:
        print(e, file=sys.stderr)
        return 2
    label = label_for_media(media, model)
    if label:
        text = _("Loaded: {media} (label {label})")
    elif media.kind != "none":
        text = _("Loaded: {media} (no matching label)")
    else:
        text = _("Loaded: {media}")
    print(text.format(media=media.describe(), label=label))
    return 0


def _apply_settings(args: argparse.Namespace) -> None:
    """Nicht angegebene Optionen mit den Standardwerten aus den Einstellungen füllen."""
    settings = load_settings(model=args.model)
    for warning in settings.warnings:
        print(warning, file=sys.stderr)
    if hasattr(args, "label") and args.label is None:
        args.label = settings.label_id
    if getattr(args, "label", None) == "auto":
        args.label = _auto_label(args.model, args.target)
    if hasattr(args, "label") and get_label(args.label).id not in {   # unbekannt: ValueError
            label.id for label in labels_for_model(args.model)}:
        raise ValueError(_("Label {label!r} does not fit the {model} – see "
                           "'labelwerk -m {model} labels'").format(label=args.label,
                                                                   model=args.model))
    if args.cmd == "print":
        args.orientation = args.orientation or settings.orientation
        args.margin = settings.margin_mm if args.margin is None else args.margin
        if args.font_size is _UNSET:
            args.font_size = settings.font_size_pt
        if args.font is None and args.font_family is None and settings.font_family != DEFAULT_FAMILY:
            args.font_family = settings.font_family


def _install_desktop(remove: bool) -> int:
    data = desktop.data_home()
    if remove:
        try:
            removed = desktop.uninstall(data, update=False)
        except OSError as e:
            print(_("labelwerk was not removed ({reason}).").format(reason=os_reason(e)),
                  file=sys.stderr)
            return 2
        print("\n".join(_("Removed: {path}").format(path=p) for p in removed)
              or _("Nothing to remove."))
        if removed:
            _report_update(desktop.update_databases(data))
        return 0
    gui_exe = Path(sys.executable).parent / "labelwerk-gui"
    try:
        paths = desktop.install(gui_exe, data, update=False)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    except OSError as e:
        print(_("labelwerk was not added ({reason}).").format(reason=os_reason(e)),
              file=sys.stderr)
        return 2
    for path in paths:
        print(_("Installed: {path}").format(path=path))
    _report_update(desktop.update_databases(data))
    print(_("labelwerk now appears in the launcher (wait a moment or log in again if needed); "
            "double-clicking a .labelwerk file opens it."))
    return 0


def _report_update(failed: list[str]) -> None:
    if failed:
        print(_("Note: {tools} did not work – the file association may only apply after logging "
                "in again.").format(tools=", ".join(failed)), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    i18n.set_language(_language(argv))
    _translate_argparse()
    args = _parser().parse_args(argv)
    settings = load_settings()
    args.settings = settings
    args.target = _target(args, settings)
    try:
        args.model = _resolve_model(args.model, args.target, settings)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2

    if args.cmd == "labels":
        for lbl in labels_for_model(args.model):
            size = f"{lbl.width}x{lbl.height}" if lbl.height else f"{lbl.width}"
            print(f"{lbl.id:<10} {size:<10} {lbl.description}")
        return 0

    if args.cmd == "install-desktop":
        return _install_desktop(args.remove)
    if args.cmd == "media":
        return _show_media(args.model, args.target)
    if args.cmd == "printers":
        return _show_printers(args.model, args.show_all)
    if args.cmd == "fonts":
        print("\n".join(families(all=args.all)))
        return 0

    if args.cmd == "print" and args.font and args.font_family:
        print(_("--font (font file) and --font-family exclude each other."), file=sys.stderr)
        return 2
    try:
        _apply_settings(args)
    except (ValueError, MediaError) as e:            # -l auto: kein Drucker, keine Rolle
        print(e, file=sys.stderr)
        return 2

    try:
        img = _make_image(args)
    except (ValueError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        return 2

    if args.preview:
        try:
            img.save(args.preview)
        except (OSError, ValueError) as e:
            print(_("Preview cannot be saved: {path} ({error})").format(path=args.preview, error=e),
                  file=sys.stderr)
            return 2
        dpi = get_label(args.label).dpi
        print(_("Preview: {path} ({width} × {height} mm)").format(
            path=args.preview, width=format_mm(img.width, dpi), height=format_mm(img.height, dpi)))
        return 0

    return _send(img, args)


if __name__ == "__main__":
    sys.exit(main())
