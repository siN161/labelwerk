# Drucker-Kompatibilität (Roadmap 6) – Design

Stand: 2026-10-19 · Status: Antworten des Nutzers 1a 2b 3a 4b (ungetestet, in README/Release-Notes) 5a 6a 7a 8a 9a;
Spec danach ohne eigene Freigabe geschrieben („fang schonmal an“) – zur Prüfung mit der Abnahme.

## Ziel

labelwerk läuft nicht nur mit dem QL-600: Das Modell des angeschlossenen Druckers wird erkannt, Etiketten,
Abschneider und Zweifarbdruck folgen seinen Fähigkeiten, Netzwerkdrucker lassen sich eintragen, bei mehreren
Druckern wird gewählt. Grundlage für spätere Fremdhersteller (6b): eine Drucker-Beschreibung, die nicht an
Brother hängt.

## Entscheidungen (Antworten)

1. **Modell automatisch** (USB); Modellfeld in den Einstellungen nur als Ersatz.
2. **Alle QL** von brother_ql: 62-mm-Modelle (QL-500 … QL-820NWB) und breite (QL-1050/1060N/1100/1110NWB/
   1115NWB, 102/104 mm); ungeprüfte gekennzeichnet („ungeprüft – Rückmeldung erwünscht“). P-touch-Bandgeräte
   (PT-…) bleiben draußen.
3. **Netzwerkdrucker** per IP/Hostname in den Einstellungen.
4. **Rot/Schwarz** (QL-8xx mit DK-22251 „62red“) jetzt, Farbe je Objekt – ungeprüft, so in README und
   Release-Notes.
5. **Mehrere Drucker:** Auswahl in der Statusleiste (und Einstellungen).
6. **Ohne Abschneider** (QL-500): Schnitt-Optionen ausgeblendet, Hinweis „von Hand abtrennen“.
7. **CLI `-l auto`** (Rolle aus dem Drucker) und `-m auto` (Modell erkannt).
8. **Referenztests je Modell** (Rasterdaten).
9. **README-Tabelle** geprüft / sollte funktionieren / nicht unterstützt.

## Nicht enthalten

P-touch-Bandgeräte, Fremdhersteller (6b), Netzwerk-Suche (mDNS/SNMP), „Medium prüfen“ über das Netz, rote Rahmen
und Farbe je Zeichen, 600-dpi-Modus, Druckerstatus-Überwachung (Papier leer, Deckel offen) außerhalb des Druckens.

## 1 – Kern (Qt-frei)

- **`printers.py`** (neu) – Drucker-Beschreibung und Erkennung:
  - `Printer(uri, model, name, source)` (frozen): `uri` wie für `printer.print_image` (`file:///dev/usb/lp1`,
    `tcp://192.168.1.20:9100`), `model` (None = unbekannt), `name` (Anzeige, z. B. „QL-600 · lp1“), `source`
    `usb` | `network`. `backend` folgt aus der URI (`linux_kernel` | `network`).
  - `usb_printers(sys_root)`: alle Brother-Geräte unter `/sys/class/usbmisc/lp*` (wie `find_brother_lp`, aber
    alle); Modell aus der IEEE-1284-Kennung des Druckers (`device/ieee1284_id`, „MDL:QL-600;“), sonst aus dem
    USB-Produktnamen (`product`), sonst aus der Produkt-ID (`PRODUCT_IDS`, z. B. `20c0` → QL-600); nur Modelle,
    die brother_ql kennt.
  - `network_printers(entries)`: Einträge aus den Einstellungen (Name, Host, Modell) – Port 9100, ohne Prüfung
    der Erreichbarkeit (kein Netzverkehr außer beim Drucken).
  - `choose(printers, wanted)`: gewählter (URI aus den Einstellungen) bzw. erster gefundener; None = keiner.
  - `Capabilities` / `capabilities(model)`: `cutter`, `two_color`, `max_tape_mm` (62 bzw. 104 aus
    brother_ql: Bytes je Zeile), `length_limits`, `tested` (nur `TESTED_MODELS = {"QL-600"}`).
  - `SUPPORTED_MODELS`: QL-Modelle aus brother_ql (ohne PT).
- **Etiketten** (`labels.py`): `labels_for_model` aus den Fähigkeiten (Breite, `restricted_to_models`,
  Rot nur bei Zweifarb-Modellen); ein unbekanntes Modell → `ValueError`.
