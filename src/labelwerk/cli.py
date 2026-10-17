"""Kommandozeile: labelwerk labels | labelwerk print "Text" -l 62"""
from __future__ import annotations

import argparse
import sys

from . import printer as prn
from .labels import labels_for_model
from .render import render_text


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="labelwerk")
    p.add_argument("-m", "--model", default=prn.DEFAULT_MODEL)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("labels", help="Etiketten für das Modell auflisten")

    pr = sub.add_parser("print", help="Text drucken")
    pr.add_argument("text", help="Text, Zeilenumbruch mit \\n")
    pr.add_argument("-l", "--label", default="62")
    pr.add_argument("-s", "--font-size", type=int)
    pr.add_argument("--font", help="Pfad zu einer .ttf-Datei")
    pr.add_argument("-p", "--printer", default=prn.DEFAULT_PRINTER)
    pr.add_argument("-b", "--backend", default=prn.DEFAULT_BACKEND,
                    choices=["linux_kernel", "pyusb", "network"])
    pr.add_argument("--no-cut", action="store_true")
    pr.add_argument("--preview", metavar="PNG", help="nur Vorschau speichern, nicht drucken")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.cmd == "labels":
        for lbl in labels_for_model(args.model):
            size = f"{lbl.width}x{lbl.height}" if lbl.height else f"{lbl.width}"
            print(f"{lbl.id:<10} {size:<10} {lbl.description}")
        return 0

    text = args.text.replace("\\n", "\n")
    img = render_text(text, args.label, font_size=args.font_size, font_path=args.font)

    if args.preview:
        img.save(args.preview)
        print(f"Vorschau: {args.preview} ({img.width}x{img.height} px)")
        return 0

    status = prn.print_image(img, args.label, model=args.model, printer=args.printer,
                             backend=args.backend, cut=not args.no_cut)
    ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
    print(f"Status: {status.get('outcome')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
