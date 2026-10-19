# Werkzeuge: Paketmarken-Typen pflegen

Nur zum Pflegen von `src/labelwerk/parcel_data/catalog.json` – labelwerk selbst braucht sie nicht.
Benötigt numpy, scipy, zxing-cpp, pypdfium2, Pillow, segno und (für `make_sheets.py`) PySide6.

| Skript | Zweck |
|---|---|
| `make_sheets.py [ORDNER]` | Testblätter (A4/A5 hoch/quer, 100×150, 105×203, 103×199) mit QR-Raster |
| `analyze.py ERGEBNIS.pdf …` | QR-Codes im umgewandelten Ergebnis → Bereiche je Stück (`analyse.json`) |
| `extract.py [TYPID …]` | genaue Bereiche je Typ (fehlende Stücke, Kanten geschärft) → `result/`, `check/` |
| `assemble.py` | `result/*.json` → `templates.json` + Bericht |
| `workdir.py` | Arbeitsordner prüfen (außerhalb des Repositorys) |
| `catalog.py templates.json catalog.json` | Daten für labelwerk (Erkennung, Seitengrößen, Bild-Regeln) |

Arbeitsordner ist Pflicht: `LABELWERK_PARCEL_DIR=ordner` (bzw. bei `make_sheets.py` als Argument) – dort liegen
Testblätter, umgewandelte Ergebnisse und alle Ausgaben (`analyse/`, `check/`, `result/`, `templates.json`). Liegt
der Ordner im Repository, brechen die Werkzeuge ab (`workdir.py`); `.gitignore` deckt die Ausgaben zusätzlich ab.
Ablauf und Format: `src/labelwerk/parcel_data/README.md`. Echte Marken (Gegenprobe) nur lokal in
`Original/` mit `Original/originale.json` – nie ins Repository.
