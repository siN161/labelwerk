# PDF/Bild direkt drucken – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `labelwerk print-file DATEI` druckt PDF/PNG/JPG 1:1 auf ein Brother-QL-Etikett (z. B. Internetmarke auf 62-mm-Endlosband).

**Architecture:** Neues Kernmodul `src/labelwerk/files.py` (ohne Qt): `load_file` → `crop` → `fit_to_label` liefert ein Bild im Format, das `printer.build_instructions` erwartet. Die CLI bekommt einen Unterbefehl `print-file`; Druckerwahl und Fehlerbehandlung werden mit `print` geteilt.

**Tech Stack:** Python ≥ 3.10, Pillow, brother_ql-inventree, pypdfium2 (neu), pytest.

Spec: `docs/superpowers/specs/2026-10-17-print-file-design.md`

## Global Constraints

- Alle Bilder intern bei **300 dpi**, Graustufen (`"L"`).
- **1:1** – nie vergrößern; verkleinern nur mit `fit=True` / `--fit`.
- `pypdfium2>=4` als feste Abhängigkeit (BSD-3/Apache-2.0).
- Benutzer-Meldungen und Kommentare **auf Deutsch**; Dezimalkomma in mm-Angaben (`58,9`).
- Fehler für Nutzer: `ValueError`/`FileNotFoundError` mit verständlicher Meldung; CLI → stderr, Exit-Code 2, kein Traceback.
- **Tests ohne Hardware** und **ohne echte Briefmarken/Adressen** – nur künstlich erzeugte Dateien in `tmp_path`.
- Tests ausführen mit `.venv/bin/python -m pytest -q` im Repo-Wurzelverzeichnis.
- Commit-Nachrichten auf Deutsch, enden mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Dateien

| Datei | Änderung |
|---|---|
| `pyproject.toml` | Abhängigkeit `pypdfium2>=4` |
| `src/labelwerk/labels.py` | `DPI`, `format_mm(dots)`, `length_limits(model)` |
| `src/labelwerk/files.py` | neu: `load_file`, `crop`, `fit_to_label` |
| `src/labelwerk/cli.py` | Unterbefehl `print-file`, gemeinsame Optionen/Druckpfad, mm in Vorschau-Ausgabe |
| `tests/test_files.py` | neu |
| `tests/test_labels.py`, `tests/test_cli.py` | erweitert |
| `README.md`, `CLAUDE.md` | Doku |

---

### Task 1: `load_file` – PDF und Bilder bei 300 dpi laden

**Files:**
- Modify: `pyproject.toml` (dependencies)
- Modify: `src/labelwerk/labels.py` (Konstante `DPI`)
- Create: `src/labelwerk/files.py`
- Create: `tests/test_files.py`

**Interfaces:**
- Produces: `labelwerk.labels.DPI = 300`; `labelwerk.files.load_file(path: str | Path, page: int = 1) -> PIL.Image.Image` (Modus `"L"`, 300 dpi). Fehler: `ValueError` (Dateityp, Seite), `FileNotFoundError`.

- [ ] **Step 1: Abhängigkeit eintragen und installieren**

In `pyproject.toml` die Liste `dependencies` ändern zu:

```toml
dependencies = [
    "brother_ql-inventree>=1.3",
    "pillow>=10",
    "pypdfium2>=4",
]
```

Run: `.venv/bin/pip install -q -e ".[dev]"`
Expected: ohne Fehler; `.venv/bin/python -c "import pypdfium2"` läuft durch.

- [ ] **Step 2: Failing tests schreiben**

`tests/test_files.py`:

```python
import pytest
from PIL import Image

from labelwerk.files import load_file


def _page(w=600, h=300):
    img = Image.new("L", (w, h), 255)
    img.paste(0, (100, 100, 200, 200))
    return img


def test_pdf_is_rendered_at_300_dpi(tmp_path):
    path = tmp_path / "seite.pdf"
    _page().save(path, "PDF", resolution=300)
    img = load_file(path)
    assert img.mode == "L"
    assert abs(img.width - 600) <= 1 and abs(img.height - 300) <= 1


def test_pdf_page_out_of_range(tmp_path):
    path = tmp_path / "seite.pdf"
    _page().save(path, "PDF", resolution=300)
    with pytest.raises(ValueError, match="nur 1 Seite"):
        load_file(path, page=2)


def test_png_with_600_dpi_keeps_size_in_mm(tmp_path):
    path = tmp_path / "bild.png"
    _page().save(path, dpi=(600, 600))
    assert load_file(path).size == (300, 150)


def test_png_without_dpi_counts_as_300_dpi(tmp_path):
    path = tmp_path / "bild.png"
    _page().save(path)
    assert load_file(path).size == (600, 300)


def test_transparency_becomes_white(tmp_path):
    path = tmp_path / "leer.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(path)
    assert load_file(path).getextrema() == (255, 255)


def test_unsupported_file_type(tmp_path):
    with pytest.raises(ValueError, match="nicht unterstützt"):
        load_file(tmp_path / "notiz.txt")


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="nicht gefunden"):
        load_file(tmp_path / "fehlt.pdf")
```

