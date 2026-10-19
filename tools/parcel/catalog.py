"""templates.json (Auswertung) → src/labelwerk/parcel_data/catalog.json (Daten für labelwerk).

Aufruf: python catalog.py templates.json ../../src/labelwerk/parcel_data/catalog.json
Erkennungs-Begriffe, weitere Seitengrößen und Bild-Regeln stehen hier von Hand."""
import json
import sys
from pathlib import Path

src = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])

A4, LETTER, A5, A6 = [210, 297], [215.9, 279.4], [148, 210], [105, 148]
NOT_INTL = ["International", "CN 23", "CN23", "Zoll", "Customs"]
DETECT = {
    "dhl-privat-1": {"all": ["DHL"], "any": ["Online Frankierung", "Sendungsnummer", "Leitcode", "Paket"],
                     "none": ["Warenpost", "Retoure", "International", "Geschäftskunden", "Amazon"]},
    "dhl-privat-1a": {"all": ["DHL"], "any": ["Online Frankierung", "Sendungsnummer", "Leitcode", "Paket"],
                      "none": ["Warenpost", "Retoure", "International", "Geschäftskunden", "Amazon"]},
    "dhl-privat-1a-100x150": {"all": ["DHL"], "any": ["Online Frankierung", "Sendungsnummer", "Paket"],
                              "none": ["Warenpost", "Retoure", "Amazon"]},
    "dhl-privat-2": {"all": ["DHL"], "any": ["International", "Online Frankierung", "Sendungsnummer"],
                     "none": ["Warenpost", "Retoure", "Geschäftskunden", "Amazon"]},
    "dhl-privat-3": {"all": ["Warenpost"], "any": ["DHL", "Deutsche Post"], "none": NOT_INTL},
    "dhl-privat-4": {"all": ["Warenpost"], "any": ["International"], "none": ["CN 23", "CN23", "Zoll", "Customs"]},
    "dhl-privat-4a": {"all": ["Warenpost"], "any": ["CN 23", "CN23", "Zoll", "Customs", "International"], "none": []},
    "dhl-privat-4b": {"all": ["Warenpost"], "any": ["CN 23", "CN23", "Zoll", "Customs", "International"], "none": []},
    "dhl-business-1": {"all": ["DHL"], "any": ["Geschäftskunden", "DHL PAKET", "Sendungsnummer"],
                       "none": ["International", "Warenpost", "Retoure"]},
    "dhl-business-2": {"all": ["DHL"], "any": ["Geschäftskunden", "DHL PAKET", "Sendungsnummer"],
                       "none": ["International", "Warenpost", "Retoure"]},
    "dhl-business-3": {"all": ["DHL"], "any": ["Shopify", "Geschäftskunden", "DHL PAKET", "Sendungsnummer"],
                       "none": ["International", "Warenpost", "Retoure"]},
    "dhl-business-4": {"all": ["DHL"], "any": ["International", "Geschäftskunden", "CN 23", "CN23"],
                       "none": ["Warenpost", "Retoure"]},
    "dhl-business-5": {"all": ["DHL"], "any": ["International", "Geschäftskunden", "CN 23", "CN23"],
                       "none": ["Warenpost", "Retoure"]},
    "dhl-retour-1": {"all": ["DHL"], "any": ["Retoure", "Retourenportal", "Return"], "none": ["Amazon"]},
    "dhl-retour-2": {"all": ["DHL"], "any": ["Retoure", "Retourenportal", "Return"], "none": ["Amazon"]},
    "dhl-retour-3": {"all": [], "any": [], "none": []},
    "dhl-retour-4": {"all": ["Amazon"], "any": ["Rücksendung", "Rücksendeetikett", "DHL"], "none": ["Hermes"]},
    "hermes-1": {"all": ["Amazon"], "any": ["Rücksendung", "Rücksendeetikett", "Hermes"], "none": ["DHL"]},
    # Versionskennung, die Hermes auf den Schein druckt (so heißen die Typen bei paketikett.de)
    "hermes-2": {"all": ["Hermes"], "any": ["Paketschein", "Sendungsnummer", "V4.2"], "none": ["Amazon", "V1.0"]},
    "hermes-3": {"all": ["Hermes"], "any": ["Paketschein", "Sendungsnummer", "V1.0"], "none": ["Amazon", "V4.2"]},
}
SOURCES = {"dhl-retour-4": [A4, LETTER], "hermes-1": [A4, LETTER]}
# Amazon-GIF (6 × 4 Zoll, 300 dpi): Lage auf der A4-Seite geschätzt (meiste Tinte in den Stücken)
RASTER = {"dhl-retour-3": {"dpi": 300, "x_mm": -2.5, "y_mm": 189.4, "px": [1800, 1200]}}


def clamp(p, size):
    """Ausschnitt auf die Seite begrenzen; das Ziel schrumpft im selben Maßstab mit (Drehung beachtet)."""
    x0, y0, x1, y1 = p["src"]
    w, h = size
    nx0, ny0, nx1, ny1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    dl, dt, dr, db = nx0 - x0, ny0 - y0, x1 - nx1, y1 - ny1          # nach innen positiv
    if not any((dl, dt, dr, db)):
        return p
    tw, th = (y1 - y0, x1 - x0) if p["rotation"] in (90, 270) else (x1 - x0, y1 - y0)
    sx = (p["dst"][2] - p["dst"][0]) / tw
    sy = (p["dst"][3] - p["dst"][1]) / th
    left, top, right, bottom = {0: (dl, dt, dr, db), 90: (db, dl, dt, dr),
                                180: (dr, db, dl, dt), 270: (dt, dr, db, dl)}[p["rotation"]]
    a, b, c, d = p["dst"]
    return dict(p, src=[nx0, ny0, nx1, ny1],
                dst=[a + left * sx, b + top * sy, c - right * sx, d - bottom * sy])


def r(v):
    return [round(x, 2) for x in v]


types = []
for t in src["types"]:
    layouts = {}
    sizes = SOURCES.get(t["id"], [t["source"]["size_mm"]])
    max_size = (max(a for a, _ in sizes), max(b for _, b in sizes))
    for key, sheets in t["layouts"].items():
        layouts[key] = [{"size_mm": r(s["size_mm"]), "pieces": [
            {"page": p["page"], "src": r(p["src"]), "rotation": p["rotation"], "dst": r(p["dst"]),
             "kind": "barcode" if p["scale"] > 1.03 or abs(p["scale"] - 1) < 0.03 else "text"}
            for p in (clamp(q, max_size) for q in s["pieces"])]} for s in sheets]
    source = {"sizes_mm": SOURCES.get(t["id"], [t["source"]["size_mm"]])}
    if t["id"] in RASTER:
        source["raster"] = RASTER[t["id"]]
    types.append({"id": t["id"], "country": t["country"], "carrier": t["carrier"], "names": t["names"],
                  "verified": bool(t.get("verified")), "source": source, "detect": DETECT[t["id"]],
                  "layouts": layouts})

catalog = {
    "version": 1,
    "countries": {"DE": {"names": {"de": "Deutschland", "en": "Germany"},
                         "carriers": {"dhl": {"de": "DHL", "en": "DHL"},
                                      "hermes": {"de": "Hermes", "en": "Hermes"}}}},
    "types": types,
}
out.write_text(json.dumps(catalog, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(types), "Typen →", out)
