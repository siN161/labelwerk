# Bildschirmfoto (Etappe 3d-2b) – Design

Stand: 2026-10-18 · Status: abgestimmt (Ablauf „wie P-touch“, Ansatz XDG-Portal interaktiv)

## Ziel

Im Werkzeug Bild ein **Bildschirmfoto** aufnehmen und direkt als Bild-Objekt aufs Etikett setzen – wie im
P-touch Editor: labelwerk geht aus dem Weg, man wählt Bereich/Fenster/Bildschirm, labelwerk kommt zurück,
das Bild liegt auf dem Etikett. Spart den Umweg System-Werkzeug → Zwischenablage → Strg+V (der bleibt).

## Nicht enthalten

Eigene Bereichsauswahl in labelwerk (die Auswahl macht das System), Verzögerung/Selbstauslöser, Löschen
oder Verwalten der vom Portal angelegten Datei, X11-Sonderwege ohne Portal, Farbwähler (`PickColor`).

## Ansatz

**XDG Desktop Portal** `org.freedesktop.portal.Screenshot` (Version ≥ 1) über **QtDBus** (in PySide6
enthalten, keine neue Abhängigkeit), Aufruf mit `interactive=true`: die Auswahl (Bereich, Fenster,
Bildschirm) zeigt der Desktop (COSMIC: eigene Oberfläche; GNOME/KDE ebenso). Standardweg unter Wayland,
funktioniert auch im Flatpak (Roadmap 8). Verworfen: Vollbild holen + eigener Auswahlrahmen (mehr Arbeit,
keine Fensterwahl), `cosmic-screenshot` direkt (nur COSMIC).

## 1 – Portal (`gui/screenshot.py`)

- Reine Hilfsfunktionen (ohne D-Bus, testbar):
  - `request_path(unique_name, token) -> str`: `/org/freedesktop/portal/desktop/request/<SENDER>/<token>`,
    SENDER = eindeutiger Busname ohne führendes „:“, „.“ → „_“.
  - `parse_response(code, results) -> (Path | None, str | None)`: 0 + `uri` `file://…` → Pfad (URL-dekodiert);
    1 → (None, None) = abgebrochen; 2 bzw. 0 ohne/mit fremder URI → (None, Fehlermeldung, Deutsch).
- `ScreenshotPortal(QObject)`:
  - `available() -> bool`: Sitzungsbus erreichbar und das Portal hat die Schnittstelle Screenshot (Eigenschaft
    `version` lesbar). Kein Absturz ohne Bus.
  - `take() -> None`: eindeutiges `handle_token`, zuerst das Signal `Response` am erwarteten Request-Pfad
    abonnieren, dann `Screenshot("", {handle_token, interactive: true, modal: true})` aufrufen. Liefert der
    Aufruf einen anderen Request-Pfad (ältere Portale), wird auf diesen umabonniert.
    Aufruffehler → sofort `finished(None, Meldung)`.
  - Signal `finished(object, object)`: (Pfad | None, Fehlermeldung | None); (None, None) = abgebrochen.
    Genau einmal je `take()`; das Abo wird danach gelöst. Fehler vor der Auswahl kommen noch während
    `take()`.
  - Empfänger je Aufnahme (`_Request`): QtDBus stellt Signale über die Ereignisschlange zu – eine schon
    eingereihte Antwort einer verworfenen Aufnahme zählt nicht. Ein neues `take()` schließt die offene
    Auswahl (`Request.Close`). Empfänger werden erst beim nächsten `take()` gelöscht (Löschen während der
    eigenen Zustellung stürzt ab). Scheitert das Abo, endet die Aufnahme sofort mit Fehler.
  - `available()` wartet höchstens 5 s, der Aufruf 10 s; D-Bus-Fehler werden über `error_text` deutsch.

## 2 – GUI

- **Aktion** `image.screenshot` „Bildschirmfoto einfügen“ im Kürzel-Verzeichnis (`shortcuts.ACTIONS`), Bereich
  canvas, **ohne Standardkürzel** (Strg+Umschalt+S bleibt für „Speichern unter“ in 3c frei), in den
  Einstellungen belegbar.
- **Bild-Panel:** Knopf **BILDSCHIRMFOTO** unter „Einfügen“ (nach „Aus Zwischenablage“), löst die Aktion aus
  (Tooltip mit Kürzel wie „Aus Datei …“).