- [ ] **Step 3: Tests laufen lassen – müssen fehlschlagen**

Run: `.venv/bin/python -m pytest -q tests/test_files.py`
Expected: Collection-Fehler `ModuleNotFoundError: No module named 'labelwerk.files'`

- [ ] **Step 4: Implementierung**

In `src/labelwerk/labels.py` direkt unter `TWO_COLOR_MODELS = {...}` einfügen:

```python
DPI = 300  # Druckauflösung der QL-Drucker
```

`src/labelwerk/files.py`:

```python
"""Lädt fertige Dateien (PDF, PNG, JPG) und bringt sie 1:1 aufs Etikett."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .labels import DPI

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


def load_file(path: str | Path, page: int = 1) -> Image.Image:
    """Datei als Graustufenbild bei 300 dpi (Größe in mm bleibt erhalten)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix != ".pdf" and suffix not in _IMAGE_SUFFIXES:
        raise ValueError(f"Dateityp nicht unterstützt: {suffix or path.name} – möglich: PDF, PNG, JPG")
    if not path.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {path}")
    return _load_pdf(path, page) if suffix == ".pdf" else _load_image(path)


def _load_pdf(path: Path, page: int) -> Image.Image:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(path)
    try:
        if not 1 <= page <= len(pdf):
            raise ValueError(f"PDF hat nur {len(pdf)} Seite(n).")
        return pdf[page - 1].render(scale=DPI / 72).to_pil().convert("L")
    finally:
        pdf.close()


def _load_image(path: Path) -> Image.Image:
    with Image.open(path) as src:
        dpi = float(src.info.get("dpi", (DPI, DPI))[0]) or DPI
        img = src.convert("RGBA")
    img = Image.alpha_composite(Image.new("RGBA", img.size, "white"), img).convert("L")
    if round(dpi) != DPI:
        f = DPI / dpi
        img = img.resize((max(1, round(img.width * f)), max(1, round(img.height * f))),
                         Image.LANCZOS)
    return img
```

- [ ] **Step 5: Tests laufen lassen – müssen bestehen**

Run: `.venv/bin/python -m pytest -q`
Expected: alle grün (33 bisherige + 7 neue = 40 passed)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/labelwerk/labels.py src/labelwerk/files.py tests/test_files.py
git commit -m "print-file: PDF/PNG/JPG bei 300 dpi laden

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `crop` – auf Schnittmarken bzw. Inhalt zuschneiden

**Files:**
- Modify: `src/labelwerk/files.py`
- Modify: `tests/test_files.py`

**Interfaces:**
- Consumes: `labelwerk.labels.DPI`
- Produces: `labelwerk.files.crop(img: Image.Image) -> Image.Image`; Konstanten `files.INK = 128`, `files.MM = DPI / 25.4`. Leeres Bild → `ValueError("Datei enthält keinen druckbaren Inhalt.")`.

Erkennungsregel (aus der Spec): In jeder Ecke des bedruckten Bereichs (Fenster 10 × 10 mm) gibt es Zeilen, die am Rand des bedruckten Bereichs beginnen und auf den ersten 3 mm zu ≥ 40 % dunkel sind, und ebensolche Spalten; beide Gruppen ≤ 1 mm dick. Die anderen drei Ecken werden durch Spiegeln/Drehen auf „oben links“ zurückgeführt. Zuschnitt an der Innenkante + 1 Pixel.

- [ ] **Step 1: Failing tests schreiben**

In `tests/test_files.py` den Import ändern zu `from labelwerk.files import crop, load_file` und anhängen:

