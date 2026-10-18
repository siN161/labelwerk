# Bildschirmfoto (Etappe 3d-2b) – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Im Reiter Bild ein Bildschirmfoto aufnehmen (Auswahl des Desktops über das XDG-Portal) und direkt als Bild-Objekt aufs Etikett setzen – wie im P-touch Editor.

**Architecture:** `gui/screenshot.py` spricht das Portal `org.freedesktop.portal.Screenshot` über QtDBus an (interaktiv, Antwort asynchron am Request-Objekt, Empfänger je Aufnahme); das Hauptfenster blendet sich aus, ruft das Portal über einen ersetzbaren Haken, zeigt sich danach wieder und fügt das Foto mit 300 dpi wie ein Bild aus der Zwischenablage ein.

**Tech Stack:** Python ≥ 3.10, PySide6 (QtDBus), Pillow, pytest, pytest-qt; in Tests dbus-daemon + PyGObject (System-Python) für das nachgebaute Portal.

Spec: `docs/superpowers/specs/2026-10-18-bildschirmfoto-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge (Branch `proto-3d2b-fix`), nach jedem Task volle Suite grün mit Exit-Code 0 (1335 → 1357 → 1376); jeder Schritt von einem Reviewer geprüft und korrigiert (veraltete Antworten, Absturz beim Löschen des Empfängers in seiner Zustellung, Aufräumen der Testprozesse, Fenster nie verschwunden, Schließen während der Aufnahme); Python 3.10 + PySide6 6.11 im Container grün (inkl. Bus-Tests).

**Patches anwenden:** Jeder Task enthält zwei Patches (Tests, Implementierung) im `git diff`-Format. Den Block **byte-genau** in eine Datei außerhalb des Repos schreiben (z. B. per Skript aus diesem Plan extrahieren) und im Repo-Wurzelverzeichnis anwenden: `git apply --whitespace=nowarn /pfad/patch.diff`. Schlägt `git apply` fehl: nicht von Hand nachbauen, sondern melden (BLOCKED).

## Global Constraints

- **Nie das echte Portal ansprechen:** keine GUI starten, keine Skripte mit `insert_screenshot`/`take_screenshot`/`ScreenshotPortal.take` außerhalb von pytest, kein `gdbus`/`busctl` an `org.freedesktop.portal.Desktop`, nie `dbus-daemon --session`/`dbus-run-session` (startet echte Dienste). Nach Testläufen `ps aux | grep -E "xdg-desktop-portal|dbus-daemon --config|fake_portal"`: keine neuen Prozesse.
- Kern bleibt **Qt-frei**; das Portal lebt in `gui/`.
- Benutzer-Meldungen und Kommentare auf Deutsch; keine Tracebacks für Nutzer.
- Tests ohne Hardware und ohne echte Nutzer-Einstellungen; jedes Widget in GUI-Tests bei `qtbot.addWidget` anmelden.
- Tests: `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – **Exit-Code 0** prüfen, nicht nur „passed“.
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Task umsetzt).

---
### Task 1: Portal-Anbindung – gui/screenshot.py, Tests gegen nachgebautes Portal auf privatem Bus

**Files:**
- Modify: `.github/workflows/tests.yml`
- Create: `src/labelwerk/gui/screenshot.py`
- Modify: `tests/gui/conftest.py`
- Create: `tests/gui/fake_portal.py`
- Create: `tests/gui/test_gui_screenshot_portal.py`

**Interfaces / Produces:** `gui/screenshot.py`: `session_bus()`, `request_path(unique_name, token) -> str`, `parse_response(code, results) -> (Path | None, str | None)`, `error_text(error_name) -> str`, `FAILED`, `ScreenshotPortal(bus=None, parent=None)` mit `available() -> bool`, `take()`, Signal `finished(object, object)`; `tests/gui/fake_portal.py` (System-Python + Gio, Arten normal/early/other/twice); `tests/gui/conftest.py`: `DBUS_SESSION_BUS_ADDRESS` ins Leere + autouse-Fixture `no_session_bus`; CI installiert `dbus python3-gi`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/conftest.py b/tests/gui/conftest.py
index c72b972..c10a5db 100644
--- a/tests/gui/conftest.py
+++ b/tests/gui/conftest.py
@@ -1,6 +1,9 @@
 import os
 
 os.environ["QT_QPA_PLATFORM"] = "offscreen"   # immer, auch wenn die Sitzung wayland/xcb vorgibt
