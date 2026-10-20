# Freiraum im eigenen Markentyp – Design

Stand 2026-10-20, Antworten des Nutzers: 1b (Abstand zwischen den Stücken), 2a (zwischen die Teile:
keinen, einen oder mehrere), 3c (Standard im Typ, im Reiter PAKET je Marke änderbar).

## Verhalten
- Ein Freiraum ist leeres Band **zwischen zwei Stücken** eines eigenen Typs. Er gehört zum Bereich
  davor: „Freiraum danach“ in mm (0 = keiner). So bleibt er beim Verschieben/Löschen anderer Bereiche
  an seinem Platz; wird sein Bereich gelöscht, verschwindet er mit.
- Anordnen (`parcel.arrange`): nach einem Stück mit Freiraum beginnt eine neue Spalte, der Abstand
  zur vorigen Spalte ist der Freiraum statt der üblichen 1 mm (mindestens diese). Ein Freiraum nach
  dem letzten Stück zählt nicht (nur zwischen den Teilen).
- Auf Endlosband ist der Maßstab eigener Typen 1:1 – der Freiraum hat genau seine Länge; auf festen
  Etiketten wird er mit allem anderen eingepasst.
- Nur eigene Typen (mitgelieferte haben feste Layouts).

## Daten
- `Piece.space_after` (mm, Standard 0); JSON des eigenen Typs: `"space_after_mm"` je Bereich, nur
  wenn > 0; geprüft 0 … `MAX_SPACE_MM` (500).
- `parcel.spaces(ptype)` → Liste (Index des Stücks, Länge) der wirksamen Freiräume;
  `parcel.with_spaces(ptype, lengths)` → Typ mit geänderten Längen (nicht gespeichert).

## Fenster „Eigener Markentyp“
- Je Bereich unter „Barcode – nicht verkleinern“: Feld „Freiraum danach“ (mm, 0 = „keiner“);
  beim letzten Bereich gesperrt (Hinweis im Tooltip). Die Liste zeigt „· Freiraum 10 mm“.
- Vorschau zeigt den Freiraum.

## Reiter PAKET
- Hat der gewählte (eigene) Typ Freiräume: Bereich „Freiraum“ mit einem Feld je Freiraum
  („Nach Bereich n“, mm), vorbelegt mit dem Wert aus dem Typ; Änderung wandelt neu um, gilt für
  diese Marke (nicht gespeichert). Neuer Typ oder neue Marke: wieder die Werte des Typs.