```python
from PIL import ImageDraw

RECT = (100, 80, 1163, 635)   # Kreuzungspunkte der Marken (90 × 47 mm)


def _with_marks(corners=("tl", "tr", "bl", "br"), dotted=False):
    img = Image.new("L", (1300, 750), 255)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = RECT
    points = {"tl": (x0, y0), "tr": (x1, y0), "bl": (x0, y1), "br": (x1, y1)}
    for name in corners:
        x, y = points[name]
        for i in range(-30, 31):
            if dotted and i % 4 >= 2:
                continue
            d.point((x + i, y), 0)
            d.point((x, y + i), 0)
    d.rectangle((300, 300, 700, 400), fill=0)   # Inhalt
    return img


def test_crop_to_solid_marks():
    w, h = crop(_with_marks()).size
    assert abs(w - (RECT[2] - RECT[0])) <= 4
    assert abs(h - (RECT[3] - RECT[1])) <= 4


def test_crop_to_dotted_marks():
    w, h = crop(_with_marks(dotted=True)).size
    assert abs(w - (RECT[2] - RECT[0])) <= 4
    assert abs(h - (RECT[3] - RECT[1])) <= 4


def test_crop_removes_marks_completely():
    cropped = crop(_with_marks())
    border = [cropped.crop(b) for b in ((0, 0, cropped.width, 1), (0, 0, 1, cropped.height))]
    assert all(b.getextrema()[0] == 255 for b in border)


def test_without_all_four_marks_crops_to_content():
    img = _with_marks(corners=("tl", "tr", "bl"))
    bbox = img.point(lambda v: 255 if v < 128 else 0).getbbox()
    assert crop(img).size == (bbox[2] - bbox[0], bbox[3] - bbox[1])


def test_logo_in_corner_is_not_a_mark():
    img = Image.new("L", (800, 500), 255)
    d = ImageDraw.Draw(img)
    for x, y in ((50, 50), (650, 50), (50, 350), (650, 350)):
        d.rectangle((x, y, x + 99, y + 99), fill=0)   # dicke Blöcke in allen Ecken
    assert crop(img).size == (700, 400)


def test_crop_empty_page():
    with pytest.raises(ValueError, match="keinen druckbaren Inhalt"):
        crop(Image.new("L", (100, 100), 255))
```

- [ ] **Step 2: Tests laufen lassen – müssen fehlschlagen**

Run: `.venv/bin/python -m pytest -q tests/test_files.py`
Expected: `ImportError: cannot import name 'crop'`

- [ ] **Step 3: Implementierung**

In `src/labelwerk/files.py` den PIL-Import ändern zu `from PIL import Image, ImageOps`, unter `_IMAGE_SUFFIXES` ergänzen:

```python
INK = 128            # dunkler gilt als bedruckt
MM = DPI / 25.4      # Punkte pro mm
```

und am Dateiende anfügen:

```python
def crop(img: Image.Image) -> Image.Image:
    """Auf den Bereich zwischen vier Eck-Schnittmarken zuschneiden, sonst auf den Inhalt."""
    ink = img.point(lambda v: 255 if v < INK else 0)
    box = ink.getbbox()
    if box is None:
        raise ValueError("Datei enthält keinen druckbaren Inhalt.")
    content = ink.crop(box)
    tl = _corner_mark(content)
    tr = _corner_mark(ImageOps.mirror(content))
    bl = _corner_mark(ImageOps.flip(content))
    br = _corner_mark(content.rotate(180))
    if None in (tl, tr, bl, br):
        return img.crop(box)
    w, h = content.size
    left, top = max(tl[0], bl[0]), max(tl[1], tr[1])
    right, bottom = w - max(tr[0], br[0]), h - max(bl[1], br[1])
    return img.crop((box[0] + left, box[1] + top, box[0] + right, box[1] + bottom))


def _corner_mark(ink: Image.Image) -> tuple[int, int] | None:
    """Innenkante (x, y) eines Schnittmarken-Kreuzes in der Ecke oben links, sonst None.

    Linien müssen am Rand des Inhalts beginnen, auf den ersten 3 mm zu 40 % dunkel
    (auch gepunktet) und höchstens 1 mm dick sein – so gilt Text oder ein Logo nicht als Marke.
    """
    span, window = round(3 * MM), round(10 * MM)
    w, h = ink.size
    px = ink.load()
    need = 0.4 * span
    rows = [y for y in range(min(window, h))
            if sum(px[x, y] > 0 for x in range(min(span, w))) >= need]
    cols = [x for x in range(min(window, w))
            if sum(px[x, y] > 0 for y in range(min(span, h))) >= need]
    if not rows or not cols or rows[-1] - rows[0] > MM or cols[-1] - cols[0] > MM:
        return None
    return cols[-1] + 2, rows[-1] + 2
```

