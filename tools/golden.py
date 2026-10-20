"""Check or regenerate the reference raster data per printer model (tests/golden/raster.json).

    python tools/golden.py            # compare (like the test)
    python tools/golden.py --update   # rewrite after an intended change

One fixed test label per model (shapes only, no text – font versions must not count) as SHA-256
of the raster data: continuous 62 mm with and without cut, die-cut 62×29, 102 mm for wide
models, 62red for two-colour models; Zebra (ZPL) per resolution 57×32 mm, 102×152 mm with
cutting and a series. Proves what is sent – not what is printed. The values depend on
brother_ql (pyproject: pinned to 1.3.x) – check and regenerate after a library update.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from labelwerk import zpl
from labelwerk.labels import get_label, labels_for_model, sized_id
from labelwerk.printer import build_instructions
from labelwerk.printers import SUPPORTED_MODELS

ZPL_MODELS = tuple(zpl.model_for(dpi) for dpi in zpl.RESOLUTIONS)
MODELS = SUPPORTED_MODELS + ZPL_MODELS

GOLDEN = Path(__file__).resolve().parent.parent / "tests" / "golden" / "raster.json"


def test_image(label_id: str, length: int = 200) -> Image.Image:
    """Frame, checkerboard (and a red field for 62red) across the whole width – only axis-parallel
    rectangles, so that no Pillow drawing routine counts."""
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
    if zpl.is_model(model):
        small, large = (sized_id(w, h, zpl.dpi_of(model)) for w, h in ((57, 32), (102, 152)))
        return {"57x32": zpl.build([test_image(small)]),
                "102x152-schneiden": zpl.build([test_image(large)], "C"),
                "57x32-serie": zpl.build([test_image(small)] * 3)}
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
            for model in MODELS}


def main(argv: list[str]) -> int:
    current = digests()
    if "--update" in argv:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
        print(f"written: {GOLDEN}")
        return 0
    stored = json.loads(GOLDEN.read_text())
    changed = [m for m in sorted(set(current) | set(stored)) if current.get(m) != stored.get(m)]
    print("unchanged" if not changed else "changed: " + ", ".join(changed))
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