+# Sitzungsbus ins Leere: kein Test erreicht echte Dienste (Bildschirmfoto-Portal öffnete eine
+# Auswahl auf dem Bildschirm); Tests mit D-Bus nutzen einen eigenen Bus mit eigener Adresse
+os.environ["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/nonexistent/labelwerk-test-bus"
 
 try:
     import PySide6  # noqa: F401
@@ -22,6 +25,14 @@ else:
         qapp.clipboard().clear()
         yield
 
+    @pytest.fixture(autouse=True)
+    def no_session_bus(monkeypatch):
+        """Zusätzlich zur Adresse ins Leere: das Bildschirmfoto-Modul bekommt statt des
+        Sitzungsbusses eine nie verbundene Verbindung."""
+        from PySide6.QtDBus import QDBusConnection
+        monkeypatch.setattr("labelwerk.gui.screenshot.session_bus",
+                            lambda: QDBusConnection("labelwerk-test-kein-bus"))
+
     @pytest.fixture(autouse=True)
     def no_printer(monkeypatch):
         """Kein Test liest echte Druckerdaten aus /sys."""
diff --git a/tests/gui/fake_portal.py b/tests/gui/fake_portal.py
new file mode 100644
index 0000000..ef14a4d
--- /dev/null
+++ b/tests/gui/fake_portal.py
@@ -0,0 +1,60 @@
+"""Nachgebautes XDG-Screenshot-Portal für Tests auf einem privaten D-Bus (nie dem der Sitzung).
+
+Läuft mit dem System-Python (PyGObject/Gio): ``python3 fake_portal.py ART CODE URI``.
+ART: ``normal`` (Antwort nach 50 ms), ``early`` (Antwort schon vor dem Rückgabewert),
+``other`` (eigener Request-Pfad wie ältere Portale), ``twice`` (zwei Antworten).
+URI „-“ = Antwort ohne ``uri``; „{n}“ in der URI wird zur Nummer des Aufrufs.
+Gibt „READY“ aus, sobald der Name belegt ist, und je Aufruf
+„CALL interactive=… modal=… token=…“; ohne Namen endet es mit Code 1.
+"""
+import sys
+
+from gi.repository import Gio, GLib
+
+MODE, CODE, URI = sys.argv[1], int(sys.argv[2]), sys.argv[3]
+XML = """<node><interface name="org.freedesktop.portal.Screenshot">
+<method name="Screenshot"><arg type="s" direction="in"/><arg type="a{sv}" direction="in"/>
+<arg type="o" direction="out"/></method><property name="version" type="u" access="read"/>
+</interface></node>"""
+INFO = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
+calls = 0
+
+
+def call(conn, sender, path, iface, method, params, invocation):
+    global calls
+    calls += 1
+    options = params.unpack()[1]
+    print(f"CALL interactive={options.get('interactive')} modal={options.get('modal')} "
+          f"token={options['handle_token']}", flush=True)
+    base = "/org/freedesktop/portal/desktop/request/" + sender[1:].replace(".", "_")
+    request = f"{base}/{options['handle_token']}" if MODE != "other" else f"{base}/alt{calls}"
+    results = {"uri": GLib.Variant("s", URI.format(n=calls))} if URI != "-" else {}
+
+    def emit():
+        conn.emit_signal(None, request, "org.freedesktop.portal.Request", "Response",
+                         GLib.Variant("(ua{sv})", (CODE, results)))
+        return False
+
+    if MODE == "early":
+        emit()
+        conn.flush_sync(None)
+    invocation.return_value(GLib.Variant("(o)", (request,)))
+    if MODE == "twice":
+        GLib.timeout_add(30, emit)
+        GLib.timeout_add(60, emit)
+    elif MODE != "early":
+        GLib.timeout_add(50, emit)
+
+
+def get_property(conn, sender, path, iface, name):
+    return GLib.Variant("u", 2)
+
+
+loop = GLib.MainLoop()
+bus = Gio.bus_get_sync(Gio.BusType.SESSION)
+bus.register_object("/org/freedesktop/portal/desktop", INFO, call, get_property, None)
+Gio.bus_own_name_on_connection(bus, "org.freedesktop.portal.Desktop", 0,
+                               lambda conn, name: print("READY", flush=True),
+                               lambda conn, name: loop.quit())    # Name nicht (mehr) belegt
+loop.run()
+sys.exit(1)
diff --git a/tests/gui/test_gui_screenshot_portal.py b/tests/gui/test_gui_screenshot_portal.py
new file mode 100644
index 0000000..a30867d
--- /dev/null
+++ b/tests/gui/test_gui_screenshot_portal.py
@@ -0,0 +1,224 @@
+"""Bildschirmfoto über das XDG-Portal (Etappe 3d-2b): Hilfsfunktionen und D-Bus-Ablauf –
+gegen ein nachgebautes Portal auf einem privaten Bus, nie gegen das echte."""
+import functools
+import select
+import shutil
+import subprocess
+import time
+import uuid
+from pathlib import Path
+
+import pytest
+from PySide6.QtDBus import QDBusConnection, QDBusMessage
+
+from labelwerk.gui import screenshot
+from labelwerk.gui.screenshot import ScreenshotPortal, error_text, parse_response, request_path
+
+FAKE = Path(__file__).with_name("fake_portal.py")
+SYSTEM_PYTHON = "/usr/bin/python3"
+START_TIMEOUT_S = 10
+
+
+# --- Hilfsfunktionen ----------------------------------------------------------------
+def test_request_path_from_unique_name():
+    assert request_path(":1.42", "labelwerk_ab12") == \
+        "/org/freedesktop/portal/desktop/request/1_42/labelwerk_ab12"
+
+
+def test_response_with_file_uri_gives_decoded_path():
+    path, error = parse_response(0, {"uri": "file:///home/x/Bilder/Bild%20vom%20Gr%C3%BCn.png"})
+    assert path == Path("/home/x/Bilder/Bild vom Grün.png") and error is None
+
+
+def test_cancelled_response_is_silent():
+    assert parse_response(1, {}) == (None, None)
+
+
+@pytest.mark.parametrize("code, results", [
+    (2, {}),                                         # Portal: anderer Fehler/abgelehnt
+    (0, {}),                                         # Erfolg ohne Datei
+    (0, {"uri": "https://example.org/bild.png"}),    # keine lokale Datei
+    (7, {"uri": "file:///tmp/a.png"}),               # unbekannter Code
+])
+def test_failed_responses_give_german_error(code, results):
+    path, error = parse_response(code, results)
+    assert path is None and error.startswith("Bildschirmfoto fehlgeschlagen")
+
+
+@pytest.mark.parametrize("name, text", [
+    ("org.freedesktop.DBus.Error.ServiceUnknown", "kein Bildschirmfoto-Portal gefunden"),
+    ("org.freedesktop.DBus.Error.UnknownMethod", "kein Bildschirmfoto-Portal gefunden"),
+    ("org.freedesktop.DBus.Error.NoReply", "das Portal antwortet nicht"),
+    ("org.freedesktop.portal.Error.NotAllowed", "vom System nicht erlaubt"),
+    ("org.example.Irgendwas", "Fehler des Portals"),
+    ("", "Fehler des Portals"),
+])
+def test_dbus_errors_are_german(name, text):
+    assert error_text(name) == f"Bildschirmfoto fehlgeschlagen – {text}"
+
+
+# --- ohne Portal ----------------------------------------------------------------------
+def test_tests_never_reach_the_session_bus():
+    assert not screenshot.session_bus().isConnected()
+    assert not QDBusConnection.sessionBus().isConnected()     # conftest: Adresse ins Leere
+
+
+def test_without_bus_portal_is_unavailable_and_take_reports_error(qtbot):
+    portal = ScreenshotPortal()
+    assert not portal.available()
+    with qtbot.waitSignal(portal.finished, timeout=1000) as signal:
+        portal.take()
+    path, error = signal.args
+    assert path is None and error.startswith("Bildschirmfoto fehlgeschlagen")
+
+
+# --- privater Bus mit nachgebautem Portal ------------------------------------------
+@functools.cache
+def _has_gio() -> bool:
+    try:
+        return subprocess.run([SYSTEM_PYTHON, "-I", "-c", "from gi.repository import Gio"],
+                              capture_output=True, timeout=10).returncode == 0
+    except (OSError, subprocess.TimeoutExpired):
+        return False
+
+
+# Eigene Bus-Konfiguration OHNE Service-Verzeichnisse: die Sitzungs-Standardkonfiguration würde
+# beim Aufruf das echte Portal des Systems auf dem Testbus starten (Auswahl auf dem Bildschirm)
+BUS_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
+ "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
+<busconfig>
+  <type>session</type>
+  <listen>unix:tmpdir=/tmp</listen>
+  <auth>EXTERNAL</auth>
+  <policy context="default">
+    <allow send_destination="*" eavesdrop="true"/>
+    <allow eavesdrop="true"/>
+    <allow own="*"/>
+  </policy>
+</busconfig>
+"""
+
+
+def _read_line(proc: subprocess.Popen) -> str:
+    """Erste Zeile der Ausgabe, höchstens ``START_TIMEOUT_S`` warten ("" = keine)."""
+    ready, _, _ = select.select([proc.stdout], [], [], START_TIMEOUT_S)
+    return proc.stdout.readline().strip() if ready else ""
+
+
+def _stop(proc: subprocess.Popen) -> None:
+    proc.terminate()
+    try:
+        proc.wait(5)
+    except subprocess.TimeoutExpired:
+        proc.kill()
+        proc.wait(5)
+
+
+@pytest.fixture
+def private_bus(tmp_path):
+    """Eigener D-Bus-Daemon nur für den Test: (Adresse, Verbindung); startet keine Dienste."""
+    if not (shutil.which("dbus-daemon") and _has_gio()):
+        pytest.skip("dbus-daemon oder PyGObject (System-Python) fehlt")
+    config = tmp_path / "bus.conf"
+    config.write_text(BUS_CONFIG)
+    daemon = subprocess.Popen(["dbus-daemon", f"--config-file={config}", "--nofork",
+                               "--print-address"], stdout=subprocess.PIPE, text=True)
+    name = f"labelwerk-test-{uuid.uuid4().hex}"
+    try:
+        address = _read_line(daemon)
+        assert address, "dbus-daemon startet nicht"
+        bus = QDBusConnection.connectToBus(address, name)
+        assert bus.isConnected(), address
+        names = bus.call(QDBusMessage.createMethodCall(
+            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
+            "ListActivatableNames")).arguments()[0]
+        assert names == ["org.freedesktop.DBus"], names       # nichts auf dem Testbus startbar
+        yield address, bus
+    finally:
+        QDBusConnection.disconnectFromBus(name)
+        _stop(daemon)
+
+
+@pytest.fixture
+def fake_portal(private_bus):
+    """Nachgebautes Portal starten: ``fake_portal(art, code, uri) -> Prozess`` (Ausgabe: CALL …)."""
+    address, _ = private_bus
+    started = []
+
+    def start(mode="normal", code=0, uri="file:///tmp/Bild%20%C3%A4.png"):
+        proc = subprocess.Popen([SYSTEM_PYTHON, "-I", str(FAKE), mode, str(code), uri],
+                                env={"DBUS_SESSION_BUS_ADDRESS": address},
+                                stdout=subprocess.PIPE, text=True)
+        started.append(proc)
+        assert _read_line(proc) == "READY"
+        return proc
+
+    yield start
+    for proc in started:
+        _stop(proc)
+
+
+def _take(qtbot, portal):
+    with qtbot.waitSignal(portal.finished, timeout=5000) as signal:
+        portal.take()
+    return signal.args
+
+
+def test_portal_on_private_bus_delivers_the_file(qtbot, private_bus, fake_portal):
+    fake = fake_portal()
+    portal = ScreenshotPortal(private_bus[1])
+    assert portal.available()
+    assert _take(qtbot, portal) == [Path("/tmp/Bild ä.png"), None]
+    call = _read_line(fake)
+    assert "interactive=True modal=True token=labelwerk_" in call
+    assert portal._request is None and portal._path is None          # Abo gelöst
+
+
+def test_portal_on_private_bus_cancel(qtbot, private_bus, fake_portal):
+    fake_portal(code=1, uri="-")
+    assert _take(qtbot, ScreenshotPortal(private_bus[1])) == [None, None]
+
+
+def test_answer_before_the_call_returns_is_not_lost(qtbot, private_bus, fake_portal):
+    """Das Portal darf schon antworten, bevor der Aufruf zurückkommt – darum vorher abonniert."""
+    fake_portal("early")
+    assert _take(qtbot, ScreenshotPortal(private_bus[1])) == [Path("/tmp/Bild ä.png"), None]
+
+
+def test_older_portal_with_own_request_path(qtbot, private_bus, fake_portal):
+    fake_portal("other")
+    assert _take(qtbot, ScreenshotPortal(private_bus[1])) == [Path("/tmp/Bild ä.png"), None]
+
+
+def test_two_answers_give_one_result(qtbot, private_bus, fake_portal):
+    fake_portal("twice", uri="file:///tmp/a.png")
+    portal = ScreenshotPortal(private_bus[1])
+    results = []
+    portal.finished.connect(lambda *args: results.append(args))
+    portal.take()
+    qtbot.waitUntil(lambda: bool(results), timeout=5000)
+    qtbot.wait(200)
+    assert results == [(Path("/tmp/a.png"), None)]
+
+
+def test_new_take_drops_the_open_one_even_with_queued_answer(qtbot, private_bus, fake_portal):
+    """Die Antwort der ersten Aufnahme steht schon in der Ereignisschlange (Qt verarbeitet
+    während ``sleep`` nichts) – gemeldet wird trotzdem nur die zweite."""
+    fake_portal(uri="file:///tmp/bild{n}.png")
+    portal = ScreenshotPortal(private_bus[1])
+    results = []
+    portal.finished.connect(lambda *args: results.append(args))
+    portal.take()
+    time.sleep(0.3)
+    portal.take()
+    qtbot.waitUntil(lambda: bool(results), timeout=5000)
+    qtbot.wait(200)
+    assert results == [(Path("/tmp/bild2.png"), None)]
+
+
+def test_portal_missing_on_private_bus(qtbot, private_bus):
+    portal = ScreenshotPortal(private_bus[1])
+    assert not portal.available()
+    path, error = _take(qtbot, portal)
+    assert (path, error) == (None, "Bildschirmfoto fehlgeschlagen – kein Bildschirmfoto-Portal "
+                                   "gefunden")
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Alle GUI-Tests scheitern beim Aufbau (die autouse-Fixture `no_session_bus` ersetzt `labelwerk.gui.screenshot.session_bus`, das Modul fehlt noch), die übrigen Tests bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/.github/workflows/tests.yml b/.github/workflows/tests.yml
index ad69cbe..d6325ad 100644
--- a/.github/workflows/tests.yml
+++ b/.github/workflows/tests.yml
@@ -11,7 +11,7 @@ jobs:
       - uses: actions/setup-python@v5
         with:
           python-version: ${{ matrix.python }}
-      - run: sudo apt-get install -y fonts-dejavu-core libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3
+      - run: sudo apt-get install -y fonts-dejavu-core libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 dbus python3-gi
       - run: pip install -e ".[dev]"
       - run: pytest -q
         env:
diff --git a/src/labelwerk/gui/screenshot.py b/src/labelwerk/gui/screenshot.py
new file mode 100644
index 0000000..be446f0
--- /dev/null
+++ b/src/labelwerk/gui/screenshot.py
@@ -0,0 +1,171 @@
+"""Bildschirmfoto über das XDG-Desktop-Portal (``org.freedesktop.portal.Screenshot``).
+
+Die Auswahl (Bereich, Fenster, Bildschirm) zeigt der Desktop (``interactive``); das Portal
+antwortet asynchron mit dem Signal ``Response`` am Request-Objekt, dessen Pfad sich aus dem
+Busnamen und einem eigenen ``handle_token`` ergibt – darum wird es vor dem Aufruf abonniert.
+Ohne D-Bus testbar: ``request_path``, ``parse_response``, ``error_text``. Aufrufe gehen als
+einzelne Nachrichten raus (``QDBusInterface`` würde beim Anlegen blockierend introspektieren).
+"""
+from __future__ import annotations
+
+import uuid
+from pathlib import Path
+from urllib.parse import unquote, urlparse
+
+from PySide6.QtCore import SLOT, QObject, Signal, Slot
+from PySide6.QtDBus import QDBus, QDBusConnection, QDBusMessage
+
+SERVICE = "org.freedesktop.portal.Desktop"
+OBJECT = "/org/freedesktop/portal/desktop"
+INTERFACE = "org.freedesktop.portal.Screenshot"
+REQUEST = "org.freedesktop.portal.Request"
+AVAILABLE_TIMEOUT_MS = 5_000      # Portal da? (startet es erst, dauert das meist < 1 s)
+CALL_TIMEOUT_MS = 10_000          # Antwort auf den Aufruf selbst (die Auswahl dauert beliebig)
+FAILED = "Bildschirmfoto fehlgeschlagen"
+_RESPONSE_SLOT = SLOT("response(uint,QVariantMap)")
+_NO_PORTAL = ("ServiceUnknown", "NameHasNoOwner", "UnknownObject", "UnknownInterface",
+              "UnknownMethod", "ServiceNotFound")
+_NO_ANSWER = ("NoReply", "Timeout", "TimedOut")
+
+
+def session_bus() -> QDBusConnection:
+    """Sitzungsbus (in Tests ersetzt – kein Test erreicht das echte Portal)."""
+    return QDBusConnection.sessionBus()
+
+
+def request_path(unique_name: str, token: str) -> str:
+    """Pfad des Request-Objekts, an dem das Portal antwortet (Busname „:1.42“ → „1_42“)."""
+    sender = unique_name.lstrip(":").replace(".", "_")
+    return f"{OBJECT}/request/{sender}/{token}"
+
+
+def parse_response(code: int, results: dict) -> tuple[Path | None, str | None]:
+    """Antwort des Portals → (Pfad der Bilddatei, Fehlermeldung); (None, None) = abgebrochen."""
+    if code == 1:
+        return None, None
+    if code != 0:
+        return None, f"{FAILED} – vom System abgelehnt oder abgebrochen"
+    uri = urlparse(str(results.get("uri") or ""))
+    if uri.scheme != "file" or not uri.path:
+        return None, f"{FAILED} – keine Bilddatei erhalten"
+    return Path(unquote(uri.path)), None
+
+
+def error_text(error_name: str) -> str:
+    """D-Bus-Fehlername (z. B. „org.freedesktop.DBus.Error.ServiceUnknown“) → deutsche Meldung
+    (die Fehlertexte von D-Bus sind englisch)."""
+    short = error_name.rsplit(".", 1)[-1]
+    if short in _NO_PORTAL:
+        return f"{FAILED} – kein Bildschirmfoto-Portal gefunden"
+    if short in _NO_ANSWER:
+        return f"{FAILED} – das Portal antwortet nicht"
+    if short == "NotAllowed":
+        return f"{FAILED} – vom System nicht erlaubt"
+    return f"{FAILED} – Fehler des Portals"
+
+
+class _Request(QObject):
+    """Empfänger der Antwort einer Aufnahme. QtDBus stellt Signale über die Ereignisschlange
+    zu: eine schon eingereihte Antwort einer verworfenen Aufnahme kommt auch nach dem Abmelden
+    noch an – sie zählt nur, solange ihr Empfänger der aktuelle ist."""
+
+    def __init__(self, portal: ScreenshotPortal):
+        super().__init__(portal)
+        self._portal = portal
+
+    @Slot("uint", "QVariantMap")
+    def response(self, code: int, results: dict) -> None:
+        self._portal._response(self, code, results)
+
+
+class ScreenshotPortal(QObject):
+    """Ein Bildschirmfoto je ``take()``; Ergebnis genau einmal über ``finished``:
+    (Pfad | None, Fehlermeldung | None), (None, None) = abgebrochen."""
+
+    finished = Signal(object, object)
+
+    def __init__(self, bus: QDBusConnection | None = None, parent: QObject | None = None):
+        super().__init__(parent)
+        self._bus = bus
+        self._request: _Request | None = None   # Empfänger der offenen Aufnahme
+        self._spent: list[_Request] = []        # frühere Empfänger, beim nächsten take() gelöscht
+        self._path: str | None = None           # dafür abonnierter Request-Pfad
+
+    def bus(self) -> QDBusConnection:
+        return self._bus if self._bus is not None else session_bus()
+
+    def _call(self, path: str, interface: str, method: str, *args,
+              timeout: int = CALL_TIMEOUT_MS) -> QDBusMessage:
+        message = QDBusMessage.createMethodCall(SERVICE, path, interface, method)
+        message.setArguments(list(args))
+        return self.bus().call(message, QDBus.CallMode.Block, timeout)
+
+    def available(self) -> bool:
+        """Sitzungsbus erreichbar und Portal mit Schnittstelle Screenshot vorhanden."""
+        if not self.bus().isConnected():
+            return False
+        reply = self._call(OBJECT, "org.freedesktop.DBus.Properties", "Get", INTERFACE,
+                           "version", timeout=AVAILABLE_TIMEOUT_MS)
+        return reply.type() == QDBusMessage.MessageType.ReplyMessage
+
+    def take(self) -> None:
+        """Auswahl des Desktops öffnen; das Ergebnis kommt über ``finished`` – bei Fehlern vor
+        der Auswahl (kein Bus, kein Portal) noch während dieses Aufrufs. Eine noch offene
+        Aufnahme wird verworfen (ihre Auswahl geschlossen, ihre Antwort nicht mehr gemeldet)."""
+        if self._path is not None:
+            self.bus().send(QDBusMessage.createMethodCall(SERVICE, self._path, REQUEST, "Close"))
+        self._drop()
+        for request in self._spent:          # nicht früher: Löschen eines Empfängers, dessen
+            request.deleteLater()             # Antwort gerade zugestellt wird, stürzt ab (SIGBUS)
+        self._spent.clear()
+        bus = self.bus()
+        if not bus.isConnected():
+            self.finished.emit(None, f"{FAILED} – keine Verbindung zum Sitzungsbus")
+            return
+        token = f"labelwerk_{uuid.uuid4().hex}"
+        self._request = _Request(self)
+        if not self._subscribe(request_path(bus.baseService(), token)):
+            return
+        reply = self._call(OBJECT, INTERFACE, "Screenshot", "",
+                           {"handle_token": token, "interactive": True, "modal": True})
+        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
+            self._finish(None, error_text(reply.errorName()))
+            return
+        try:
+            handle = reply.arguments()[0].path()
+        except (IndexError, AttributeError):
+            self._finish(None, f"{FAILED} – unerwartete Antwort des Portals")
+            return
+        if handle != self._path:            # ältere Portale: eigener Pfad
+            self._subscribe(handle)
+
+    def _subscribe(self, path: str) -> bool:
+        """Antwort am Pfad ``path`` abonnieren (ein älteres wird gelöst); scheitert das, ist die
+        Aufnahme mit Fehler beendet – sonst käme nie eine Antwort."""
+        self._unsubscribe()
+        if not self.bus().connect(SERVICE, path, REQUEST, "Response", self._request,
+                                  _RESPONSE_SLOT):
+            self._finish(None, f"{FAILED} – Antwort des Portals nicht abonnierbar")
+            return False
+        self._path = path
+        return True
+
+    def _unsubscribe(self) -> None:
+        if self._path is not None:
+            self.bus().disconnect(SERVICE, self._path, REQUEST, "Response", self._request,
+                                  _RESPONSE_SLOT)
+            self._path = None
+
+    def _drop(self) -> None:
+        self._unsubscribe()
+        if self._request is not None:
+            self._spent.append(self._request)
+            self._request = None
+
+    def _response(self, request: _Request, code: int, results: dict) -> None:
+        if request is self._request:
+            self._finish(*parse_response(code, results))
+
+    def _finish(self, path: Path | None, error: str | None) -> None:
+        self._drop()
+        self.finished.emit(path, error)
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `1357 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/tests.yml src/labelwerk/gui/screenshot.py tests/gui/conftest.py tests/gui/fake_portal.py tests/gui/test_gui_screenshot_portal.py
git commit -m "Bildschirmfoto: Portal-Anbindung (gui/screenshot.py), Tests gegen nachgebautes Portal auf privatem Bus

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: GUI – Bildschirmfoto im Reiter Bild

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/labelwerk/gui/image_import.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/image.py`
- Modify: `src/labelwerk/shortcuts.py`
- Create: `tests/gui/test_gui_screenshot.py`

**Interfaces / Produces:** Aktion `image.screenshot` „Bildschirmfoto einfügen“ (ohne Standardkürzel); `ImagePanel.screenshot` (Knopf BILDSCHIRMFOTO); `MainWindow.insert_screenshot()`, Haken `screenshot_available()`/`take_screenshot()`, `screenshot_finished(path, error)`, Konstanten `NO_SCREENSHOT`, `HIDE_DELAY_MS`, `RESTORE_TIMEOUT_MS`; `image_import.SCREENSHOT`, `image_import.load_screenshot(path) -> (Bild, dpi)`; `_insert_picture(..., dpi=DPI)`; Doku CLAUDE.md.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_screenshot.py b/tests/gui/test_gui_screenshot.py
new file mode 100644
index 0000000..3970bbc
--- /dev/null
+++ b/tests/gui/test_gui_screenshot.py
@@ -0,0 +1,239 @@
+"""Werkzeug Bild – Bildschirmfoto (Etappe 3d-2b): Ablauf im Hauptfenster. Das Portal ist durch
+Haken ersetzt (``screenshot_available``/``take_screenshot``); ohne Ersatz sieht die GUI keinen
+Sitzungsbus (``conftest.no_session_bus``) – nie das echte Portal."""
+import pytest
+from PIL import Image, ImageDraw
+
+from labelwerk import shortcuts
+from labelwerk.document import Document, ImageObject, TextObject
+from labelwerk.gui import main_window
+from labelwerk.gui.main_window import NO_SCREENSHOT, SCREENSHOT, MainWindow
+from labelwerk.settings import Settings
+
+MM = 300 / 25.4
+
+
+def _window(qtbot, doc=None, **settings):
+    win = MainWindow(doc=doc or Document("62", length_mm=40,
+                                         objects=[TextObject("Eins", size_pt=14, x_mm=4, y_mm=4)]),
+                     settings=Settings(check_media_on_start=False, **settings))
+    qtbot.addWidget(win)
+    win.show()
+    return win
+
+
+def _shot(tmp_path, w=240, h=120, dpi=72):
+    """Bildschirmfoto-Datei: weißer Rand, schwarzes Feld (Datei mit DPI-Angabe, die nicht gilt)."""
+    img = Image.new("RGB", (w, h), "white")
+    ImageDraw.Draw(img).rectangle((20, 20, w - 21, h - 21), fill="black")
+    path = tmp_path / "Bildschirmfoto vom 2026-10-18.png"
+    img.save(path, dpi=(dpi, dpi))
+    return path
+
+
+@pytest.fixture
+def portal(monkeypatch):
+    """Ersetztes Portal: verfügbar; ``calls`` zählt die Aufnahmen."""
+    class Fake:
+        available = True
+        calls = 0
+    fake = Fake()
+    monkeypatch.setattr(MainWindow, "screenshot_available", lambda self: fake.available)
+
+    def take(self):
+        fake.calls += 1
+    monkeypatch.setattr(MainWindow, "take_screenshot", take)
+    return fake
+
+
+def _start(win, qtbot, portal):
+    calls = portal.calls
+    win.panel("image").screenshot.click()
+    qtbot.waitUntil(lambda: portal.calls == calls + 1, timeout=2000)
+
+
+# --- Aktion und Knopf ----------------------------------------------------------------
+def test_screenshot_action_has_no_default_key(qtbot):
+    entry = shortcuts.action("image.screenshot")
+    assert (entry.name, entry.default, entry.scope) == ("Bildschirmfoto einfügen", "", "canvas")
+    win = _window(qtbot)
+    assert win.shortcut_actions["image.screenshot"] in win.canvas.actions()
+    button = win.panel("image").screenshot
+    assert button.text() == "BILDSCHIRMFOTO" and button.isEnabled()
+    assert button.toolTip() == "Bildschirmfoto einfügen"
+
+
+def test_assigned_key_shows_in_tooltip(qtbot):
+    win = _window(qtbot, shortcuts={"image.screenshot": "Ctrl+Alt+S"})
+    assert "Ctrl+Alt+S" in win.panel("image").screenshot.toolTip()
+
+
+# --- Ablauf ------------------------------------------------------------------------
+def test_window_hides_then_portal_is_called(qtbot, portal):
+    win = _window(qtbot)
+    win.panel("image").screenshot.click()
+    assert not win.isVisible() and portal.calls == 0          # erst ausblenden …
+    qtbot.waitUntil(lambda: portal.calls == 1, timeout=2000)  # … dann die Auswahl
+    assert not win.isVisible()
+    assert not win.shortcut_actions["image.screenshot"].isEnabled()
+
+
+def test_screenshot_is_inserted_at_300_dpi_and_selected(qtbot, portal, tmp_path):
+    win = _window(qtbot)
+    _start(win, qtbot, portal)
+    win.screenshot_finished(_shot(tmp_path), None)
+    assert win.isVisible() and win.shortcut_actions["image.screenshot"].isEnabled()
+    obj = win.doc.objects[1]
+    assert isinstance(obj, ImageObject) and obj.source == SCREENSHOT == "Bildschirmfoto"
+    assert obj.dpi == 300                                     # DPI-Angabe der Datei gilt nicht
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((200 / MM, 80 / MM), abs=0.01)   # zugeschnitten
+    assert win.canvas.selection() == [1]
+    win.undo()
+    assert len(win.doc.objects) == 1                          # ein Rückgängig-Schritt
+
+
+def test_screenshot_follows_crop_setting(qtbot, portal, tmp_path):
+    win = _window(qtbot, image_crop=False)
+    _start(win, qtbot, portal)
+    win.screenshot_finished(_shot(tmp_path), None)
+    obj = win.doc.objects[1]
+    assert obj.crop is None and obj.w_mm == pytest.approx(240 / MM, abs=0.01)
+
+
+def test_screenshot_follows_rotate_setting(qtbot, portal, tmp_path):
+    """Endlosband 62 mm, automatische Länge: breites Foto mit „drehen“ gedreht 1:1."""
+    doc = Document("62", objects=[TextObject("Absender", size_pt=10, x_mm=3, y_mm=3)])
+    win = _window(qtbot, doc, image_rotate=True)
+    _start(win, qtbot, portal)
+    win.screenshot_finished(_shot(tmp_path, 867, 442), None)
+    obj = win.doc.objects[1]
+    assert obj.rotation == 90 and obj.w_mm == pytest.approx(827 / MM, abs=0.01)
+    assert "Bild um 90° gedreht" in win.result.text()
+
+
+def test_huge_screenshot_keeps_its_size(qtbot, portal, tmp_path):
+    """Über zwei 4K-Bildschirme: beim Laden auf 6000 px begrenzt – die Größe bleibt 1:1."""
+    win = _window(qtbot)
+    _start(win, qtbot, portal)
+    win.screenshot_finished(_shot(tmp_path, 7680, 400), None)
+    obj = win.doc.objects[1]
+    assert obj.natural_mm()[0] == pytest.approx(7640 / MM, rel=0.002)
+
+
+def test_cancel_inserts_nothing_and_says_nothing(qtbot, portal):
+    win = _window(qtbot)
+    _start(win, qtbot, portal)
+    win.screenshot_finished(None, None)
+    assert win.isVisible() and len(win.doc.objects) == 1 and win.result.text() == ""
+    assert win.shortcut_actions["image.screenshot"].isEnabled()
+
+
+def test_portal_error_is_shown(qtbot, portal):
+    win = _window(qtbot)
+    _start(win, qtbot, portal)
+    win.screenshot_finished(None, "Bildschirmfoto fehlgeschlagen – keine Bilddatei erhalten")
+    assert win.isVisible() and len(win.doc.objects) == 1
+    assert win.result.text() == "Bildschirmfoto fehlgeschlagen – keine Bilddatei erhalten"
+    assert win.result.property("state") == "error"
+    assert win.shortcut_actions["image.screenshot"].isEnabled()
+
+
+def test_unreadable_file_is_shown(qtbot, portal, tmp_path):
+    win = _window(qtbot)
+    _start(win, qtbot, portal)
+    win.screenshot_finished(tmp_path / "weg.png", None)
+    assert win.isVisible() and len(win.doc.objects) == 1
+    assert win.result.text().startswith("Bildschirmfoto: ") and "weg.png" in win.result.text()
+    assert win.result.property("state") == "error"
+
+
+def test_error_in_take_brings_window_back_at_once(qtbot, monkeypatch):
+    monkeypatch.setattr(MainWindow, "screenshot_available", lambda self: True)
+
+    def broken(self):
+        raise RuntimeError("kaputt")
+    monkeypatch.setattr(MainWindow, "take_screenshot", broken)
+    win = _window(qtbot)
+    win.panel("image").screenshot.click()
+    qtbot.waitUntil(win.isVisible, timeout=2000)
+    assert win.result.text() == "Bildschirmfoto fehlgeschlagen – kaputt"
+    assert win.shortcut_actions["image.screenshot"].isEnabled()
+    assert not win._restore_timer.isActive()
+
+
+def test_real_portal_object_answers_through_the_window(qtbot, monkeypatch):
+    """Echtes ``ScreenshotPortal`` (ohne Sitzungsbus in Tests): seine Antwort kommt über
+    ``finished`` im Hauptfenster an – noch während ``take()``."""
+    monkeypatch.setattr(MainWindow, "screenshot_available", lambda self: True)
+    win = _window(qtbot)
+    win.panel("image").screenshot.click()
+    qtbot.waitUntil(win.isVisible, timeout=2000)
+    assert win.result.text() == ("Bildschirmfoto fehlgeschlagen – keine Verbindung zum "
+                                 "Sitzungsbus")
+    assert win.shortcut_actions["image.screenshot"].isEnabled()
+    assert not win._restore_timer.isActive()
+
+
+def test_app_does_not_quit_while_hidden(qtbot, portal, qapp):
+    assert qapp.quitOnLastWindowClosed()
+    win = _window(qtbot)
+    _start(win, qtbot, portal)
+    assert not qapp.quitOnLastWindowClosed()
+    win.screenshot_finished(None, None)
+    assert qapp.quitOnLastWindowClosed()
+
+
+def test_closing_during_screenshot_ends_it(qtbot, portal, tmp_path, monkeypatch):
+    monkeypatch.setattr(main_window, "RESTORE_TIMEOUT_MS", 100)
+    win = _window(qtbot)
+    win.panel("image").screenshot.click()
+    win.close()                                    # noch in der Pause vor der Auswahl
+    qtbot.wait(main_window.HIDE_DELAY_MS + 200)
+    assert portal.calls == 0 and not win.isVisible()
+    win.screenshot_finished(_shot(tmp_path), None)
+    assert len(win.doc.objects) == 1
+
+
+def test_without_portal_window_stays_and_hint_names_clipboard(qtbot):
+    """Ohne Ersatz: kein Sitzungsbus in Tests → wie ein System ohne Portal."""
+    win = _window(qtbot)
+    win.panel("image").screenshot.click()
+    assert win.isVisible()
+    assert win.result.text() == NO_SCREENSHOT and "Strg+V" in NO_SCREENSHOT
+    assert win.result.property("state") == "error"
+
+
+def test_second_click_while_taking_does_nothing(qtbot, portal):
+    win = _window(qtbot)
+    _start(win, qtbot, portal)
+    win.insert_screenshot()
+    qtbot.wait(main_window.HIDE_DELAY_MS + 100)
+    assert portal.calls == 1
+
+
+def test_timeout_shows_window_and_late_answer_still_inserts(qtbot, portal, tmp_path,
+                                                            monkeypatch):
+    monkeypatch.setattr(main_window, "RESTORE_TIMEOUT_MS", 100)
+    win = _window(qtbot)
+    _start(win, qtbot, portal)
+    qtbot.waitUntil(win.isVisible, timeout=2000)
+    assert win.shortcut_actions["image.screenshot"].isEnabled()
+    win.screenshot_finished(_shot(tmp_path), None)
+    assert len(win.doc.objects) == 2
+    win.screenshot_finished(_shot(tmp_path), None)            # nur die erste Antwort zählt
+    assert len(win.doc.objects) == 2
+
+
+def test_answer_without_open_screenshot_is_ignored(qtbot, tmp_path):
+    win = _window(qtbot)
+    win.screenshot_finished(_shot(tmp_path), None)
+    assert len(win.doc.objects) == 1
+
+
+def test_screenshot_ends_text_editing_first(qtbot, portal):
+    win = _window(qtbot)
+    win.canvas.set_selection([0])
+    win.edit_selected()
+    assert win.edit_session.active
+    _start(win, qtbot, portal)
+    assert not win.edit_session.active
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests in `tests/gui/test_gui_screenshot.py` schlagen fehl (ImportError `NO_SCREENSHOT`/`SCREENSHOT` bzw. fehlende Aktion), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 5ff5706..b55990c 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -16,7 +16,8 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - Freies Platzieren (Etappe 3d-1): mehrere Objekte, Auswahl, Ziehen mit Einrasten, Anfasser, Bearbeitungsleiste, Reiter Layout, Drehen, Reihenfolge, Zwischenablage, Rückgängig, Tastenkürzel änderbar (Einstellungen → Tastenkürzel).
 - Direkt auf dem Etikett schreiben (Etappe 3d-1b): Schreibmodus (Text anlegen + Klick bzw. Doppelklick, Esc/Klick daneben beendet), Schreibmarke/Markierung aus dem Kern-Zeilensatz, Markieren mit Maus und Tastatur, eine Bearbeitung = ein Rückgängig-Schritt, Rahmen wächst an der Kante der Textposition; Feld INHALT entfällt.
 - Bild-Objekt (Etappe 3d-2a): Werkzeug Bild – aus Datei (PNG/JPG/GIF/BMP/WebP/SVG/PDF-Seite), Zwischenablage, Ablegen; 1:1, automatisch zugeschnitten, zu große eingepasst (Einstellungen: automatisch zuschneiden an, drehen statt verkleinern aus); Umwandlung Strich/Foto, Schwelle, Umkehren, Zuschnitt, Originalgröße, Seitenverhältnis, Drehen; Strg+V: Objekte (MIME application/x-labelwerk-objects) › lokale Dateien › Text als Textrahmen › Bild.
-- 1335 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- Bildschirmfoto (Etappe 3d-2b): Knopf BILDSCHIRMFOTO im Reiter Bild – labelwerk blendet sich aus, der Desktop zeigt seine Auswahl (XDG-Portal), das Bild kommt mit 300 dpi aufs Etikett; ohne Portal Hinweis auf Zwischenablage + Strg+V.
+- 1376 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -67,14 +68,19 @@ src/labelwerk/
     main_window.py  Hauptfenster, Werkzeug- und Bearbeitungsleiste, Statusleiste; Aktionen auf der Auswahl, Druck-Rückfragen;
                     shortcut_actions (Aktions-ID → QAction); rendert über render.Renderer; leere Textrahmen entfallen beim Abwählen;
                     Bilder einfügen (insert_image_files, paste_image, Ablegen; Dialoge ask_image_file/ask_pdf_page ersetzbar),
-                    Strg+V nach Zwischenablage des Systems (eigene Kopie › Dateien › Text › Bild; Stand beim Ändern gemerkt,
+                    Bildschirmfoto (insert_screenshot: ausblenden, Portal, wieder zeigen; Haken screenshot_available/take_screenshot,
+                    Antwort screenshot_finished; 60 s Sicherheitsnetz), Strg+V nach Zwischenablage des Systems (eigene Kopie › Dateien › Text › Bild; Stand beim Ändern gemerkt,
                     Daten erst beim Einfügen gelesen); Auswahl zeigt Panel der Objektart
     tools.py        Werkzeug-Registry (Papier, Text, Bild, Layout; neue Werkzeuge als Eintrag)
     panels/         Eigenschaften-Panels je Werkzeug (paper, text und image mit Bereich Position)
-    panels/image.py Reiter Bild: Aus Datei/Aus Zwischenablage, Quelle, Strich/Foto, Schwelle (Regler = ein Schritt), Umkehren,
+    panels/image.py Reiter Bild: Aus Datei/Aus Zwischenablage/Bildschirmfoto, Quelle, Strich/Foto, Schwelle (Regler = ein Schritt), Umkehren,
                     Zuschnitt (Fallback ohne Inhalt: ganzes Bild + Hinweis), Originalgröße 1:1, Seitenverhältnis, Drehen (Aktionen), Position
     image_import.py Bilder beschaffen: load (SVG per QSvgRenderer bei 300 dpi, Maße mit Einheit selbst gelesen: svg_size; sonst files.load_image), page_count,
                     mime_image/mime_files/mime_text (Zwischenablage, Ablegen; ohne Auflösung 300 dpi), MIME_OBJECTS
+    screenshot.py   Bildschirmfoto über das XDG-Portal (QtDBus, interaktiv): ScreenshotPortal (available, take, Signal
+                    finished(Pfad | None, Fehler | None); Empfänger je Aufnahme, veraltete Antworten zählen nicht), request_path,
+                    parse_response, error_text; GUI-Tests: Sitzungsbus-Adresse ins Leere + session_bus ersetzt (conftest);
+                    Tests gegen tests/gui/fake_portal.py auf privatem dbus-daemon mit eigener Config ohne servicedir
     panels/position.py PositionSection: Bereich Position (X/Y/B/H in mm), show_frame(rect, editable_size), Signal edited(key, wert)
     panels/layout.py Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Knöpfe = Aktionen)
     canvas.py       Etikett in echter Größe, Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom;
@@ -110,6 +116,7 @@ Abhängigkeiten: `brother_ql-inventree>=1.3` (GPLv3+, Import als `brother_ql`),
 - Gruppe `lp` gilt erst nach neuer Anmeldung; bis dahin im Terminal `newgrp lp`.
 - Benutzer braucht Gruppe `lp` für `/dev/usb/lpN` (`crw-rw---- root lp`). Erledigt.
 - `Replace media error` = angefordertes Etikett passt nicht zur eingelegten Rolle (Drucker erkennt die DK-Rolle per Sensor).
+- D-Bus in Tests: nie `dbus-daemon --session`/`dbus-run-session` – deren Standard-Config startet echte Dienste (Portal öffnet Auswahl auf dem Bildschirm); eigene busconfig ohne servicedir.
 - GUI-Tests: jedes Widget bei `qtbot.addWidget` anmelden (sonst Absturz beim Beenden); immer Exit-Code von pytest prüfen, nicht nur „passed“.
 - Statusabfrage (Medium prüfen): Invalidate (200 × 0x00) + ESC @ + ESC i S, Antwort 32 Bytes sofort; brother_ql-Lesen nicht verwenden (kann ohne Zeitlimit blockieren).
 - Backends: `linux_kernel` (Standard, `/dev/usb/lpN`), `pyusb` (`usb://0x04f9:0x20c0`), `network`.
@@ -127,7 +134,7 @@ labelwerk print "X1 -K3\nKlemme 24V" -l 62
 ## GUI (MVP umgesetzt)
 Desktop-GUI mit **PySide6** (LGPL, GPL-kompatibel).
 
-Nächste Schritte: Etappe 3d-2b Bildschirmfoto (XDG-Portal), danach 3d-2c Symbole/ClipArt (Roadmap 0/5).
+Nächste Schritte: Etappe 3d-2c Symbole/ClipArt (Roadmap 0/5).
 
 Anforderungen MVP:
 - Mehrzeiliges Textfeld
@@ -144,7 +151,7 @@ Umsetzung:
 - GUI bleibt dünn: Logik, die testbar ist, gehört in den Kern
 
 ## Roadmap danach
-0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (erledigt, Spec 2026-10-17-direkt-schreiben) · 3d-2a Bild (erledigt, Spec 2026-10-17-bild-objekt) · 3d-2b Bildschirmfoto · 3d-2c Symbole/ClipArt · 3c Neu/Öffnen/Speichern + Favoriten · Zierrahmen ums Etikett (P-touch „Rahmen“) · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen.
+0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (erledigt, Spec 2026-10-17-direkt-schreiben) · 3d-2a Bild (erledigt, Spec 2026-10-17-bild-objekt) · 3d-2b Bildschirmfoto (erledigt, Spec 2026-10-18-bildschirmfoto) · 3d-2c Symbole/ClipArt · 3c Neu/Öffnen/Speichern + Favoriten · Zierrahmen ums Etikett (P-touch „Rahmen“) · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen.
 1. ~~Text 90° drehen (Text längs zum Endlosband, wichtig für 12–29 mm)~~ erledigt in Etappe 1
 2. Eingelegte Rolle automatisch aus dem Druckerstatus auslesen → teilweise erledigt in Etappe 1 (GUI-Vorauswahl, `labelwerk media`); `-l auto` in der CLI fehlt noch
 3. Barcodes und QR-Codes
diff --git a/src/labelwerk/gui/image_import.py b/src/labelwerk/gui/image_import.py
index 53dc2bf..d6b67e0 100644
--- a/src/labelwerk/gui/image_import.py
+++ b/src/labelwerk/gui/image_import.py
@@ -26,6 +26,7 @@ FILE_FILTER = ("Bilder und PDF (" + " ".join(f"*{s} *{s.upper()}" for s in SUFFI
                "Alle Dateien (*)")              # Großschreibung: Kameras, Windows
 CLIPBOARD = "Zwischenablage"                    # Quelle eines eingefügten Bilds
 DROPPED = "Abgelegtes Bild"
+SCREENSHOT = "Bildschirmfoto"
 MIME_OBJECTS = "application/x-labelwerk-objects"   # kopierte Objekte (Kennung der Kopie)
 SVG_DPI = 96                                    # SVG: 1 px = 1/96 in
 
@@ -47,6 +48,16 @@ def load(path: Path, page: int = 1) -> tuple[Image.Image, float]:
     return files.load_image(path, page)
 
 
+def load_screenshot(path: Path) -> tuple[Image.Image, float]:
+    """Bildschirmfoto-Datei: (RGB-Bild, dpi) mit 1 Bildschirmpixel = 1 Druckpunkt (300 dpi) –
+    eine Auflösungsangabe der Datei gilt nicht; hat das Laden ein riesiges Foto verkleinert
+    (``imaging.limit_size``), entsprechend weniger, damit die Größe stimmt."""
+    image, _ = load(path)
+    with Image.open(path) as raw:
+        scale = max(image.size) / max(raw.size)
+    return image, DPI * scale
+
+
 def load_svg(path: Path) -> tuple[Image.Image, float]:
     """SVG bei 300 dpi auf Weiß rastern (Größe aus width/height samt Einheit, sonst Qts
     Größe/viewBox; 1 px = 1/96 in); sehr große Zeichnungen gröber, höchstens
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index bcc4818..c8070c7 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -33,11 +33,12 @@ from .actions import apply_shortcuts, build_actions
 from .canvas import Canvas
 from .history import History, restore
 from . import image_import
-from .image_import import CLIPBOARD, DROPPED, MIME_OBJECTS
+from .image_import import CLIPBOARD, DROPPED, MIME_OBJECTS, SCREENSHOT
 from .media_worker import MediaWorker
 from .panels.image import CROP_FAILED
 from .panels.text import DEFAULT_PT
 from .print_worker import PrintWorker
+from .screenshot import FAILED as SCREENSHOT_FAILED, ScreenshotPortal
 from .settings_dialog import SettingsDialog
 from .symbols import SIZE, line_icon
 from .text_edit_mode import TextEditSession
@@ -56,6 +57,10 @@ SHRUNK_HINT = "Bild auf {percent} verkleinert"                    # „37 %“
 CODES_HINT = " – Codes ggf. nicht mehr lesbar"                    # nur Strich (Codes)
 TURNED_HINT = "Bild um 90° gedreht, damit es 1:1 passt"
 NO_CLIPBOARD_IMAGE = "Kein Bild in der Zwischenablage."
+NO_SCREENSHOT = ("Bildschirmfoto nicht verfügbar (kein XDG-Portal) – mit dem System-Werkzeug in "
+                 "die Zwischenablage kopieren und mit Strg+V einfügen")
+HIDE_DELAY_MS = 300        # Bildschirmfoto: so lange nimmt der Desktop das Fenster weg
+RESTORE_TIMEOUT_MS = 60_000   # ohne Antwort des Portals kommt das Fenster danach trotzdem wieder
 # Bearbeitungsleiste: Aktion und eigenes Symbol (gui/icons); None = Trenner
 EDIT_BAR = (("tool.select", "tool-select"), ("tool.text", "tool-text"), None,
             ("edit.cut", "edit-cut"), ("edit.copy", "edit-copy"), ("edit.paste", "edit-paste"),
@@ -99,6 +104,10 @@ class MainWindow(QMainWindow):
         self._text_pastes = 0                       # Text eingefügt seit dem letzten Ändern
         self._notice: str | None = None             # Meldung zum Einfügen von Bildern
         self._image_dir = ""                        # Ordner des zuletzt eingefügten Bilds
+        self._portal: ScreenshotPortal | None = None   # Bildschirmfoto (beim ersten Gebrauch)
+        self._shooting = False                      # Fenster für ein Bildschirmfoto ausgeblendet
+        self._quit_on_close = True                  # Einstellung der App vor dem Ausblenden
+        self._shot_pending = False                  # Antwort des Portals steht noch aus
         self._merge_next = None                     # Pfeiltasten: Schritte zusammenfassen
         self._restoring = False                     # Rückgängig setzt gerade die Auswahl
         self._arranging = False                     # Auswahl wird intern umgestellt (Anlegen …)
@@ -213,6 +222,12 @@ class MainWindow(QMainWindow):
         self._printer_timer.setInterval(PRINTER_POLL_MS)
         self._printer_timer.timeout.connect(self.refresh_printer)
         self._printer_timer.start()
+        self._hide_timer = QTimer(self)              # Bildschirmfoto: erst ausblenden, dann Auswahl
+        self._hide_timer.setSingleShot(True)
+        self._hide_timer.timeout.connect(self._take_hidden)
+        self._restore_timer = QTimer(self)           # … und ohne Antwort wieder zeigen
+        self._restore_timer.setSingleShot(True)
+        self._restore_timer.timeout.connect(self._show_again)
 
         # Schreibmodus direkt auf dem Etikett (Editor des Text-Panels als Eingabepuffer)
         self.edit_session = TextEditSession(self)
@@ -263,7 +278,8 @@ class MainWindow(QMainWindow):
                     "edit.paste": self.paste, "edit.duplicate": self.duplicate_selected,
                     "tool.select": lambda: self._choose_tool("select"),
                     "tool.text": lambda: self._choose_tool("text"),
-                    "image.insert": self.insert_image_file}
+                    "image.insert": self.insert_image_file,
+                    "image.screenshot": self.insert_screenshot}
         handlers["text.start_edit"] = handlers["text.start_edit_enter"] = self.edit_selected
         for key, handler in handlers.items():
             self.shortcut_actions[key].triggered.connect(lambda _=False, h=handler: h())