- [ ] **Step 4: Tests laufen lassen – müssen bestehen**

Run: `.venv/bin/python -m pytest -q`
Expected: alle grün (46 passed)

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/files.py tests/test_files.py
git commit -m "print-file: Zuschnitt auf Schnittmarken oder Inhalt

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `fit_to_label` – 1:1 aufs Etikett setzen, bei Bedarf drehen

**Files:**
- Modify: `src/labelwerk/labels.py`
- Modify: `src/labelwerk/files.py`
- Modify: `tests/test_labels.py`, `tests/test_files.py`

**Interfaces:**
- Consumes: `labels.get_label(label_id) -> Label` (`.width`, `.height` = bedruckbare Punkte, `height is None` bei Endlos), `render.MARGIN = 12`, `files.MM`
- Produces:
  - `labels.format_mm(dots: int) -> str` – z. B. `format_mm(696) == "58,9"`
  - `labels.length_limits(model: str) -> tuple[int, int]` – z. B. `(150, 11811)` für `"QL-600"`; unbekannt → `ValueError`
  - `files.fit_to_label(img, label_id: str, fit: bool = False, model: str = "QL-600") -> Image.Image` – Breite = `label.width`; Endlos: Höhe = Motiv + 2 × `MARGIN`, begrenzt auf `length_limits`; gestanzt: exakt `label.width × label.height`.

- [ ] **Step 1: Failing tests schreiben**

An `tests/test_labels.py` anhängen (Import oben ergänzen um `format_mm, length_limits`):

```python
def test_format_mm_uses_decimal_comma():
    assert format_mm(696) == "58,9"


def test_length_limits_for_ql600():
    assert length_limits("QL-600") == (150, 11811)
```

In `tests/test_files.py` den Import ändern zu `from labelwerk.files import crop, fit_to_label, load_file` und anhängen:

```python
def _motif(w_mm, h_mm):
    img = Image.new("L", (round(w_mm * 300 / 25.4), round(h_mm * 300 / 25.4)), 0)
    return img


def test_wide_motif_is_rotated_onto_endless_tape():
    out = fit_to_label(_motif(90, 47), "62")
    assert out.size == (696, 1063 + 2 * 12)


def test_small_motif_is_not_rotated():
    out = fit_to_label(_motif(40, 20), "62")
    assert out.size == (696, 236 + 2 * 12)


def test_motif_is_centered_and_not_scaled():
    out = fit_to_label(_motif(40, 20), "62")
    bbox = out.point(lambda v: 255 if v < 128 else 0).getbbox()
    assert (bbox[2] - bbox[0], bbox[3] - bbox[1]) == (472, 236)
    assert bbox[0] == (696 - 472) // 2


def test_short_motif_gets_minimum_length():
    assert fit_to_label(_motif(40, 2), "62").height == 150


def test_too_large_motif_raises_with_mm():
    with pytest.raises(ValueError, match=r"120,0 × 70,0 mm.*--fit"):
        fit_to_label(_motif(120, 70), "62")


def test_fit_shrinks_and_keeps_aspect_ratio():
    out = fit_to_label(_motif(120, 70), "62", fit=True)
    bbox = out.point(lambda v: 255 if v < 128 else 0).getbbox()
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    assert out.width == 696 and w == 696
    assert abs(h / w - 120 / 70) < 0.01          # gedreht, da so größer


def test_die_cut_label_has_exact_size():
    assert fit_to_label(_motif(40, 20), "62x29").size == (696, 271)


def test_result_is_accepted_by_printer_driver():
    from labelwerk.printer import build_instructions
    data = build_instructions(fit_to_label(_motif(90, 47), "62"), "62")
    assert data.endswith(b"\x1a")
```

- [ ] **Step 2: Tests laufen lassen – müssen fehlschlagen**

Run: `.venv/bin/python -m pytest -q tests/test_labels.py tests/test_files.py`
Expected: `ImportError: cannot import name 'format_mm'` bzw. `'fit_to_label'`

- [ ] **Step 3: Implementierung**

In `src/labelwerk/labels.py` den Import ergänzen:

```python
from brother_ql.models import ModelsManager
```

und am Dateiende anfügen:

