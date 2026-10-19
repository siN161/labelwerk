"""paketikett-Ergebnisse genau auswerten.

1. QR-Codes im Ergebnis lesen (Inhalt „KÜRZEL x y“ = Mitte der Zelle in mm auf dem Testblatt).
2. Je Code eine affine Abbildung Testblatt(mm) → Ergebnis(px) aus den vier Ecken.
3. Codes mit gleicher Abbildung = ein ausgeschnittener Bereich; Abbildung aus allen Ecken neu.
4. Grenzen genau: dunkle Pixel des Ergebnisses, die das (gerenderte) Testblatt unter dieser Abbildung
   erklärt, zusammenhängend mit den Codes des Bereichs → Rechteck im Ergebnis → zurück aufs Testblatt.

Aufruf: LABELWERK_PARCEL_DIR=ordner python analyze.py ERGEBNIS.pdf [...]
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
import zxingcpp
from PIL import Image, ImageDraw
from scipy import ndimage

DPI = 300
PX = DPI / 25.4
QR_MM = 7.4
sys.path.insert(0, str(Path(__file__).parent))
from workdir import workdir  # noqa: E402

# Arbeitsordner mit Testblättern und umgewandelten Ergebnissen; Ausgaben (Bilder, JSON) ebenfalls dort
DATA = workdir()
WORK = DATA
NAMES = {"A4H": "A4-hoch", "A4Q": "A4-quer", "A5H": "A5-hoch", "A5Q": "A5-quer", "L100": "100x150",
         "L105": "105x203", "L103": "103x199"}
OUT = WORK / "analyse"
_sheets = {}


def page_images(path, dpi=DPI):
    pdf = pdfium.PdfDocument(str(path))
    for i in range(len(pdf)):
        page = pdf[i]
        w, h = page.get_size()
        img = page.render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
        yield i, img, (w * 25.4 / 72, h * 25.4 / 72)


def sheet(code, sparse):
    key = (code, sparse)
    if key not in _sheets:
        f = DATA / f"testblatt-{NAMES[code]}{'-wenig' if sparse else ''}.pdf"
        __, img, __ = next(page_images(f, 600))
        dark = np.asarray(img) < 100
        k = 600 / 25.4
        yy, xx = np.indices(dark.shape)
        on_line = (np.abs(((xx / k) + 5) % 10 - 5) < 0.4) | (np.abs(((yy / k) + 5) % 10 - 5) < 0.4)
        _sheets[key] = dark & ~on_line                     # nur QR-Module (Linien sind periodisch)
    return _sheets[key]


def decode(img):
    found = []
    tile, step = 700, 500
    for y in range(0, max(1, img.height - 200), step):
        for x in range(0, max(1, img.width - 200), step):
            box = (x, y, min(img.width, x + tile), min(img.height, y + tile))
            for r in zxingcpp.read_barcodes(img.crop(box), formats=zxingcpp.BarcodeFormat.QRCode):
                p = r.position
                pts = [(q.x + x, q.y + y) for q in (p.top_left, p.top_right, p.bottom_right, p.bottom_left)]
                c = np.mean(pts, axis=0)
                if any(t == r.text and np.linalg.norm(np.mean(q, axis=0) - c) < 15 for t, q in found):
                    continue
                found.append((r.text, pts))
    return found


def corners(cx, cy):
    h = QR_MM / 2
    return [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]


def fit(src, dst):
    """Affine Abbildung (2×3) mm → px nach kleinsten Quadraten."""
    A = np.hstack([np.asarray(src, float), np.ones((len(src), 1))])
    M, *_ = np.linalg.lstsq(A, np.asarray(dst, float), rcond=None)
    err = np.abs(A @ M - dst).max()
    return M.T, err                                      # 2×3


def apply(M, pts):
    pts = np.asarray(pts, float)
    return pts @ M[:, :2].T + M[:, 2]


def group(items):
    gs = []
    for it in items:
        for g in gs:
            if g["code"] != it["code"]:
                continue
            L0, L = g["M"][:, :2], it["M"][:, :2]
            if np.linalg.norm(L - L0) / np.linalg.norm(L0) > 0.04:
                continue
            pred = g["p0"] + L0 @ (np.array(it["c"]) - g["c0"])
            if np.linalg.norm(pred - it["p"]) < 15:
                g["items"].append(it)
                break
        else:
            gs.append({"code": it["code"], "M": it["M"], "p0": it["p"], "c0": np.array(it["c"]), "items": [it]})
    for g in gs:
        src = [p for it in g["items"] for p in corners(*it["c"])]
        dst = [p for it in g["items"] for p in it["pts"]]
        g["M"], g["err"] = fit(src, dst)
    return gs


def seed(g):
    """Rechteck der gelesenen Codes samt Ruhezone (px)."""
    pts = np.array([p for it in g["items"] for p in it["pts"]])
    q = 1.3 * PX * np.linalg.norm(g["M"][:, 0]) / PX
    return [pts[:, 0].min() - q, pts[:, 1].min() - q, pts[:, 0].max() + q, pts[:, 1].max() + q]


def refine(box, others, ink):
    """Rechteck nach außen erweitern, bis eine ganz weiße Spalte/Zeile kommt (Lücke zwischen den
    Stücken – innerhalb eines Stücks kreuzen die Rasterlinien jede Spalte), ein anderes Stück beginnt
    oder das Bild endet."""
    H, W = ink.shape
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)

    def hits(nx0, ny0, nx1, ny1):
        return any(nx0 < o[2] and o[0] < nx1 and ny0 < o[3] and o[1] < ny1 for o in others)

    changed = True
    while changed:
        changed = False
        if x0 > 0 and ink[y0:y1, x0 - 1].any() and not hits(x0 - 1, y0, x0, y1):
            x0 -= 1; changed = True
        if x1 < W and ink[y0:y1, x1].any() and not hits(x1, y0, x1 + 1, y1):
            x1 += 1; changed = True
        if y0 > 0 and ink[y0 - 1, x0:x1].any() and not hits(x0, y0 - 1, x1, y0):
            y0 -= 1; changed = True
        if y1 < H and ink[y1, x0:x1].any() and not hits(x0, y1, x1, y1 + 1):
            y1 += 1; changed = True
    return x0, y0, x1, y1


def describe(M):
    L = M[:, :2] / PX
    sx, sy = np.linalg.norm(L[:, 0]), np.linalg.norm(L[:, 1])
    angle = (math.degrees(math.atan2(L[1, 0], L[0, 0])) + 360) % 360
    mirror = np.linalg.det(L) < 0
    return round(angle / 90) % 4 * 90, angle, sx, sy, mirror


def analyze(path):
    sparse = "wenig" in path.name
    result = {"file": f"{path.parent.name}/{path.name}", "pages": []}
    for i, img, page_mm in page_images(path):
        arr = np.asarray(img)
        dark = arr < 128
        items = []
        for text, pts in decode(img):
            try:
                code, cx, cy = text.split()
                c = (float(cx), float(cy))
            except ValueError:
                continue
            M, err = fit(corners(*c), pts)
            if err < 6:
                items.append({"code": code, "c": c, "pts": pts, "M": M, "p": np.mean(pts, axis=0)})
        regions = []
        canvas = img.convert("RGB")
        draw = ImageDraw.Draw(canvas)
        ink = arr < 245
        gs = group(items)
        seeds = [seed(g) for g in gs]
        boxes = [list(refine(seeds[n], [s for m, s in enumerate(seeds) if m != n], ink)) for n in range(len(gs))]
        # aneinanderstoßende Stücke: Grenze mitten in der Lücke zwischen den gelesenen Codes
        for a in range(len(gs)):
            for b in range(len(gs)):
                A_, B_ = boxes[a], boxes[b]
                if a == b or not (A_[0] < B_[2] and B_[0] < A_[2] and A_[1] < B_[3] and B_[1] < A_[3]):
                    continue
                sa, sb = seeds[a], seeds[b]
                if sa[2] <= sb[0]:                       # a links von b
                    m = round((sa[2] + sb[0]) / 2); A_[2] = min(A_[2], m); B_[0] = max(B_[0], m)
                elif sa[3] <= sb[1]:                     # a über b
                    m = round((sa[3] + sb[1]) / 2); A_[3] = min(A_[3], m); B_[1] = max(B_[1], m)
        for n, g in enumerate(gs):
            box = boxes[n]
            x0, y0, x1, y1 = box
            A = np.vstack([g["M"], [0, 0, 1]])
            Ai = np.linalg.inv(A)
            cs = apply(Ai[:2], [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
            s0, s1 = cs.min(axis=0), cs.max(axis=0)
            rot, angle, sx, sy, mirror = describe(g["M"])
            regions.append({"code": g["code"], "codes": len(g["items"]),
                            "src_mm": [round(v, 1) for v in (*s0, *s1)],
                            "dst_mm": [round(v / PX, 1) for v in (x0, y0, x1, y1)],
                            "rot": rot, "angle": round(angle, 2), "scale": [round(sx, 3), round(sy, 3)],
                            "mirror": bool(mirror), "fit_px": round(float(g["err"]), 1), "M": g["M"].tolist()})
            draw.rectangle([x0, y0, x1, y1], outline=(255, 0, 0), width=3)
            draw.text((x0 + 6, y0 + 6), f"{s0[0]:.0f},{s0[1]:.0f}", fill=(255, 0, 0))
        regions.sort(key=lambda r: (r["dst_mm"][0], r["dst_mm"][1]))
        result["pages"].append({"size_mm": [round(v, 1) for v in page_mm], "codes": len(items), "regions": regions})
        OUT.mkdir(exist_ok=True)
        canvas.save(OUT / f"{path.parent.name}-{path.stem[:45]}-{i + 1}.png".replace(" ", "_"))
    return result


def main(paths):
    allres = []
    for p in paths:
        r = analyze(Path(p))
        allres.append(r)
        print(f"\n=== {r['file']}")
        for i, pg in enumerate(r["pages"]):
            print(f"Seite {i + 1}: {pg['size_mm'][0]} × {pg['size_mm'][1]} mm, {pg['codes']} Codes")
            for g in pg["regions"]:
                s, d = g["src_mm"], g["dst_mm"]
                print(f"  {g['code']:4s} Quelle {s[0]:6.1f},{s[1]:6.1f} – {s[2]:6.1f},{s[3]:6.1f}"
                      f"  → Ziel {d[0]:6.1f},{d[1]:5.1f} – {d[2]:6.1f},{d[3]:5.1f}"
                      f"  {g['rot']:3d}° ({g['angle']:6.2f})  Maßstab {g['scale'][0]:.3f}/{g['scale'][1]:.3f}"
                      f"{'  GESPIEGELT' if g['mirror'] else ''}  [{g['codes']}]")
    (WORK / "analyse.json").write_text(json.dumps(allres, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
