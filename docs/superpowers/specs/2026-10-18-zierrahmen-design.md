# Zierrahmen ums Etikett – Design

Stand: 2026-10-18 · Status: abgestimmt (nur ums Etikett, Linienrahmen mit Einstellungen, Innenraum schrumpft)

## Ziel

Ein Rahmen ums ganze Etikett wie der P-touch „Rahmen“: Linienrahmen in mehreren Arten, scharf in jeder
Etikettgröße, folgt Größe und automatischer Länge; automatisch gesetzter Inhalt bleibt innerhalb.

## Nicht enthalten

Form-Objekte (Rechteck, Linie, Ellipse), Rahmen um einzelne Objekte, Zierornamente, CLI-Option,
Rahmen als Voreinstellung für neue Etiketten (dafür gibt es Favoriten).

## 1 – Kern (Qt-frei)

- **Datenmodell** (`document.py`): `Frame(style, rounded=False, line_mm=0.5, inset_mm=0.0, padding_mm=1.0)`,
  `Document.frame: Frame | None = None`.
  - `style`: `single` (einfach), `double` (doppelt: zwei Linien je `line_mm`, Abstand `line_mm`), `thick_thin`
    (außen 2 × `line_mm`, innen `line_mm`, Abstand `line_mm`), `dashed` (Strich 3 × `line_mm`, Lücke 2 ×),
    `dotted` (runde Punkte im Abstand 2 × `line_mm`), `corners` (nur Eckwinkel, Schenkel 4 mm bzw. höchstens
    ein Viertel der kürzeren Seite).
  - Grenzen: `line_mm` 0,1–3, `inset_mm` 0–10, `padding_mm` 0–10; unbekannte Art → `ValueError` (deutsch).
  - `rounded`: Eckradius 2 mm bzw. höchstens ein Viertel der kürzeren Seite; bei `corners` bogenförmige
    Ecken.
- **Lage:** Außenkante des Rahmens = bedruckbarer Bereich (Etikett minus `MARGIN` quer und `margin_mm` in
  Bandlaufrichtung), um `inset_mm` nach innen versetzt. Ist kein Platz mehr (Innenraum ≤ 0), entfällt
  der Rahmen nicht still: `ValueError` „Rahmen passt nicht aufs Etikett“ (GUI: Meldung wie bei
  Renderfehlern).
- **Runde Etiketten** (`shape == "round"`): Rahmen ist ein Kreis um den Mittelpunkt (Durchmesser =
  kürzere Seite des bedruckbaren Bereichs − 2 × `inset_mm`); `rounded` gilt dort nicht, `corners` ergibt
  keinen Rahmen und wird in der GUI nicht angeboten (Datei mit `corners` auf rundem Etikett: wie `single`).
  Innenraum = Quadrat im Kreis.
- **Zeichnen:** `render.draw_frame(img, doc, size)` in Druckpunkten (300 dpi, Pillow, schwarz), in
  `compose`/`render_document` vor den Objekten; Vorschau = Druck. Pixelgenau: Linien liegen ganz innerhalb
  der Außenkante, Strichstärke = `round(line_mm · 300/25,4)`, mindestens 1 Punkt.
- **Innenraum:** `_Sheet.room()` und das mittige Platzieren (`_place`) rechnen ohne Rahmenstärke und
  `padding_mm` (Innenabstand je Seite = `inset_mm` + Rahmenbreite + `padding_mm`); die automatische
  Länge (`_label_size`) legt den Innenabstand in Bandlaufrichtung zusätzlich zu. Frei platzierte
  Objekte bleiben, wo sie sind (Lage relativ zum Etikett wie bisher).
- `layout.frame_area(doc, model, size) -> Rect | None` (mm, Innenraum) für Ausrichten und Einrasten.
- **Renderer-Cache:** `frame` gehört zum Kontext (Änderung → Etikett neu, Objekte nur, wenn sich der
  Innenraum für sie ändert, d. h. nicht positionierte).
- **Speichern** (`storage.py`): Feld `frame` im Dokument (optional, `null` = kein Rahmen), Schema `FRAME`
  mit Arten und Grenzen; Version bleibt 1 (ältere Stände übergehen das Feld).

## 2 – GUI

- **Reiter PAPIER, Bereich „Rahmen“** (nach „Ränder“): Auswahlliste der Arten mit Vorschau je Eintrag (aus
  dem Kern gezeichnet) – „Kein“, Einfach, Doppelt, Dick-dünn, Gestrichelt, Gepunktet, Nur Ecken (nicht bei
  runden Etiketten); Haken „abgerundet“ (nicht bei runden); Strichstärke, Abstand zum Rand, Innenabstand in mm
  (deaktiviert bei „Kein“). Jede Änderung = ein Rückgängig-Schritt (Felder wie die Ränder: beim Verlassen
  bzw. Enter).
- **Arbeitsfläche:** zeigt den Rahmen als Teil des Etiketts (Druckbild), nicht anklickbar.
- **Ausrichten am Etikett** und **Einrasten** an Kanten/Mitte nutzen bei aktivem Rahmen zusätzlich den
  Innenraum (`frame_area`); ohne Rahmen wie bisher.

## Tests

- Kern: Pixeltests je Art (Strichstärke, Lage an der Außenkante, Doppel-/Dick-dünn-Abstände, Striche
  und Punkte, Ecken, abgerundet), runder Rahmen bei `d24`, Endlosband mit automatischer Länge (Rahmen
  folgt, Länge wächst um den Innenabstand), Innenraum (automatischer Text bleibt innerhalb, wird kleiner),
  positionierte Objekte unverändert, Rahmen passt nicht → Meldung, Grenzen und unbekannte Art,
  Renderer = `render_document`.
- Speichern: Rundweg mit Rahmen, Datei ohne `frame`, ungültige Werte → `StorageError`.
- GUI: Panel (Arten, runde Etiketten ohne „Nur Ecken“/abgerundet, Felder aus bei „Kein“), Rückgängig,
  Ausrichten/Einrasten am Innenraum.