@@ -922,6 +938,90 @@ class MainWindow(QMainWindow):
             return
         self._insert_picture(image, CLIPBOARD)
 
+    # --- Bildschirmfoto ------------------------------------------------------
+    def _screenshot_portal(self) -> ScreenshotPortal:
+        if self._portal is None:
+            self._portal = ScreenshotPortal(parent=self)
+            self._portal.finished.connect(self.screenshot_finished)
+        return self._portal
+
+    def screenshot_available(self) -> bool:
+        """Gibt es das Bildschirmfoto-Portal? (in Tests ersetzbar)"""
+        return self._screenshot_portal().available()
+
+    def take_screenshot(self) -> None:
+        """Auswahl des Desktops öffnen; die Antwort kommt über ``screenshot_finished`` (in
+        Tests ersetzbar)."""
+        self._screenshot_portal().take()
+
+    def insert_screenshot(self) -> None:
+        """„Bildschirmfoto“ wie P-touch: labelwerk geht aus dem Weg, der Desktop zeigt seine
+        Auswahl (Bereich, Fenster, Bildschirm), danach liegt das Bild auf dem Etikett.
+        Ohne Portal bleibt das Fenster und ein Hinweis nennt den Weg über die Zwischenablage."""
+        if self._shooting:
+            return
+        self.finish_editing()
+        if not self.screenshot_available():
+            self._show_notice([NO_SCREENSHOT], "error")
+            return
+        self._shooting = self._shot_pending = True
+        self.shortcut_actions["image.screenshot"].setEnabled(False)
+        # ausgeblendet ist kein Fenster mehr sichtbar: schlösse sich jetzt ein anderes, endete
+        # die App sonst
+        app = QApplication.instance()
+        self._quit_on_close = app.quitOnLastWindowClosed()
+        app.setQuitOnLastWindowClosed(False)
+        self.hide()
+        self._hide_timer.start(HIDE_DELAY_MS)
+
+    def _take_hidden(self) -> None:
+        """Fenster ist weg: Auswahl öffnen; ohne Antwort kommt das Fenster nach
+        ``RESTORE_TIMEOUT_MS`` trotzdem wieder. Ein unerwarteter Fehler lässt das Fenster nie
+        verschwunden."""
+        self._restore_timer.start(RESTORE_TIMEOUT_MS)
+        try:
+            self.take_screenshot()
+        except Exception as e:  # Fenster sofort zurück; Meldung statt Traceback
+            self.screenshot_finished(None, f"{SCREENSHOT_FAILED} – {e}")
+
+    def screenshot_finished(self, path: Path | None, error: str | None) -> None:
+        """Antwort des Portals: Pfad → einfügen (300 dpi: 1 Bildschirmpixel = 1 Druckpunkt, wie
+        aus der Zwischenablage), Meldung → Statusleiste, (None, None) = abgebrochen. Es zählt
+        nur die erste Antwort je Aufnahme – auch eine nach der Zeitüberschreitung (kommt sie
+        erst während der nächsten Aufnahme, gilt sie für diese, und die entfällt)."""
+        if not self._shot_pending:
+            return
+        self._shot_pending = False
+        self._show_again()
+        if error is not None:
+            self._show_notice([error], "error")
+            return
+        if path is None:
+            return
+        try:
+            image, dpi = image_import.load_screenshot(Path(path))
+        except (ValueError, OSError) as e:
+            self._show_notice([f"Bildschirmfoto: {e}"], "error")
+            return
+        self._insert_picture(image, SCREENSHOT, dpi=dpi)
+
+    def _show_again(self) -> None:
+        """Nach dem Bildschirmfoto (oder ohne Antwort nach ``RESTORE_TIMEOUT_MS``): Fenster
+        zeigen und nach vorn holen, Aktion wieder frei."""
+        self._restore_timer.stop()
+        if not self._shooting:
+            return
+        self._end_shooting()
+        self.show()
+        self.raise_()
+        self.activateWindow()
+
+    def _end_shooting(self) -> None:
+        self._shooting = False
+        self._hide_timer.stop()
+        self.shortcut_actions["image.screenshot"].setEnabled(True)
+        QApplication.instance().setQuitOnLastWindowClosed(self._quit_on_close)
+
     def _dropped(self, paths: list[Path], image: Image.Image | None, x_mm: float,
                  y_mm: float) -> None:
         """Bilddateien oder Bilddaten auf die Arbeitsfläche abgelegt: an der Ablagestelle
@@ -932,10 +1032,11 @@ class MainWindow(QMainWindow):
             self._insert_picture(image, DROPPED, at=(x_mm, y_mm))
 
     def _insert_picture(self, image: Image.Image, source: str,
-                        at: tuple[float, float] | None = None) -> None:
-        """Bild ohne Auflösungsangabe (Zwischenablage, Bilddaten) mit 300 dpi einfügen."""
+                        at: tuple[float, float] | None = None, dpi: float = DPI) -> None:
+        """Bild ohne Auflösungsangabe (Zwischenablage, Bilddaten, Bildschirmfoto) einfügen –
+        300 dpi, also 1 Pixel = 1 Druckpunkt."""
         notes: list[str] = []
-        self._insert_images([self._new_image(image, DPI, source, None, notes)], at, notes)
+        self._insert_images([self._new_image(image, dpi, source, None, notes)], at, notes)
 
     def _new_image(self, image: Image.Image, dpi: float, source: str, page: int | None,
                    notes: list[str]) -> ImageObject:
@@ -1057,6 +1158,10 @@ class MainWindow(QMainWindow):
 
     def closeEvent(self, event) -> None:
         self._printer_timer.stop()
+        self._restore_timer.stop()
+        self._shot_pending = False                  # keine Auswahl und kein Einfügen mehr
+        if self._shooting:
+            self._end_shooting()
         super().closeEvent(event)
 
     # --- Einstellungen ----------------------------------------------------
diff --git a/src/labelwerk/gui/panels/image.py b/src/labelwerk/gui/panels/image.py
index 8db343c..9da2a63 100644
--- a/src/labelwerk/gui/panels/image.py
+++ b/src/labelwerk/gui/panels/image.py
@@ -1,4 +1,5 @@
-"""Panel „Bild“: Bilder einfügen (Datei, Zwischenablage) und das gewählte Bild einstellen.
+"""Panel „Bild“: Bilder einfügen (Datei, Zwischenablage, Bildschirmfoto) und das gewählte Bild
+einstellen.
 
 Umwandlung in Schwarz/Weiß (Strich = harte Schwelle, Foto = Rasterpunkte), Schwelle,
 Umkehren, Zuschnitt (automatisch an/aus), Originalgröße 1:1, Seitenverhältnis, Drehen
@@ -23,7 +24,8 @@ from ..widgets import SpinBox
 from . import Panel
 from .position import PositionSection
 
-HINT = "Bild aus einer Datei oder der Zwischenablage einfügen – oder aufs Etikett ziehen"
+HINT = ("Bild aus einer Datei, der Zwischenablage oder als Bildschirmfoto einfügen – oder aufs "
+        "Etikett ziehen")
 CROP_FAILED = "Bild nicht zugeschnitten – nur weiße Fläche gefunden"
 _SOURCE_PX = 240                    # Quelle: längere Namen in der Mitte gekürzt (Tooltip)
 _ROTATE = (("rotate_left", "object.rotate_left", "rotate-left"),     # (Attribut, Aktion, Symbol)
@@ -52,7 +54,9 @@ class ImagePanel(Panel):
         self.from_clipboard.setToolTip("Bild aus der Zwischenablage einfügen")
         self.from_clipboard.setEnabled(False)
         self.from_clipboard.clicked.connect(self.paste_requested)
-        for button in (self.from_file, self.from_clipboard):
+        self.screenshot = QPushButton("BILDSCHIRMFOTO")
+        self.screenshot.setToolTip("Bildschirmfoto einfügen")
+        for button in (self.from_file, self.from_clipboard, self.screenshot):
             self.layout_.addWidget(button)
 
         self.section("Quelle")
@@ -136,11 +140,13 @@ class ImagePanel(Panel):
         self.original.clicked.connect(lambda: step(self._change, layout.original_size))
 
     def use_actions(self, actions: dict[str, QAction]) -> None:
-        """„Aus Datei …“ löst die Aktion „Bild einfügen …“ aus (Kürzel im Tooltip)."""
-        action = actions["image.insert"]
-        self.from_file.clicked.connect(lambda: action.trigger())
-        self.from_file.setToolTip(action.toolTip())
-        action.changed.connect(lambda: self.from_file.setToolTip(action.toolTip()))
+        """„Aus Datei …“ und „Bildschirmfoto“ lösen ihre Aktionen aus (Kürzel im Tooltip)."""
+        for button, key in ((self.from_file, "image.insert"),
+                            (self.screenshot, "image.screenshot")):
+            action = actions[key]
+            button.clicked.connect(lambda _=False, a=action: a.trigger())
+            button.setToolTip(action.toolTip())
+            action.changed.connect(lambda b=button, a=action: b.setToolTip(a.toolTip()))
         # Drehen: dieselben Aktionen wie im Reiter Layout (wirken auf die Auswahl = das Bild)
         for attr, key, _ in _ROTATE:
             button, rotate = getattr(self, attr), actions[key]
diff --git a/src/labelwerk/shortcuts.py b/src/labelwerk/shortcuts.py
index 5bd2487..c25d119 100644
--- a/src/labelwerk/shortcuts.py
+++ b/src/labelwerk/shortcuts.py
@@ -37,6 +37,7 @@ ACTIONS: tuple[Action, ...] = (
     Action("tool.select", "Werkzeug Auswahl", "Esc", "canvas"),
     Action("tool.text", "Werkzeug Text anlegen", "T", "canvas"),
     Action("image.insert", "Bild einfügen …", "Ctrl+Shift+I", "canvas"),
+    Action("image.screenshot", "Bildschirmfoto einfügen", "", "canvas"),
     Action("edit.cut", "Ausschneiden", "Ctrl+X", "canvas"),
     Action("edit.copy", "Kopieren", "Ctrl+C", "canvas"),
     Action("edit.paste", "Einfügen", "Ctrl+V", "canvas"),
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `1376 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md src/labelwerk/gui/image_import.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/image.py src/labelwerk/shortcuts.py tests/gui/test_gui_screenshot.py
git commit -m "GUI: Bildschirmfoto im Reiter Bild – ausblenden, Auswahl des Desktops, Bild aufs Etikett

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Abnahme (manuell, durch den Nutzer)

- [ ] BILD → BILDSCHIRMFOTO: labelwerk verschwindet, die COSMIC-Auswahl erscheint; Bereich wählen → labelwerk kommt zurück, das Foto liegt ausgewählt auf dem Etikett (Quelle „Bildschirmfoto“), labelwerk selbst ist nicht mit auf dem Foto.
- [ ] Auch „Fenster“ und „Bildschirm“ in der Auswahl; Abbrechen (Esc) → labelwerk kommt zurück, nichts eingefügt, keine Meldung.
- [ ] Größe: 1 Bildschirmpixel = 1 Druckpunkt; Einstellungen Zuschnitt/Drehen wirken; Rückgängig entfernt das Foto in einem Schritt.
- [ ] Maximiertes Fenster bleibt nach dem Foto maximiert; Fokus/Vordergrund danach.
- [ ] Kürzel in Einstellungen → Tastenkürzel für „Bildschirmfoto einfügen“ belegen und benutzen.