```python
def format_mm(dots: int) -> str:
    """Punkte (300 dpi) als mm-Angabe mit Dezimalkomma, z. B. "58,9"."""
    return f"{dots * 25.4 / DPI:.1f}".replace(".", ",")


def length_limits(model: str) -> tuple[int, int]:
    """Erlaubte Etikettlänge (Endlosband) in Punkten, z. B. (150, 11811) für den QL-600."""
    for m in ModelsManager().iter_elements():
        if m.identifier == model:
            return m.min_max_length_dots
    raise ValueError(f"Unbekanntes Druckermodell: {model!r}")
```

In `src/labelwerk/files.py` die Imports ändern zu:

```python
from .labels import DPI, format_mm, get_label, length_limits
from .render import MARGIN
```

und am Dateiende anfügen:

```python
def fit_to_label(img: Image.Image, label_id: str, fit: bool = False,
                 model: str = "QL-600") -> Image.Image:
    """Motiv 1:1 mittig aufs Etikett setzen; drehen nur wenn nötig, verkleinern nur mit fit."""
    label = get_label(label_id)
    min_len, max_len = length_limits(model)
    max_w = label.width
    max_h = label.height if label.height else max_len - 2 * MARGIN

    def fits(w: int, h: int) -> bool:
        return w <= max_w and h <= max_h

    if not fits(*img.size):
        if fits(img.height, img.width):
            img = img.rotate(90, expand=True)
        elif fit:
            img = _shrink(img, max_w, max_h)
        else:
            limit = (f"{format_mm(max_w)} mm breit" if not label.height
                     else f"{format_mm(max_w)} × {format_mm(max_h)} mm groß")
            raise ValueError(
                f"Motiv ist {format_mm(img.width)} × {format_mm(img.height)} mm, "
                f"Etikett {label_id!r} ist höchstens {limit} – "
                "mit --fit verkleinern (Codes evtl. nicht mehr lesbar)")

    height = label.height or min(max(img.height + 2 * MARGIN, min_len), max_len)
    out = Image.new("L", (max_w, height), 255)
    out.paste(img, ((max_w - img.width) // 2, (height - img.height) // 2))
    return out


def _shrink(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Proportional verkleinern, in der Lage (gedreht oder nicht), die größer bleibt."""
    def scale(w: int, h: int) -> float:
        return min(max_w / w, max_h / h)

    if scale(img.height, img.width) > scale(*img.size):
        img = img.rotate(90, expand=True)
    s = scale(*img.size)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
```

- [ ] **Step 4: Tests laufen lassen – müssen bestehen**

Run: `.venv/bin/python -m pytest -q`
Expected: alle grün (56 passed)

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/labels.py src/labelwerk/files.py tests/test_labels.py tests/test_files.py
git commit -m "print-file: Motiv 1:1 aufs Etikett setzen, bei Bedarf drehen oder mit --fit verkleinern

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: CLI `print-file` + Doku

**Files:**
- Modify: `src/labelwerk/cli.py` (komplett ersetzen, Inhalt unten)
- Modify: `tests/test_cli.py`
- Modify: `README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: `files.load_file`, `files.crop`, `files.fit_to_label(img, label_id, fit, model)`, `labels.format_mm`, `printer.print_image`, `printer.PrintError`, `detect.find_brother_lp`, `detect.find_brother_usb`
- Produces: Unterbefehl `labelwerk print-file DATEI [-l] [--page] [--fit] [--preview] [-p] [-b] [--no-cut]`. Bestehende Tests, die `labelwerk.cli.find_brother_lp`, `labelwerk.cli.find_brother_usb` und `labelwerk.cli.prn.print_image` per `monkeypatch` ersetzen, müssen weiter funktionieren.

- [ ] **Step 1: Failing tests schreiben**

An `tests/test_cli.py` anhängen:

```python
from PIL import Image


def _png(tmp_path, w_mm=40, h_mm=20):
    path = tmp_path / "motiv.png"
    Image.new("L", (round(w_mm * 300 / 25.4), round(h_mm * 300 / 25.4)), 0).save(path)
    return path


def test_print_file_preview_reports_size_in_mm(tmp_path, capsys):
    out = tmp_path / "vorschau.png"
    rc = main(["print-file", str(_png(tmp_path)), "-l", "62", "--preview", str(out)])
    assert rc == 0
    assert out.exists()
    assert "58,9 × 22,0 mm" in capsys.readouterr().out