- **Einstellungen** (`settings.py`): `printer` (gewählte URI, "" = automatisch), `printer_model` (Ersatz,
  "" = automatisch), `last_model` (zuletzt erkanntes Modell – gilt ohne Drucker), `network_printers` (Liste
  `{name, host, model}`, geprüft: Host ohne Leerzeichen/Schema, Modell bekannt). Etikett-Prüfung mit dem
  wirksamen Modell.
- **Drucken** (`printer.py`): `print_image(…, printer, backend, cut)` – Backend aus der URI (`network` für
  `tcp://`); ohne Abschneider `cut=False`; Rot: `build_instructions(…, red=True)` für Etiketten
  BLACK_RED_WHITE (RGB-Druckbild, `to_print_mode` behält Rot). Meldungen für Netzwerkfehler (nicht erreichbar,
  Zeitüberschreitung).
- **Farbe** (`document.py`): `color` (`COLORS` = black, red; Standard black) an Text-, Bild- und Barcode-
  Objekten; gespeichert (Schemata). `render`: rote Objekte rot (RGB 255/0/0), aber nur, wenn das Etikett Rot
  kann (sonst schwarz – Vorschau = Druck); `compose` klebt je Farbe. Barcodes in Rot: Hinweis „Scanner lesen
  Rot schlecht“.
- **CLI** (`cli.py`): `-m/--model auto` (Standard: erkannt, sonst Einstellung), `-l auto` (Rolle per
  Statusabfrage des USB-Druckers → Etikett; ohne Drucker/Rolle verständliche Meldung, Exit-Code 2),
  `labelwerk printers` (gefundene Drucker mit Modell und Status „geprüft/ungeprüft“).
- **Referenztests** (`tests/golden/`): je unterstütztem Modell die Rasterdaten eines festen Testetiketts
  (62 mm bzw. 102 mm, mit/ohne Schnitt, Rot bei Zweifarb-Modellen) als SHA-256; `tools/golden.py --update`
  erzeugt sie neu. Beweist, was gesendet wird – nicht, was gedruckt wird.

## 2 – GUI

- **Statusleiste:** Druckeranzeige wird ein Knopf mit Menü: gefundene Drucker (USB und eingetragene Netzwerk-
  drucker, „● QL-600 · lp1“), „Automatisch (erster gefundener)“; ungeprüfte Modelle mit „ungeprüft“ und
  Tooltip „Rückmeldung erwünscht“. Wahl wird gespeichert.
- **Modell wechselt** (anderer Drucker, Wahl, Einstellung): `MainWindow.set_model(model)` – Etikettenliste
  (Reiter Papier), Längengrenzen, Schnitt, Farbe, Medium prüfen folgen; das offene Etikett bleibt, passt es
  nicht zum Modell → Hinweis (wie beim Öffnen: „Etikett passt nicht zum Drucker“), `last_model` gespeichert.
- **Einstellungen** (Reiter Allgemein): „Druckermodell“ (Automatisch / Liste) und „Netzwerkdrucker“
  (Liste mit Hinzufügen/Entfernen: Name, Host, Modell).
- **Ohne Abschneider:** Reiter SERIE ohne Schnitt-Auswahl, Hinweis „Drucker ohne Abschneider – Etiketten von
  Hand abtrennen“.
- **Farbe:** Reiter LAYOUT, Bereich „Farbe“ (Schwarz/Rot) für die Auswahl – nur mit Etikett 62red auf einem
  Zweifarb-Modell, sonst mit Tooltip gesperrt.
- **Medium prüfen:** nur USB (bei Netzwerkdrucker gesperrt, Tooltip).

## 3 – Doku

README: Tabelle *geprüft* (QL-600 + DK-22205) / *sollte funktionieren* (übrige QL bis 62 mm, breite QL,
Zweifarbdruck – ungeprüft) / *nicht unterstützt* (P-touch-Bandgeräte, andere Hersteller); Bitte um Rückmeldung.

## Tests

Erkennung mit gefälschtem sysfs (`tmp_path`: ieee1284_id, product, idProduct), mehrere Drucker, Wahl;
Fähigkeiten und Etiketten je Modell; Einstellungen (Netzwerkdrucker, Ersatzmodell); Drucken ohne Abschneider,
über das Netz (Backend gefälscht), in Rot (Rasterdaten mit Rot-Ebene); Farbe rendern/speichern; CLI `-l auto`,
`-m auto`, `printers` (Statusabfrage gefälscht); Referenztests je Modell; GUI: Druckerwahl, Modellwechsel,
Schnitt ausgeblendet, Farbe in Layout, Einstellungen. Nie echte Hardware, kein Netzverkehr.
