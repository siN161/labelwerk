"""Test sheets for a conversion service (e.g. paketikett.de): vector PDF with real text, grid every
10 mm, in every cell a QR code "CODE x y" (centre of the cell in mm). From the converted result
``analyze.py`` reads which area went where (rotation, scale). No real data.

Usage: QT_QPA_PLATFORM=offscreen python make_sheets.py WORKING_FOLDER (or $LABELWERK_PARCEL_DIR)
"""
import os
import sys

import segno
from workdir import workdir
from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

SHEETS = {  # name: (code in the QR, width, height in mm)
    "A4-hoch": ("A4H", 210, 297), "A4-quer": ("A4Q", 297, 210), "A5-hoch": ("A5H", 148, 210),
    "A5-quer": ("A5Q", 210, 148), "100x150": ("L100", 100, 150), "105x203": ("L105", 105, 203),
    "103x199": ("L103", 103, 199),
}


def sheet(out, name, code, w, h, sparse=False):
    path = os.path.join(out, f"testblatt-{name}{'-wenig' if sparse else ''}.pdf")
    pdf = QPdfWriter(path)
    pdf.setPageSize(QPageSize(QSizeF(w, h), QPageSize.Unit.Millimeter, name))
    pdf.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    pdf.setResolution(1200)
    pdf.setTitle(f"labelwerk test sheet {name}")
    p = QPainter(pdf)
    mm = pdf.resolution() / 25.4
    p.scale(mm, mm)                                  # from here on in mm
    thin, thick = QPen(QColor(150, 150, 150), 0.1), QPen(Qt.GlobalColor.black, 0.35)
    if not sparse:
        for x in range(0, w + 1, 10):
            p.setPen(thick if x % 50 == 0 else thin)
            p.drawLine(QPointF(x, 0), QPointF(x, h))
        for y in range(0, h + 1, 10):
            p.setPen(thick if y % 50 == 0 else thin)
            p.drawLine(QPointF(0, y), QPointF(w, y))
    step = 30 if sparse else 10
    for x in range(0, w - 9, step):
        for y in range(0, h - 9, step):
            cx, cy = x + 5, y + 5
            qr = segno.make(f"{code} {cx} {cy}", error="l", micro=False)   # Version 1: 21 Module
            n = qr.symbol_size(border=0)[0]
            size = 7.4                                # 0.35 mm per module, 1.3 mm quiet zone to the line
            cell = size / n
            ox, oy = x + (10 - size) / 2, y + (10 - size) / 2
            for r, row in enumerate(qr.matrix):
                for c, v in enumerate(row):
                    if v:
                        p.fillRect(QRectF(ox + c * cell, oy + r * cell, cell, cell), Qt.GlobalColor.black)
    # Corners and direction: asymmetric, so that rotation/mirroring is unambiguous
    big = QFont("DejaVu Sans")
    big.setPixelSize(4)
    big.setBold(True)
    p.setFont(big)
    for text, rect in (("TL", QRectF(1, 1, 12, 5)), ("TR", QRectF(w - 13, 1, 12, 5)),
                       ("BL", QRectF(1, h - 6, 12, 5)), ("BR", QRectF(w - 13, h - 6, 12, 5))):
        p.fillRect(rect, QColor(255, 255, 255))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    p.drawText(QRectF(0, h / 2 - 3, w, 6), Qt.AlignmentFlag.AlignCenter, f"labelwerk test sheet {name} ↑ TOP")
    p.end()


def main(out):
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])   # noqa: F841 (fonts)
    for name, (code, w, h) in SHEETS.items():
        sheet(out, name, code, w, h)
        if name.startswith("A4"):
            sheet(out, name, code, w, h, sparse=True)


if __name__ == "__main__":
    main(str(workdir(sys.argv[1] if len(sys.argv) > 1 else None)))