def test_print_file_sends_image_in_label_width(tmp_path, monkeypatch):
    sent = {}
    def fake_print(img, label, **kw):
        sent["size"] = img.size
        return {"outcome": "printed", "did_print": True}
    monkeypatch.setattr("labelwerk.cli.prn.print_image", fake_print)
    rc = main(["print-file", str(_png(tmp_path)), "-l", "62", "-p", "file:///dev/usb/lp0"])
    assert rc == 0
    assert sent["size"][0] == 696


def test_print_file_unsupported_type(tmp_path, capsys):
    path = tmp_path / "notiz.txt"
    path.write_text("x")
    rc = main(["print-file", str(path), "--preview", str(tmp_path / "x.png")])
    assert rc == 2
    assert "nicht unterstützt" in capsys.readouterr().err


def test_print_file_missing_file(tmp_path, capsys):
    rc = main(["print-file", str(tmp_path / "fehlt.pdf"), "--preview", str(tmp_path / "x.png")])
    assert rc == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_print_file_too_large_suggests_fit(tmp_path, capsys):
    rc = main(["print-file", str(_png(tmp_path, 120, 70)), "--preview", str(tmp_path / "x.png")])
    assert rc == 2
    assert "--fit" in capsys.readouterr().err
```

- [ ] **Step 2: Tests laufen lassen – müssen fehlschlagen**

Run: `.venv/bin/python -m pytest -q tests/test_cli.py`
Expected: die 5 neuen Tests FAIL (argparse: `invalid choice: 'print-file'` → `SystemExit: 2`), die bisherigen bestehen.

- [ ] **Step 3: Implementierung – `src/labelwerk/cli.py` komplett ersetzen**

```python
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
```

- [ ] **Step 4: Tests laufen lassen – müssen bestehen**

Run: `.venv/bin/python -m pytest -q`
Expected: alle grün (61 passed)

- [ ] **Step 5: Doku**

`README.md`, Abschnitt „Benutzung“ – Codeblock ersetzen durch:

```bash
labelwerk labels                                   # verfügbare Etiketten
labelwerk print "X1 -K3\nKlemme 24V" -l 62x29 --preview vorschau.png
labelwerk print "X1 -K3\nKlemme 24V" -l 62x29      # drucken (Drucker wird automatisch erkannt)
labelwerk print-file internetmarke.pdf -l 62       # PDF/PNG/JPG 1:1 drucken
```

und die Zeile „Optionen: …“ ersetzen durch:

```
Optionen: `-s` Schriftgröße, `--font` eigene TTF, `-b pyusb` alternatives USB-Backend, `--no-cut`.
`print-file` schneidet auf Schnittmarken (z. B. Internetmarke) bzw. den Inhalt zu, dreht bei Bedarf und druckt 1:1; `--fit` verkleinert zu große Motive, `--page N` wählt die PDF-Seite.
```

Im Architektur-Block der README nach `render.py` einfügen:

```
files.py    PDF/Bild → zugeschnitten, 1:1 aufs Etikett gesetzt
```

`CLAUDE.md`, Abschnitt „Architektur“ – nach dem `render.py`-Eintrag einfügen:

```
  files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
              crop(img) -> auf Schnittmarken bzw. Inhalt; fit_to_label(img, label_id, fit) -> 1:1, ggf. gedreht
```

und unter „Abhängigkeiten“ `pypdfium2>=4` ergänzen. Im Abschnitt „Stand (funktioniert)“ ergänzen: `- \`labelwerk print-file\` druckt PDF/PNG/JPG 1:1 (z. B. Internetmarke auf \`-l 62\`).`

- [ ] **Step 6: Commit**

```bash
git add src/labelwerk/cli.py tests/test_cli.py README.md CLAUDE.md
git commit -m "CLI: print-file druckt PDF/PNG/JPG 1:1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Abnahme am echten Drucker (manuell, durch den Nutzer)

- [ ] **Step 1: Vorschau einer echten Internetmarke**

Run: `labelwerk print-file ~/Documents/Versand/<datei>.pdf -l 62 --preview /tmp/marke.png`
Expected: `Vorschau: /tmp/marke.png (58,9 × 92,0 mm), ±0,2 mm`; Bild zeigt die gedrehte Marke ohne Schnittmarkenreste.

- [ ] **Step 2: Drucken** (nur der Nutzer löst den Druck aus)

Run: `labelwerk print-file ~/Documents/Versand/<datei>.pdf -l 62`
Expected: `Status: printed`; Etikett ca. 92 mm lang; Matrixcode mit Handy-Scanner lesbar.
