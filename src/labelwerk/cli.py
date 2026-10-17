"""Kommandozeile: labelwerk labels | print "Text" -l 62 | print-file datei.pdf -l 62"""
from __future__ import annotations

import argparse
import sys

from PIL import Image

from . import printer as prn
from .detect import find_brother_lp, find_brother_usb
from .files import crop, fit_to_label, load_file
from .labels import format_mm, labels_for_model
from .render import render_text


def _add_output_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-l", "--label", default="62")
    p.add_argument("-p", "--printer", default="auto",
                   help="auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP")
    p.add_argument("-b", "--backend", default=prn.DEFAULT_BACKEND,
                   choices=["linux_kernel", "pyusb", "network"])
    p.add_argument("--no-cut", action="store_true")
    p.add_argument("--preview", metavar="PNG", help="nur Vorschau speichern, nicht drucken")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="labelwerk")
    p.add_argument("-m", "--model", default=prn.DEFAULT_MODEL)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("labels", help="Etiketten für das Modell auflisten")

    pr = sub.add_parser("print", help="Text drucken")
    pr.add_argument("text", help="Text, Zeilenumbruch mit \\n")
    pr.add_argument("-s", "--font-size", type=int)
    pr.add_argument("--font", help="Pfad zu einer .ttf-Datei")
    _add_output_options(pr)

    pf = sub.add_parser("print-file", help="PDF/Bild 1:1 drucken")
    pf.add_argument("file", help="PDF, PNG oder JPG")
    pf.add_argument("--page", type=int, default=1, help="PDF-Seite (Standard 1)")
    pf.add_argument("--fit", action="store_true",
                    help="verkleinern, falls zu groß (Codes evtl. nicht mehr lesbar)")
    _add_output_options(pf)
    return p


_HARDWARE_HINT = "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb'"
_NOT_DETECTED = {
    "linux_kernel": "Brother-Drucker unter /dev/usb/lp* nicht gefunden.\n"
                    f"{_HARDWARE_HINT}, 'lsmod | grep usblp'.\n"
                    "Manuell angeben mit -p file:///dev/usb/lpN",
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
        return fit_to_label(img, args.label, fit=args.fit, model=args.model)
    text = args.text.replace("\\n", "\n")
    return render_text(text, args.label, font_size=args.font_size, font_path=args.font)


def _send(img: Image.Image, args: argparse.Namespace) -> int:
    if args.printer == "auto":
        args.printer = _detect_printer(args.backend)
        if args.printer is None:
            print(_NOT_DETECTED[args.backend], file=sys.stderr)
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.cmd == "labels":
        for lbl in labels_for_model(args.model):
            size = f"{lbl.width}x{lbl.height}" if lbl.height else f"{lbl.width}"
            print(f"{lbl.id:<10} {size:<10} {lbl.description}")
        return 0

    try:
        img = _make_image(args)
    except (ValueError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        return 2

    if args.preview:
        img.save(args.preview)
        print(f"Vorschau: {args.preview} ({format_mm(img.width)} × {format_mm(img.height)} mm)")
        return 0

    return _send(img, args)


if __name__ == "__main__":
    sys.exit(main())
