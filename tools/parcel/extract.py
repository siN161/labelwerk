"""Exact areas per paketikett type: pieces from the QR codes (analyze2), missing pieces by
cross-correlation, edges sharpened by comparison with a rebuild.

LABELWERK_PARCEL_DIR=folder python extract.py [TYPEID …]  (configuration in TYPES below) → check/<id>-<n>.png, result/<id>.json
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage, signal

sys.path.insert(0, str(Path(__file__).parent))
import analyze as A  # noqa: E402

HERE = A.WORK
D = A.DATA
PX = A.PX
SHEET = {"A4H": ("testblatt-A4-hoch.pdf", (210, 297)), "A5H": ("testblatt-A5-hoch.pdf", (148, 210)),
         "L100": ("testblatt-100x150.pdf", (100, 150))}

# id: (folder, file, name de, name en, carrier, source mm, format)
TYPES = {
    "dhl-privat-1": ("DHL Privat", "1 DHL National [dhl.de][shop.deutschepost.de][ebay] - a4 hoch.pdf",
                     "DHL national (dhl.de, Post-Shop, eBay)", "DHL domestic (dhl.de, Post shop, eBay)",
                     "dhl", (210, 297), "62"),
    "dhl-privat-1a": ("DHL Privat", "1a DHL National [dhl.de][shop.deutschepost.de][ebay] 100x150 - a4 hoch.pdf",
                      "DHL national 100 × 150 mm (dhl.de, Post-Shop, eBay)",
                      "DHL domestic 100 × 150 mm (dhl.de, Post shop, eBay)", "dhl", (210, 297), "100x150"),
    "dhl-privat-1a-100x150": ("DHL Privat", "1a 1 DHL National [dhl.de][shop.deutschepost.de][ebay] - 100x150.pdf",
                              "DHL national, Marke 100 × 150 mm", "DHL domestic, 100 × 150 mm label", "dhl",
                              (100, 150), "100x150"),
    "dhl-privat-2": ("DHL Privat", "2 DHL National International [dhl.de][shop.deutschepost.de][ebay] - a4 hoch.pdf",
                     "DHL national/international (dhl.de, Post-Shop, eBay)",
                     "DHL domestic/international (dhl.de, Post shop, eBay)", "dhl", (210, 297), "62"),
    "dhl-privat-3": ("DHL Privat", "3 DHL Warenpost national - a4 hoch.pdf", "DHL Warenpost national",
                     "DHL Warenpost domestic", "dhl", (210, 297), "62"),
    "dhl-privat-4": ("DHL Privat", "4 DHL Warenpost international ohne Zoll - a4 hoch.pdf",
                     "DHL Warenpost international ohne Zoll", "DHL Warenpost international without customs",
                     "dhl", (210, 297), "62"),
    "dhl-privat-4a": ("DHL Privat", "4a DHL Warenpost international mit Zoll - a4 hoch.pdf",
                      "DHL Warenpost international mit Zoll", "DHL Warenpost international with customs",
                      "dhl", (210, 297), "62"),
    "dhl-privat-4b": ("DHL Privat", "4b DHL Warenpost international mit Zoll NEU - a4 hoch.pdf",
                      "DHL Warenpost international mit Zoll (neu)", "DHL Warenpost international with customs (new)",
                      "dhl", (210, 297), "62"),
    "dhl-business-1": ("DHL Business", "1 DHL A5 national Geschäftskunden [Business Portal] - A5 hoch.pdf",
                       "DHL Geschäftskunden A5 national", "DHL business customers A5 domestic", "dhl",
                       (148, 210), "62"),
    "dhl-business-2": ("DHL Business", "2 DHL 105 x 203 mm national Geschäftskunden [Business Portal] - A5 hoch.pdf",
                       "DHL Geschäftskunden 105 × 203 mm national", "DHL business customers 105 × 203 mm domestic",
                       "dhl", (105, 203), "62"),
    "dhl-business-3": ("DHL Business", "3 DHL 99 x 200 mm national Geschäftskunden [Shopify Business Portal] - A5 hoch.pdf",
                       "DHL Geschäftskunden 99 × 200 mm national (Shopify)",
                       "DHL business customers 99 × 200 mm domestic (Shopify)", "dhl", (99, 200), "62"),
    "dhl-business-4": ("DHL Business", "4 DHL A5 international Geschäftskunden [Business Portal] - A5 hoch.pdf",
                       "DHL Geschäftskunden A5 international", "DHL business customers A5 international", "dhl",
                       (148, 210), "62"),
    "dhl-business-5": ("DHL Business", "5 DHL A6 international Geschäftskunden [Business Portal] - A5 hoch.pdf",
                       "DHL Geschäftskunden A6 international", "DHL business customers A6 international", "dhl",
                       (105, 148), "62"),
    "dhl-retour-1": ("DHL Retour", "1 DHL Retour [Retourenportal] - A4 hoch.pdf", "DHL Retoure (Retourenportal)",
                     "DHL return (returns portal)", "dhl", (210, 297), "62"),
    "dhl-retour-2": ("DHL Retour", "2 DHL Retour [neues Retourenportal] - A4 hoch.pdf",
                     "DHL Retoure (neues Retourenportal)", "DHL return (new returns portal)", "dhl", (210, 297), "62"),
    "dhl-retour-3": ("DHL Retour", "3 DHL Retour [Amazon gif] - A4 hoch.pdf", "DHL Retoure Amazon (GIF)",
                     "DHL return Amazon (GIF)", "dhl", (210, 297), "62"),
    "dhl-retour-4": ("DHL Retour", "4 DHL Retour [Amazon pdf] - A4 hoch.pdf", "DHL Retoure Amazon (PDF)",
                     "DHL return Amazon (PDF)", "dhl", (210, 297), "62"),
    "hermes-1": ("Hermes", "1 Hermes Retour [Amazon] - A4 hoch.pdf", "Hermes Retoure Amazon",
                 "Hermes return Amazon", "hermes", (210, 297), "62"),
    "hermes-2": ("Hermes", "2 Hermes V4.2.000 - A4 hoch.pdf", "Hermes Paketschein (V4.2)",
                 "Hermes parcel label (V4.2)", "hermes", (210, 297), "62"),
    "hermes-3": ("Hermes", "3 Hermes V1.0.2 - A4 hoch.pdf", "Hermes Paketschein (V1.0)",
                 "Hermes parcel label (V1.0)", "hermes", (210, 297), "62"),
}
# Real parcel labels (local only, never in the repo): Original/originale.json in the data folder, e.g.
# {"source": "marke.pdf", "results": {"dhl-privat-1": "marke-umgewandelt-1.pdf"}}
_originals = D / "Original" / "originale.json"
_orig = json.loads(_originals.read_text()) if _originals.exists() else {"source": "", "results": {}}
ORIGINAL = _orig["results"]
ORIGINAL_SRC = _orig["source"]


# --- Images ---------------------------------------------------------------------------
def target_ink(img):
    """Ink in the result in the polarity of the source (paketikett inverts the test sheets)."""
    a = np.asarray(img, float)
    nonwhite = (a < 235).sum()
    if (a < 60).mean() > 0.4 or nonwhite and ((a >= 140) & (a < 220)).sum() / nonwhite > 0.2:   # inverted
        t = np.where(a >= 235, 255.0, 255 - np.minimum(255, a * 1.5))
    else:
        t = a
    return t < 128


def src_ink(img):
    return np.asarray(img) < 128


def rot_point(x, y, r, W0, H0):
    """Pixel (x, y) after rotating the image by r° clockwise (expand)."""
    if r == 0:
        return x, y
    if r == 90:
        return H0 - 1 - y, x
    if r == 180:
        return W0 - 1 - x, H0 - 1 - y
    return y, W0 - 1 - x


def rotate_cw(a, r):
    return np.rot90(a, k=-(r // 90)) if r else a


# --- Pieces ---------------------------------------------------------------------------
class Piece:
    def __init__(self, M, src_mm, codes):
        self.M = np.asarray(M, float)        # mm (source) → px (result), 2×3
        self.src = list(src_mm)              # [x0, y0, x1, y1] mm
        self.codes = codes

    def full(self):
        return np.vstack([self.M, [0, 0, 1]])

    def dst_box(self):
        x0, y0, x1, y1 = self.src
        pts = np.array([[x0, y0, 1], [x1, y0, 1], [x1, y1, 1], [x0, y1, 1]], float)
        q = (self.full() @ pts.T).T
        return (int(round(q[:, 0].min())), int(round(q[:, 1].min())),
                int(round(q[:, 0].max())), int(round(q[:, 1].max())))

    def rotation(self):
        L = self.M[:, :2]
        ang = (np.degrees(np.arctan2(L[1, 0], L[0, 0])) + 360) % 360
        return int(round(ang / 90) % 4 * 90)

    def scale(self):
        L = self.M[:, :2] / PX
        return float(np.linalg.norm(L[:, 0])), float(np.linalg.norm(L[:, 1]))


def warp(src_img, piece, shape):
    H, W = shape
    inv = np.linalg.inv(piece.full() @ np.diag([1 / PX, 1 / PX, 1]))   # px out → px source
    w = src_img.transform((W, H), Image.AFFINE, tuple(inv[:2].ravel()), resample=Image.BILINEAR, fillcolor=255)
    return np.asarray(w) < 128


def initial_pieces(out_img, sparse=False):
    items = []
    for text, pts in A.decode(out_img):
        try:
            code, cx, cy = text.split()
            c = (float(cx), float(cy))
        except ValueError:
            continue
        M, err = A.fit(A.corners(*c), pts)
        if err < 6:
            items.append({"code": code, "c": c, "pts": pts, "M": M, "p": np.mean(pts, axis=0)})
    groups = A.group(items)
    code = items[0]["code"] if items else None
    pieces = []
    for g in groups:
        pts = np.array([p for it in g["items"] for p in A.corners(*it["c"])])
        s0, s1 = pts.min(axis=0), pts.max(axis=0)
        pieces.append(Piece(g["M"], [s0[0] - 1.3, s0[1] - 1.3, s1[0] + 1.3, s1[1] + 1.3], len(g["items"])))
    return code, pieces


# --- Cost ---------------------------------------------------------------------------
class Scene:
    def __init__(self, target, warped_list, pieces):
        self.target = target
        self.tdil = ndimage.binary_dilation(target, iterations=1)
        self.warped = warped_list
        self.pieces = pieces
        self.active = [True] * len(pieces)
        self.cdil = [ndimage.binary_dilation(w, iterations=1) for w in warped_list]

    def compose(self):
        H, W = self.target.shape
        c = np.zeros((H, W), bool)
        cd = np.zeros((H, W), bool)
        for i, p in enumerate(self.pieces):
            if not self.active[i]:
                continue
            x0, y0, x1, y1 = p.dst_box()
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
            if x1 > x0 and y1 > y0:
                c[y0:y1, x0:x1] = self.warped[i][y0:y1, x0:x1]
                cd[y0:y1, x0:x1] = self.cdil[i][y0:y1, x0:x1]
        return c, cd

    def cost(self):
        c, cd = self.compose()
        return int((c & ~self.tdil).sum() + (self.target & ~cd).sum())

    def optimize(self, step=0.25, rng=3.0, rounds=3, extra=None):
        best = self.cost() + (extra() if extra else 0)
        for _ in range(rounds):
            improved = False
            for i, p in enumerate(self.pieces):
                if not self.active[i]:
                    continue
                for e in range(4):
                    base = p.src[e]
                    for d in np.arange(-rng, rng + step / 2, step):
                        p.src[e] = base + d
                        if p.src[0] >= p.src[2] - 1 or p.src[1] >= p.src[3] - 1:
                            continue
                        c = self.cost() + (extra() if extra else 0)
                        if c < best:
                            best, base, improved = c, p.src[e], True
                    p.src[e] = base
            margin = 0.003 * self.target.sum()        # weak pieces only if they clearly help
            for i, p in enumerate(self.pieces):
                if p.codes < 2:
                    small = min(p.src[2] - p.src[0], p.src[3] - p.src[1]) < 4
                    self.active[i] = not self.active[i]
                    c = self.cost() + (extra() if extra else 0)
                    if self.active[i] and not small and c < best - margin:
                        best, improved = c, True
                    elif not self.active[i] and (small or c <= best + margin):
                        best, improved = c, True
                    else:
                        self.active[i] = not self.active[i]
            if not improved:
                break
        return best


# --- Missing pieces ----------------------------------------------------------------------
def residual(target, pieces, active, min_mm2):
    H, W = target.shape
    covered = np.zeros((H, W), bool)
    for i, p in enumerate(pieces):
        if active[i]:
            x0, y0, x1, y1 = p.dst_box()
            covered[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = True
    covered = ndimage.binary_dilation(covered, iterations=int(PX))
    rest = target & ~covered
    rest = ndimage.binary_closing(rest, np.ones((int(2 * PX), int(2 * PX))))
    lab, n = ndimage.label(rest)
    comps = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if len(ys) / PX ** 2 >= min_mm2:
            comps.append((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1, len(ys)))
    return comps


def search(patch, sink, scales):
    """Best mapping (Dice of the ink) for a piece of the result: rotation, scale, position."""
    Pi = patch.astype(float)
    best = None
    for r in (0, 90, 180, 270):
        R = rotate_cw(sink, r)
        img = Image.fromarray((~R).astype(np.uint8) * 255)
        for s in scales:
            S = np.asarray(img.resize((max(1, int(R.shape[1] * s)), max(1, int(R.shape[0] * s))),
                                      Image.BILINEAR)) < 128
            if S.shape[0] < Pi.shape[0] or S.shape[1] < Pi.shape[1]:
                continue
            Sf = S.astype(float)
            ov = signal.fftconvolve(Sf, Pi[::-1, ::-1], mode="valid")
            win = signal.fftconvolve(Sf, np.ones_like(Pi), mode="valid")
            c = 2 * ov / (Pi.sum() + win + 1e-9)
            idx = np.unravel_index(np.argmax(c), c.shape)
            if best is None or c[idx] > best[0]:
                best = (float(c[idx]), r, s, idx)
    return best


def piece_from(r, s, oy, ox, bx0, by0, shape):
    H0, W0 = shape
    srcpts, dstpts = [], []
    for x, y in ((0, 0), (W0 - 1, 0), (0, H0 - 1), (W0 - 1, H0 - 1)):
        rx, ry = rot_point(x, y, r, W0, H0)
        srcpts.append((x / PX, y / PX))
        dstpts.append((rx * s - ox + bx0, ry * s - oy + by0))
    M, __ = A.fit(srcpts, dstpts)
    return M


def find_missing(scene, src_img, scales, min_mm2=25, rounds=4):
    """Ink that no piece explains → search a mapping by cross-correlation (Dice); extent of the
    new piece = blocks (1 mm) in which the mapping explains the ink. Several rounds: a
    remainder made of two pieces is thus split up one after the other."""
    target = scene.target
    H, W = target.shape
    sink = src_ink(src_img)
    pieces = list(scene.pieces)
    active = list(scene.active)
    found = []
    tried = set()
    for _ in range(rounds):
        comps = [c for c in residual(target, pieces, active, min_mm2) if c[:4] not in tried]
        if not comps:
            break
        new = False
        for bx0, by0, bx1, by1, area in comps:
            tried.add((bx0, by0, bx1, by1))
            patch = target[by0:by1, bx0:bx1]
            if patch.mean() < 0.02 or min(patch.shape) < 2 * PX:
                continue
            best = search(patch, sink, scales)
            if best is None or best[0] < 0.5:
                print(f"  Remainder {bx0 / PX:.0f},{by0 / PX:.0f} mm ({area / PX ** 2:.0f} mm²): no mapping"
                      f" ({best[0] if best else None:.2f})")
                continue
            score, r, s, (oy, ox) = best
            M = piece_from(r, s, oy, ox, bx0, by0, sink.shape)
            p = Piece(M, [0, 0, 1, 1], 2)
            w = warp(src_img, p, target.shape)
            # Extent: largest connected area of blocks (1 mm) with a match
            B = int(PX)
            gh, gw = (by1 - by0 + B - 1) // B, (bx1 - bx0 + B - 1) // B
            grid = np.zeros((gh, gw), bool)
            for j in range(gh):
                for i in range(gw):
                    y, x = by0 + j * B, bx0 + i * B
                    tw = w[y:y + B, x:x + B]; tt = target[y:y + B, x:x + B]
                    n = tw.sum() + tt.sum()
                    grid[j, i] = n >= 4 and 2 * (tw & tt).sum() / n > 0.75
            grid = ndimage.binary_closing(grid, np.ones((3, 3))) & ndimage.binary_dilation(grid)
            lab, n = ndimage.label(grid)
            if not n:
                continue
            sizes = ndimage.sum(grid, lab, range(1, n + 1))
            jj, ii = np.nonzero(lab == 1 + int(np.argmax(sizes)))
            d0 = (bx0 + ii.min() * B, by0 + jj.min() * B)
            d1 = (bx0 + (ii.max() + 1) * B, by0 + (jj.max() + 1) * B)
            inv = np.linalg.inv(np.vstack([M, [0, 0, 1]]))
            cs = A.apply(inv[:2], [d0, (d1[0], d0[1]), d1, (d0[0], d1[1])])
            s0, s1 = cs.min(axis=0), cs.max(axis=0)
            p.src = [s0[0], s0[1], s1[0], s1[1]]
            print(f"  Remainder {bx0 / PX:.0f},{by0 / PX:.0f} mm: rotation {r}°, scale {s:.3f}, "
                  f"Dice {score:.2f} → source {s0[0]:.1f},{s0[1]:.1f}–{s1[0]:.1f},{s1[1]:.1f}")
            found.append(p)
            pieces.append(p)
            active.append(True)
            new = True
        if not new:
            break
    return found


def same_transform(a, b, tol_px=4):
    """Same mapping: linear parts ≈ equal, position of a common point ≈ equal."""
    La, Lb = a.M[:, :2], b.M[:, :2]
    if np.linalg.norm(La - Lb) / np.linalg.norm(La) > 0.015:
        return False
    c = np.array([(a.src[0] + a.src[2]) / 2, (a.src[1] + a.src[3]) / 2])
    return np.linalg.norm(A.apply(a.M, [c])[0] - A.apply(b.M, [c])[0]) < tol_px


def merge(pieces):
    """Merge pieces with the same mapping into one (enclosing rectangle in the source)."""
    out = []
    for p in pieces:
        for q in out:
            if same_transform(q, p):
                q.src = [min(q.src[0], p.src[0]), min(q.src[1], p.src[1]),
                         max(q.src[2], p.src[2]), max(q.src[3], p.src[3])]
                q.codes = max(q.codes, p.codes)
                break
        else:
            out.append(p)
    return out


def refine_translation(piece, src_img, target, rng=3):
    """Adjust the position of a piece to the pixel (±rng px)."""
    H, W = target.shape
    x0, y0, x1, y1 = piece.dst_box()
    x0, y0, x1, y1 = max(0, x0 + 10), max(0, y0 + 10), min(W, x1 - 10), min(H, y1 - 10)
    if x1 - x0 < 20 or y1 - y0 < 20:
        return
    w = warp(src_img, piece, target.shape)
    best = None
    for dy in range(-rng, rng + 1):
        for dx in range(-rng, rng + 1):
            t = target[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
            if t.shape != (y1 - y0, x1 - x0):
                continue
            c = int((t ^ w[y0:y1, x0:x1]).sum())
            if best is None or c < best[0]:
                best = (c, dx, dy)
    if best and (best[1] or best[2]):
        piece.M[:, 2] += [best[1], best[2]]


# --- Flow ---------------------------------------------------------------------------
def process(tid):
    folder, fname, de, en, carrier, source, fmt = TYPES[tid]
    out_path = D / folder / fname
    pages_out = list(A.page_images(out_path))
    result = {"id": tid, "names": {"de": de, "en": en}, "country": "DE", "carrier": carrier,
              "source": {"size_mm": list(source)}, "verified": tid in ORIGINAL, "layouts": {fmt: []},
              "check": []}
    for pno, out_img, size in pages_out:
        code, pieces = initial_pieces(out_img)
        sheet_file, sheet_size = SHEET[code]
        src_img = next(A.page_images(D / sheet_file))[1]
        target = target_ink(out_img)
        for p in pieces:
            refine_translation(p, src_img, target)
        scene = Scene(target, [warp(src_img, p, target.shape) for p in pieces], pieces)
        scene.optimize(rounds=1)
        scales = sorted({round(np.mean(p.scale()), 2) for p in pieces} |
                        {round(v, 3) for v in np.arange(0.45, 1.151, 0.025)})
        extra = find_missing(scene, src_img, scales)
        for p in extra:
            refine_translation(p, src_img, target)
        if extra:
            keep = [p for i, p in enumerate(pieces) if scene.active[i]]
            pieces = merge(keep + merge(extra))
            scene = Scene(target, [warp(src_img, p, target.shape) for p in pieces], pieces)
        cost = scene.optimize()
        ink = int(target.sum())
        check = {"page": pno + 1, "mismatch_pct": round(100 * cost / max(1, ink), 1)}
        # Cross-check/sharpening against the real original (shared cost)
        if tid in ORIGINAL:
            o_out = list(A.page_images(D / "Original" / ORIGINAL[tid]))[pno][1]
            o_src = next(A.page_images(D / "Original" / ORIGINAL_SRC))[1]
            o_target = target_ink(o_out)
            o_scene = Scene(o_target, [warp(o_src, p, o_target.shape) for p in pieces], pieces)
            o_scene.active = scene.active
            before = o_scene.cost()
            o_ink = int(o_target.sum())
            # The original counts as much as the test sheet (normalised)
            w = ink / max(1, o_ink)
            scene.optimize(extra=lambda: int(w * o_scene.cost()), step=0.25, rng=2.0, rounds=2)
            after = o_scene.cost()
            check["original_mismatch_pct"] = [round(100 * before / max(1, o_ink), 1),
                                              round(100 * after / max(1, o_ink), 1)]
            check["mismatch_pct"] = round(100 * scene.cost() / max(1, ink), 1)
            save_check(o_scene, HERE / "check" / f"{tid}-{pno + 1}-original.png")
        save_check(scene, HERE / "check" / f"{tid}-{pno + 1}.png")
        label = {"size_mm": [round(size[0], 1), round(size[1], 1)], "pieces": []}
        for i, p in enumerate(pieces):
            if not scene.active[i]:
                continue
            x0, y0, x1, y1 = p.dst_box()
            sx, sy = p.scale()
            label["pieces"].append({
                "page": 1, "src": [round(v * 4) / 4 for v in p.src], "rotation": p.rotation(),
                "dst": [round(x0 / PX * 4) / 4, round(y0 / PX * 4) / 4], "scale": round((sx + sy) / 2, 3),
                "scale_xy": [round(sx, 3), round(sy, 3)],
                "kind": "barcode" if abs((sx + sy) / 2 - 1) < 0.03 else "text",
                "M": p.M.round(4).tolist()})
        # Order = paint order (later pieces lie on top)
        result["layouts"][fmt].append(label)
        result["check"].append(check)
        print(f"{tid} page {pno + 1}: {len(label['pieces'])} pieces, deviation {check}")
    (HERE / "result").mkdir(exist_ok=True)
    (HERE / "result" / f"{tid}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    return result


def save_check(scene, path):
    c, __ = scene.compose()
    t = scene.target
    rgb = np.stack([np.where(c, 0, 255), np.where(t, 0, 255), np.where(t, 0, 255)], -1).astype(np.uint8)
    img = Image.fromarray(rgb)
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for i, p in enumerate(scene.pieces):
        if scene.active[i]:
            d.rectangle(p.dst_box(), outline=(0, 160, 0), width=2)
    path.parent.mkdir(exist_ok=True)
    img.save(path)


if __name__ == "__main__":
    for tid in (sys.argv[1:] or TYPES):
        process(tid)
