"""Kommandozeile: labelwerk labels | print "Text" | print-file datei.pdf | media | printers | fonts |
install-desktop"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from . import desktop
from . import printer as prn
from . import printers
from .detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp, find_brother_usb
from .files import crop, fit_to_label, load_file
from .fonts import DEFAULT_FAMILY, families
from .document import ALIGNMENTS, MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
from .labels import format_mm, get_label, labels_for_model
from .media import MediaError, label_for_media, read_media
from .render import font_warnings, render_document
from .settings import load_settings, network_entries
from .storage import os_reason


def _font_size(value: str) -> float | None:
    """'auto' (= None) oder Größe in pt, 4–100."""
    if value.lower() == "auto":
        return None
    try:
        size = float(value.replace(",", "."))
    except ValueError:
        size = 0.0
    if not MIN_PT <= size <= MAX_PT:
        raise argparse.ArgumentTypeError("Schriftgröße: 'auto' oder 4–100 (pt)")
    return size


def _margin(value: str) -> float:
    try:
        mm = float(value)
    except ValueError:
        mm = float("nan")
    if not 0 <= mm <= MAX_MARGIN_MM:      # nan fällt hier ebenfalls durch
        raise argparse.ArgumentTypeError(f"Rand: Zahl von 0 bis {MAX_MARGIN_MM:g} mm")
    return mm


def _add_output_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-l", "--label", help="Etikett, z. B. 62, oder auto (eingelegte Rolle vom "
                                         "Drucker); Standard aus den Einstellungen")
    p.add_argument("-p", "--printer", default="auto",
                   help="auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP")
    p.add_argument("-b", "--backend", choices=["linux_kernel", "pyusb", "network"],
                   help="Standard: aus dem Drucker (tcp:// → network)")
    p.add_argument("--no-cut", action="store_true")
    p.add_argument("--preview", metavar="PNG", help="nur Vorschau speichern, nicht drucken")


_UNSET = object()   # -s nicht angegeben (None bedeutet „auto“)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=desktop.APP_NAME)
    p.add_argument("-m", "--model", default="auto",
                   help="auto (Standard: erkannt, sonst aus den Einstellungen) oder z. B. QL-700; "
                        "siehe 'labelwerk printers'")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("labels", help="Etiketten für das Modell auflisten")

    pr = sub.add_parser("print", help="Text drucken")
    pr.add_argument("text", help="Text, Zeilenumbruch mit \\n")
    pr.add_argument("-s", "--font-size", type=_font_size, default=_UNSET, metavar="PT",
                    help="'auto' oder 4–100 pt (Standard aus den Einstellungen)")
    pr.add_argument("--font", help="Pfad zu einer .ttf-Datei")
    pr.add_argument("--font-family", metavar="NAME",
                    help="Schriftfamilie, z. B. 'Liberation Sans' (siehe 'labelwerk fonts')")
    pr.add_argument("--align", choices=ALIGNMENTS, default="center",
                    help="Textposition: left, center (Standard), right, justify")
    pr.add_argument("--bold", action=argparse.BooleanOptionalAction, default=True,
                    help="fett (Standard) bzw. --no-bold")
    pr.add_argument("--italic", action="store_true", help="kursiv")
    pr.add_argument("--underline", action="store_true", help="unterstrichen")
    pr.add_argument("--orientation", choices=ORIENTATIONS,
                    help="vertical: Hochformat (Leserichtung quer zum Band), horizontal: Querformat (längs zum Band); Standard aus den Einstellungen")
    pr.add_argument("--margin", type=_margin, metavar="MM",
                    help="Rand ringsum ab Papierkante in mm (Standard aus den Einstellungen)")
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
    sub.add_parser("printers", help="gefundene Drucker und unterstützte Modelle auflisten")
    sub.add_parser("fonts", help="installierte Schriftfamilien auflisten")

    di = sub.add_parser("install-desktop", help="labelwerk-gui im Starter (Super-Taste) eintragen")
    di.add_argument("--remove", action="store_true", help="Eintrag und Icon wieder entfernen")
    return p


_HARDWARE_HINT = "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb'"
_NOT_DETECTED = {
    "linux_kernel": f"{PRINTER_NOT_FOUND}\nManuell angeben mit -p file:///dev/usb/lpN",
    "pyusb": "Brother-Drucker per USB (pyusb) nicht gefunden.\n"
             f"{_HARDWARE_HINT}, Zugriff auf den USB-Bus (udev-Regel).\n"
             "Manuell angeben mit -p usb://0x04f9:0xPID",
    "network": "Kein Netzwerkdrucker eingetragen (Einstellungen der GUI).\n"
               "Adresse angeben mit -p tcp://IP",
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
    found = _all_printers(settings)
    if wanted != "auto":
        return printers.printer_for(wanted, found)
    if backend == "network":
        found = [p for p in found if p.source == "network"]
    elif backend == "linux_kernel":
        found = [p for p in found if p.source == "usb"]
    return printers.choose(found, settings.printer)


def _all_printers(settings) -> list[printers.Printer]:
    return printers.usb_printers() + printers.network_printers(network_entries(settings))


def _resolve_model(model: str, target: printers.Printer | None, settings) -> str:
    """``-m auto``: Modell des Zieldruckers, sonst Ersatzmodell bzw. zuletzt erkanntes aus den
    Einstellungen; ein angegebenes muss bekannt sein."""
    if model != "auto":
        if model not in printers.SUPPORTED_MODELS:
            raise ValueError(f"Unbekanntes Druckermodell {model!r} – erlaubt: "
                             f"{', '.join(printers.SUPPORTED_MODELS)}")
        return model
    return printers.effective_model(target, settings.printer_model, settings.last_model)


def _auto_label(model: str, target: printers.Printer | None) -> str:
    """``-l auto``: Etikett zur eingelegten Rolle (Statusabfrage per USB beim Zieldrucker) – sonst
    ValueError."""
    if target is not None and target.source != "usb":
        raise ValueError("-l auto (Rolle abfragen) geht nur bei Druckern per USB.")
    printer = target.uri if target is not None and target.uri.startswith("file://") \
        else find_brother_lp()
    if printer is None:
        raise ValueError(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND)
    media = read_media(printer)
    if media.kind == "none":
        raise ValueError("Keine Rolle eingelegt.")
    label = label_for_media(media, model)
    if label is None:
        raise ValueError(f"Kein Etikett für die eingelegte Rolle ({media.describe()}) beim {model}.")
    return label


def _make_image(args: argparse.Namespace) -> Image.Image:
    if args.cmd == "print-file":
        img = crop(load_file(args.file, page=args.page))
        rotate = args.rotate if args.rotate == "auto" else int(args.rotate)
        return fit_to_label(img, args.label, fit=args.fit, model=args.model, rotate=rotate)
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
        if args.printer is None:
            busy = args.backend in (None, "linux_kernel") and brother_busy()
            print(BUSY_MESSAGE if busy else _NOT_DETECTED[args.backend or "linux_kernel"],
                  file=sys.stderr)
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


def _show_printers(model: str) -> int:
    """Gefundene Drucker (USB, eingetragene Netzwerkdrucker) und unterstützte Modelle."""
    found = _all_printers(load_settings())
    for p in found:
        caps = printers.capabilities(p.model) if p.model else None
        state = ("Modell nicht erkannt" if caps is None else
                 "geprüft" if caps.tested else printers.UNTESTED_HINT)
        print(f"{p.name:<28} {p.uri:<30} {state}")
    if not found:
        print("Kein Drucker gefunden.")
    print(f"Wirksames Modell: {model}")
    print("Unterstützt: " + ", ".join(
        f"{m}{'' if printers.capabilities(m).tested else ' (ungeprüft)'}"
        for m in printers.SUPPORTED_MODELS))
    return 0


def _show_media(model: str) -> int:
    printer = find_brother_lp()
    if printer is None:
        print(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND, file=sys.stderr)
        return 2
    try:
        media = read_media(printer)
    except MediaError as e:
        print(e, file=sys.stderr)
        return 2
    label = label_for_media(media, model)
    hint = f" (Etikett {label})" if label else " (kein passendes Etikett)" if media.kind != "none" else ""
    print(f"Eingelegt: {media.describe()}{hint}")
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
        raise ValueError(f"Etikett {args.label!r} passt nicht zum {args.model} – siehe "
                         f"'labelwerk -m {args.model} labels'")
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
            print(f"labelwerk wurde nicht entfernt ({os_reason(e)}).", file=sys.stderr)
            return 2
        print("\n".join(f"Entfernt: {p}" for p in removed) or "Nichts zu entfernen.")
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
        print(f"labelwerk wurde nicht eingetragen ({os_reason(e)}).", file=sys.stderr)
        return 2
    for path in paths:
        print(f"Installiert: {path}")
    _report_update(desktop.update_databases(data))
    print("labelwerk erscheint jetzt im Starter (ggf. kurz warten oder neu anmelden); "
          "Doppelklick auf eine .labelwerk-Datei öffnet sie.")
    return 0


def _report_update(failed: list[str]) -> None:
    if failed:
        print(f"Hinweis: {', '.join(failed)} hat nicht geklappt – Dateizuordnung gilt ggf. erst "
              f"nach neuer Anmeldung.", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = load_settings()
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
        return _show_media(args.model)
    if args.cmd == "printers":
        return _show_printers(args.model)
    if args.cmd == "fonts":
        print("\n".join(families()))
        return 0

    if args.cmd == "print" and args.font and args.font_family:
        print("--font (Schriftdatei) und --font-family schließen sich aus.", file=sys.stderr)
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
            print(f"Vorschau kann nicht gespeichert werden: {args.preview} ({e})", file=sys.stderr)
            return 2
        print(f"Vorschau: {args.preview} ({format_mm(img.width)} × {format_mm(img.height)} mm)")
        return 0

    return _send(img, args)


if __name__ == "__main__":
    sys.exit(main())
