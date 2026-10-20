"""result/*.json → templates.json (layout format of the spec) + templates-bericht.txt."""
import json
import sys
from pathlib import Path

PX = 300 / 25.4


def dst_of(p):
    M = p["M"]; src = p["src"]
    xs, ys = [], []
    for x, y in ((src[0], src[1]), (src[2], src[1]), (src[2], src[3]), (src[0], src[3])):
        xs.append(M[0][0] * x + M[0][1] * y + M[0][2])
        ys.append(M[1][0] * x + M[1][1] * y + M[1][2])
    return [min(xs) / PX, min(ys) / PX, max(xs) / PX, max(ys) / PX]


def piece(p):
    """Edges to 0.25 mm; target from the mapping for exactly these edges (0.01 mm)."""
    src = [round(v * 4) / 4 for v in p["src"]]
    M = p["M"]
    xs, ys = [], []
    for x, y in ((src[0], src[1]), (src[2], src[1]), (src[2], src[3]), (src[0], src[3])):
        xs.append(M[0][0] * x + M[0][1] * y + M[0][2])
        ys.append(M[1][0] * x + M[1][1] * y + M[1][2])
    return {"page": p["page"], "src": src, "rotation": p["rotation"],
            "dst": [round(min(xs) / PX, 2), round(min(ys) / PX, 2), round(max(xs) / PX, 2), round(max(ys) / PX, 2)],
            "scale": p["scale"], "kind": p["kind"]}

def inv_map(M, x, y):
    """px (result) → mm (source)."""
    import numpy as np
    A = np.vstack([np.array(M), [0, 0, 1]])
    q = np.linalg.solve(A, [x, y, 1])
    return q[0], q[1]


def tidy(pieces, size_mm):
    """Clip the targets to the page; separate strips lying on top of each other (overlap over the full
    width or height) at the boundary – so nothing depends on the paint order where that is not
    necessary. Source adjusted to match (mapping M)."""
    W, H = size_mm

    def set_dst(p, d):
        pts = [inv_map(p["M"], d[0] * PX, d[1] * PX), inv_map(p["M"], d[2] * PX, d[3] * PX)]
        xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
        p["src"] = [min(xs), min(ys), max(xs), max(ys)]
        p["_dst"] = d

    for p in pieces:
        d = list(p["_dst"])
        d = [max(0.0, d[0]), max(0.0, d[1]), min(W, d[2]), min(H, d[3])]
        if d != p["_dst"]:
            set_dst(p, d)
    for j in range(len(pieces)):
        for i in range(j):
            a, b = pieces[i]["_dst"], pieces[j]["_dst"]
            ox = min(a[2], b[2]) - max(a[0], b[0]); oy = min(a[3], b[3]) - max(a[1], b[1])
            if ox <= 0.3 or oy <= 0.3:
                continue
            wa, ha = a[2] - a[0], a[3] - a[1]; wb, hb = b[2] - b[0], b[3] - b[1]
            d = list(a)
            if ox >= 0.9 * min(wa, wb) and oy < 0.5 * min(ha, hb):      # stacked on top of each other
                if a[1] < b[1]: d[3] = b[1]
                else: d[1] = b[3]
            elif oy >= 0.9 * min(ha, hb) and ox < 0.5 * min(wa, wb):    # side by side
                if a[0] < b[0]: d[2] = b[0]
                else: d[0] = b[2]
            else:
                continue                                                # real overlay
            set_dst(pieces[i], d)


sys.path.insert(0, str(Path(__file__).parent))
from workdir import workdir  # noqa: E402

HERE = workdir()                        # working folder (result/ → templates.json)
ORDER = ["dhl-privat-1", "dhl-privat-1a", "dhl-privat-1a-100x150", "dhl-privat-2", "dhl-privat-3", "dhl-privat-4",
         "dhl-privat-4a", "dhl-privat-4b", "dhl-business-1", "dhl-business-2", "dhl-business-3", "dhl-business-4",
         "dhl-business-5", "dhl-retour-1", "dhl-retour-2", "dhl-retour-3", "dhl-retour-4", "hermes-1", "hermes-2",
         "hermes-3"]


def main():
    types, rows = [], []
    for tid in ORDER:
        f = HERE / "result" / f"{tid}.json"
        if not f.exists():
            rows.append(f"{tid}: MISSING")
            continue
        r = json.loads(f.read_text())
        layouts = {}
        for fmt, labels in r["layouts"].items():
            layouts[fmt] = []
            for lab in labels:
                w, h = lab["size_mm"]
                for p in lab["pieces"]:
                    p["_dst"] = dst_of(p)
                tidy(lab["pieces"], (w, h))
                layouts[fmt].append({
                    "size_mm": [w, h], "length_mm": max(w, h), "height_mm": min(w, h),
                    "pieces": [piece(p) for p in lab["pieces"]]})
        types.append({"id": r["id"], "names": r["names"], "country": r["country"], "carrier": r["carrier"],
                      "source": r["source"], "verified": r["verified"], "layouts": layouts})
        fmt = next(iter(layouts))
        n = sum(len(l["pieces"]) for l in layouts[fmt])
        lengths = " + ".join(f"{l['size_mm'][0]:g}×{l['size_mm'][1]:g}" for l in layouts[fmt])
        dev = ", ".join(f"S{c['page']} {c['mismatch_pct']} %"
                        + (f" (original {c['original_mismatch_pct'][1]} %)" if "original_mismatch_pct" in c else "")
                        for c in r["check"])
        rows.append(f"{tid:24s} {n:2d} pieces  {lengths:20s}  deviation {dev}  "
                    f"{'tested' if r['verified'] else 'untested'}")
    note = ("Coordinates in mm. src: rectangle on the source page (x to the right, y downwards, origin top left).\n"
            "rotation: clockwise rotation from source to target. dst: rectangle [x0, y0, x1, y1] of the rotated\n"
            "piece on the output page size_mm (x to the right, y downwards) – the piece is scaled exactly to this\n"
            "rectangle; scale: mean scale (for information, kind: barcode at ≈ 1).\n"
            "Order of the pieces = paint order (later ones lie on top).\n")
    out = {"format": 1, "note": note, "types": types}
    (HERE / "templates.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    (HERE / "templates-bericht.txt").write_text(note + "\n" + "\n".join(rows) + "\n")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
