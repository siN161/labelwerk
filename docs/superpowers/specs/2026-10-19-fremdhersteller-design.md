# Drucker anderer Hersteller (Roadmap 6b) – Design

Stand: 2026-10-19 · Status: Antworten des Nutzers 1b, 2a (Rückfall b), 3a, 4a, 5b, 6a, 7a, 8a; Spec danach ohne eigene
Freigabe geschrieben – zur Prüfung mit der Abnahme.

## Ziel

labelwerk druckt nicht nur auf Brother-QL: auf jeden in CUPS eingerichteten Etikettendrucker (Dymo LabelWriter,
Zebra mit Treiber, …) und direkt auf Zebra-Drucker in ihrer Druckersprache ZPL – jeweils in der echten Auflösung
des Druckers, damit Barcodes scharf bleiben. Ohne Testgerät: alles „ungeprüft“, getestet gegen nachgebildete
Drucker.

## Entscheidungen (Antworten)

1. **CUPS allgemein und Zebra direkt (ZPL)**; Bluetooth-Geräte (Niimbot, Phomemo) später mit Testgerät.
2. **Etikettengrößen aus dem Treiber** (PPD); Rückfall: **eigene Liste je Hersteller** (Dymo, Zebra).
3. **Echte Auflösung des Druckers** (203 dpi, 300 dpi …) statt fester 300 dpi.
4. **Ein Druckermenü** unten links für Brother, CUPS und Zebra.
5. **Schnitt-Optionen des Treibers** im Reiter SERIE anbieten.
6. CUPS über **`lpstat`, `lpoptions`, `lp`** (keine neue Abhängigkeit).
7. **Kein Testgerät**: alles „ungeprüft“, Tests gegen nachgebildete Ausgaben von `lpstat`/`lpoptions` und
   gegen ZPL-Referenzdaten.
8. **CLI** `-p cups:NAME` (und `-p zpl+tcp://IP`, `-p zpl+file:///dev/usb/lpN`).

## Nicht enthalten

Bluetooth-Geräte, Endlosband bei Fremddruckern (nur feste Etiketten), Zweifarbdruck außer Brother, Statusabfrage
und „Medium prüfen“ bei Fremddruckern, Druckerverwaltung (Warteschlange einrichten macht das System), Abbrechen
eines schon an CUPS übergebenen Auftrags (geht über die Druckerverwaltung des Systems).

## 1 – Auflösung je Etikett (Kern-Umbau)

- **`Label.dpi`** (Brother: 300). Alle Umrechnungen mm ↔ Druckpunkte und pt → Druckpunkte (Schrift) richten sich
  nach dem Etikett des Dokuments statt nach der festen Zahl 300: `render` (`_Sheet.dpi`, Schriftgrößen, Rahmen,
  Barcodes – Modul bleibt „ganze Druckpunkte“, wird also bei 203 dpi physisch breiter), `layout` (`RenderedObject.dpi`
  trägt die Auflösung zu den mm-Rechtecken), `files`/`imaging` (Bilder 1:1 in Etikett-dpi), `barcodes`, `storage`
  (Grenzen in Druckpunkten), GUI-Arbeitsfläche (echte Größe bei jeder Auflösung).
- **Etiketten anderer Hersteller** als eigene Etikett-IDs, die Größe und Auflösung tragen: `"54x25mm@300"` (fest,
  Breite × Höhe in mm, auf 0,1 mm) – `labels.get_label` versteht sie ohne angeschlossenen Drucker (Datei bleibt
  öffnbar); bedruckbar = ganzes Etikett (der Rand des Dokuments hält Abstand). Beschreibung „54 × 25 mm · 300 dpi“.
- **Vorschau = Druck** bleibt: das Druckbild hat die Auflösung des Druckers.

## 2 – CUPS

- **`cups.py`** (Kern, ohne Qt): `queues()` aus `lpstat -e` (Name) und `lpstat -v` (Geräte-URI); Warteschlangen, die
  ein Brother-QL per USB sind, werden nicht doppelt gezeigt, wenn labelwerk ihn direkt findet (Direktweg zuerst).
  `media(queue)`: Etiketten aus der PPD (`/etc/cups/ppd/<queue>.ppd`: `*PaperDimension`, `*DefaultResolution`);
  nicht lesbar → Namen aus `lpoptions -p <queue> -l` (`PageSize`: „62x29mm“, „w288h432“ in Punkt); nichts davon →
  Liste je Hersteller (`MEDIA_LISTS`: Dymo-Klassiker 99010/99012/11352/…, Zebra 2×1"/4×6" …). Auflösung aus der PPD,
  sonst 300 dpi. `cut_options(queue)`: Optionen aus `lpoptions -l`, deren Name oder Titel „Cut“/„Schnitt“ enthält
  (Titel und Werte wie angegeben). Aufrufe mit Zeitlimit; Fehler → `CupsError` (deutsch).