- **Ablauf** (`MainWindow.insert_screenshot`):
  1. Schreibmodus beenden. Portal nicht verfügbar → Hinweis in der Statusleiste (Zustand „error“):
     „Bildschirmfoto nicht verfügbar (kein XDG-Portal) – mit dem System-Werkzeug in die Zwischenablage
     kopieren und mit Strg+V einfügen“; Fenster bleibt sichtbar.
  2. Fenster ausblenden (`hide()`), nach `HIDE_DELAY_MS` = 300 ms (Desktop nimmt das Fenster weg)
     `take_screenshot()` aufrufen – ersetzbarer Haken wie `ask_image_file` (Standard: `ScreenshotPortal.take`).
     Aktion währenddessen gesperrt (kein zweiter Aufruf).
  3. Antwort (`finished`): Fenster wieder zeigen und nach vorn holen (`show`, `raise_`, `activateWindow`),
     Aktion entsperren. Pfad → Bild laden (`image_import.load`), mit **300 dpi** (1 Bildschirmpixel = 1
     Druckpunkt; eine DPI-Angabe in der Datei wird ignoriert, eine Verkleinerung beim Laden riesiger Fotos
     eingerechnet: `image_import.load_screenshot`) einfügen wie ein Bild aus der Zwischenablage
     (`_insert_picture`: Zuschnitt/Drehen nach Einstellungen, zu groß → verkleinert, Endlosband hinter den
     Inhalt, ausgewählt, ein Rückgängig-Schritt), Quelle „Bildschirmfoto“. Abgebrochen → nichts, keine
     Meldung. Fehler → Meldung in der Statusleiste („error“), Datei nicht lesbar → „Bildschirmfoto: …“.
     Eine Ausnahme beim Portal-Aufruf holt das Fenster sofort zurück (Meldung statt Traceback).
     Solange ausgeblendet, beendet sich die App nicht, wenn sich ein anderes Fenster schließt
     (`quitOnLastWindowClosed` vorübergehend aus). Schließen während der Aufnahme beendet sie (keine
     Auswahl, kein Einfügen mehr).
  4. **Sicherheitsnetz:** keine Antwort nach `RESTORE_TIMEOUT_MS` = 5 min → Fenster wieder zeigen, Aktion
     entsperren; eine spätere Antwort wird trotzdem noch eingefügt (nur die erste je Aufnahme).
- Die vom Portal angelegte Datei bleibt unangetastet (gehört dem Nutzer bzw. dem Desktop).

## Tests

- **Nie gegen das echte Portal** (es würde eine Auswahl auf dem Bildschirm öffnen): `tests/gui/conftest.py`
  setzt `DBUS_SESSION_BUS_ADDRESS` ins Leere und ersetzt `screenshot.session_bus` (autouse); GUI-Tests
  ersetzen die Haken `screenshot_available`/`take_screenshot`. D-Bus-Ablauf gegen `tests/gui/fake_portal.py`
  (System-Python + Gio) auf einem eigenen `dbus-daemon` mit eigener Konfiguration **ohne** Service-
  Verzeichnisse (die Sitzungs-Standardkonfiguration startet echte Dienste); Fixture prüft
  `ListActivatableNames`. Ohne dbus-daemon/PyGObject übersprungen; CI installiert `dbus python3-gi`.
- Kern-artige Tests: `request_path` (Sonderzeichen im Busnamen), `parse_response` (0 mit URI inkl.
  Leerzeichen/Umlaut %-kodiert, 0 ohne URI, nicht-`file`-URI, 1, 2).
- GUI: Knopf im Panel + Aktion im Verzeichnis (ohne Kürzel); Fenster wird ausgeblendet und nach der Antwort
  wieder gezeigt; Erfolg → Bild 300 dpi, Quelle „Bildschirmfoto“, ausgewählt, ein Rückgängig-Schritt,
  Einstellungen Zuschnitt/Drehen wirken; Abbruch → nichts, keine Meldung, Fenster sichtbar; Fehler →
  Meldung; kein Portal → Hinweis, Fenster nie ausgeblendet; Zeitüberschreitung → Fenster sichtbar, späte
  Antwort fügt ein; zweiter Klick während der Aufnahme wirkungslos.
- Echter Ablauf (COSMIC-Auswahl, Datei) bei der Abnahme durch den Nutzer.
