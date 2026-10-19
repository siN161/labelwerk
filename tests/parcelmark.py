"""Erzeugte Test-Paketmarken (keine echten Daten): kleine PDFs mit Text (Helvetica) und schwarzen
Flächen, von Hand geschrieben – ohne Qt und ohne zusätzliche Bibliothek."""
from __future__ import annotations

from pathlib import Path

PT = 72 / 25.4


def make_pdf(path: Path, size_mm=(210, 297), texts=(), rects=(), images=()) -> Path:
    """PDF mit einer Seite ``size_mm``. ``texts``: (x_mm, y_mm, Text) – y von oben;
    ``rects``: (x0, y0, x1, y1) in mm, schwarz gefüllt; ``images``: (x_mm, y_mm, PIL-Bild „L“,
    dpi) – als Graustufenbild eingebettet (Barcodes)."""
    w, h = size_mm[0] * PT, size_mm[1] * PT
    ops = ["0 g"]
    for x0, y0, x1, y1 in rects:
        ops.append(f"{x0 * PT:.2f} {h - y1 * PT:.2f} {(x1 - x0) * PT:.2f} {(y1 - y0) * PT:.2f} re f")
    for n, (x, y, img, dpi) in enumerate(images):
        iw, ih = img.width * 72 / dpi, img.height * 72 / dpi
        ops.append(f"q {iw:.2f} 0 0 {ih:.2f} {x * PT:.2f} {h - y * PT - ih:.2f} cm /Im{n} Do Q")
    for x, y, text in texts:
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"BT /F1 10 Tf {x * PT:.2f} {h - y * PT:.2f} Td ({safe}) Tj ET")
    content = "\n".join(ops).encode("latin-1")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"]
    xobjects = " ".join(f"/Im{n} {6 + n} 0 R" for n in range(len(images)))
    objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w:.2f} {h:.2f}] "
                   f"/Resources << /Font << /F1 5 0 R >> /XObject << {xobjects} >> >> "
                   f"/Contents 4 0 R >>".encode())
    objects.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                   b"/Encoding /WinAnsiEncoding >>")
    for _, _, img, _ in images:
        data = img.convert("L").tobytes()
        objects.append(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace "
                       b"/DeviceGray /BitsPerComponent 8 /Length %d >>\nstream\n"
                       % (img.width, img.height, len(data)) + data + b"\nendstream")
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    path = Path(path)
    path.write_bytes(bytes(out))
    return path
