"""Referenz-Rasterdaten je Druckermodell (tests/golden/raster.json) prüfen bzw. neu erzeugen.

    python tools/golden.py            # vergleichen (wie der Test)
    python tools/golden.py --update   # nach einer gewollten Änderung neu schreiben

Je Modell ein festes Testetikett (nur Formen, keine Schrift – Schriftversionen dürfen nicht
zählen) als SHA-256 der Rasterdaten: Endlos 62 mm mit und ohne Schnitt, gestanzt 62×29, bei
breiten Modellen 102 mm, bei Zweifarb-Modellen 62red. Beweist, was gesendet wird – nicht, was
gedruckt wird. Die Werte hängen an brother_ql (pyproject: auf 1.3.x festgelegt) – nach einem
Update der Bibliothek prüfen und neu erzeugen.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from labelwerk.labels import get_label, labels_for_model
from labelwerk.printer import build_instructions
from labelwerk.printers import SUPPORTED_MODELS

GOLDEN = Path(__file__).resolve().parent.parent / "tests" / "golden" / "raster.json"


def test_image(label_id: str, length: int = 200) -> Image.Image:
    """Rahmen, Schachbrett (und bei 62red ein rotes Feld) über die ganze Breite – nur achsparallele
    Rechtecke, damit keine Zeichenroutine von Pillow mitzählt."""
    label = get_label(label_id)
    size = (label.width, label.height or length)
    img = Image.new("RGB", size, "white")
    pen = ImageDraw.Draw(img)
    pen.rectangle((0, 0, size[0] - 1, size[1] - 1), outline="black", width=3)
    for y in range(10, size[1] - 10, 20):
        for x in range(10 + (y // 20) % 2 * 10, size[0] // 2, 20):
            pen.rectangle((x, y, x + 9, y + 9), fill="black")
    if label.two_color:
        pen.rectangle((size[0] // 2 + 10, 10, size[0] - 10, size[1] // 2), fill=(255, 0, 0))
    return img


def cases(model: str) -> dict[str, bytes]:
    available = {label.id for label in labels_for_model(model)}
    out = {"62": build_instructions(test_image("62"), "62", model),
           "62-ohne-schnitt": build_instructions(test_image("62"), "62", model, cut=False),
           "62x29": build_instructions(test_image("62x29"), "62x29", model),
           "62-serie": build_instructions([test_image("62")] * 3, "62", model, cut_every=3)}
    if "102" in available:
        out["102"] = build_instructions(test_image("102"), "102", model)
    if "62red" in available:
        out["62red"] = build_instructions(test_image("62red"), "62red", model)
    return out


def digests() -> dict[str, dict[str, str]]:
    return {model: {name: hashlib.sha256(data).hexdigest() for name, data in cases(model).items()}
            for model in SUPPORTED_MODELS}


def main(argv: list[str]) -> int:
    current = digests()
    if "--update" in argv:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
        print(f"geschrieben: {GOLDEN}")
        return 0
    stored = json.loads(GOLDEN.read_text())
    changed = [m for m in sorted(set(current) | set(stored)) if current.get(m) != stored.get(m)]
    print("unverändert" if not changed else "geändert: " + ", ".join(changed))
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