- **Drucken** (`printer.print_image` für `cups:NAME`): PNG je Etikett in Druckerauflösung, `lp -d NAME -o ppi=<dpi>
  -o PageSize=<Größe> [Schnitt-Optionen] datei1.png …` – eine Serie = ein Auftrag mit mehreren Dateien; Auftrags-ID
  aus der Antwort („An die Warteschlange übergeben ✓ (Auftrag QL-12)“). Fehler (Warteschlange gestoppt/unbekannt) →
  `PrintError`.
- **Modell-ID** `cups:NAME`: `labels_for_model` = Etiketten der Warteschlange, `capabilities` (Abschneider = es gibt
  eine Schnitt-Option, kein Rot, `tested` = nein).

## 3 – Zebra direkt (ZPL)

- **Erkennung:** USB-Drucker mit Hersteller 0a5f (Zebra) unter `/dev/usb/lp*`; Auflösung aus der IEEE-1284-Kennung
  („…203dpi…“, „…300dpi…“), sonst 203 dpi; Netzwerk-Zebras in den Einstellungen (Netzwerkdrucker bekommen eine
  „Art“: Brother oder Zebra, bei Zebra die Auflösung).
- **Etiketten:** Liste `ZEBRA_MEDIA` (gängige Größen: 51×25, 57×32, 76×51, 102×51, 102×76, 102×152 mm …) in der
  Auflösung des Druckers.
- **ZPL:** `^XA ^PW<Breite> ^LL<Länge> ^MM<Modus> ^FO0,0 ^GFA,…(Bild als Hex, Zeilen komprimiert nach Zebra-ASCII)
  ^FS ^PQ1 ^XZ` je Etikett; Serie = ein Datenstrom. Schnitt-Modus (Reiter SERIE): Abreißen (T), Schneiden (C),
  Ablösen (P). Senden roh an `/dev/usb/lpN` bzw. TCP 9100 (Zeitlimit wie Brother-Netzwerk).
- **Modell-ID** `zpl:203` / `zpl:300`; URIs `zpl+file:///dev/usb/lpN`, `zpl+tcp://host:9100`.
- **Referenztests:** ZPL eines festen Testetiketts je Auflösung als SHA-256 (wie die Brother-Referenzen).

## 4 – GUI

- **Druckermenü:** Brother (direkt), Zebra (direkt) und CUPS-Warteschlangen („Dymo LabelWriter 450 · CUPS“),
  ungeprüfte gekennzeichnet; Automatisch: Brother direkt › Zebra direkt › CUPS.
- **Reiter Papier:** Etiketten des gewählten Druckers (bei CUPS aus dem Treiber, gruppiert „Etiketten des Druckers“).
- **Reiter SERIE:** bei CUPS die Schnitt-Optionen des Treibers (je Option eine Auswahl), bei Zebra der Modus, bei
  Brother wie bisher; gespeichert je Drucker in den Einstellungen (`printer_options`), nicht in der Datei.
- **Einstellungen:** Netzwerkdrucker mit Art (Brother/Zebra) und bei Zebra Auflösung.
- **Medium prüfen** nur Brother per USB (sonst gesperrt mit Hinweis).

## Tests

Auflösung: dasselbe Etikett bei 203 und 300 dpi physisch gleich groß (Text, Bild 1:1, Rahmen, Positionen),
Barcodes in ganzen Punkten bei 203 dpi lesbar (zxing); Etikett-IDs „…@dpi“ (lesen, speichern, unbekannt);
CUPS mit nachgebildeten Ausgaben (`subprocess` ersetzt): Warteschlangen, PPD-Größen, Schnitt-Optionen, `lp`-Aufruf
(Argumente, mehrere Dateien), Fehler, Zeitlimit; Zebra: Erkennung (sysfs), ZPL-Aufbau und Referenz-Hash, Senden
(Gerät/Socket ersetzt); GUI: Menü mit allen Arten, Etikettenliste, Schnitt-Optionen, Einstellungen. Kein Test ruft
echte `lp`-Befehle, Geräte oder das Netz.
