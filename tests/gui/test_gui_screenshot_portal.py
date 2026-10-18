"""Bildschirmfoto über das XDG-Portal (Etappe 3d-2b): Hilfsfunktionen und D-Bus-Ablauf –
gegen ein nachgebautes Portal auf einem privaten Bus, nie gegen das echte."""
import functools
import select
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from PySide6.QtDBus import QDBusConnection, QDBusMessage

from labelwerk.gui import screenshot
from labelwerk.gui.screenshot import ScreenshotPortal, error_text, parse_response, request_path

FAKE = Path(__file__).with_name("fake_portal.py")
SYSTEM_PYTHON = "/usr/bin/python3"
START_TIMEOUT_S = 10


# --- Hilfsfunktionen ----------------------------------------------------------------
def test_request_path_from_unique_name():
    assert request_path(":1.42", "labelwerk_ab12") == \
        "/org/freedesktop/portal/desktop/request/1_42/labelwerk_ab12"


def test_response_with_file_uri_gives_decoded_path():
    path, error = parse_response(0, {"uri": "file:///home/x/Bilder/Bild%20vom%20Gr%C3%BCn.png"})
    assert path == Path("/home/x/Bilder/Bild vom Grün.png") and error is None


def test_cancelled_response_is_silent():
    assert parse_response(1, {}) == (None, None)


@pytest.mark.parametrize("code, results", [
    (2, {}),                                         # Portal: anderer Fehler/abgelehnt
    (0, {}),                                         # Erfolg ohne Datei
    (0, {"uri": "https://example.org/bild.png"}),    # keine lokale Datei
    (7, {"uri": "file:///tmp/a.png"}),               # unbekannter Code
])
def test_failed_responses_give_german_error(code, results):
    path, error = parse_response(code, results)
    assert path is None and error.startswith("Bildschirmfoto fehlgeschlagen")


@pytest.mark.parametrize("name, text", [
    ("org.freedesktop.DBus.Error.ServiceUnknown", "kein Bildschirmfoto-Portal gefunden"),
    ("org.freedesktop.DBus.Error.UnknownMethod", "kein Bildschirmfoto-Portal gefunden"),
    ("org.freedesktop.DBus.Error.NoReply", "das Portal antwortet nicht"),
    ("org.freedesktop.portal.Error.NotAllowed", "vom System nicht erlaubt"),
    ("org.example.Irgendwas", "Fehler des Portals"),
    ("", "Fehler des Portals"),
])
def test_dbus_errors_are_german(name, text):
    assert error_text(name) == f"Bildschirmfoto fehlgeschlagen – {text}"


# --- ohne Portal ----------------------------------------------------------------------
def test_tests_never_reach_the_session_bus():
    assert not screenshot.session_bus().isConnected()
    assert not QDBusConnection.sessionBus().isConnected()     # conftest: Adresse ins Leere


def test_without_bus_portal_is_unavailable_and_take_reports_error(qtbot):
    portal = ScreenshotPortal()
    assert not portal.available()
    with qtbot.waitSignal(portal.finished, timeout=1000) as signal:
        portal.take()
    path, error = signal.args
    assert path is None and error.startswith("Bildschirmfoto fehlgeschlagen")


# --- privater Bus mit nachgebautem Portal ------------------------------------------
@functools.cache
def _has_gio() -> bool:
    try:
        return subprocess.run([SYSTEM_PYTHON, "-I", "-c", "from gi.repository import Gio"],
                              capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# Eigene Bus-Konfiguration OHNE Service-Verzeichnisse: die Sitzungs-Standardkonfiguration würde
# beim Aufruf das echte Portal des Systems auf dem Testbus starten (Auswahl auf dem Bildschirm)
BUS_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:tmpdir=/tmp</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


def _read_line(proc: subprocess.Popen) -> str:
    """Nächste Zeile der Ausgabe, höchstens ``START_TIMEOUT_S`` warten ("" = keine). Der Fake
    läuft ungepuffert (Bytes): ein Puffer von Python würde ``select`` später Zeilen verbergen."""
    ready, _, _ = select.select([proc.stdout], [], [], START_TIMEOUT_S)
    if not ready:
        return ""
    line = proc.stdout.readline()
    return (line.decode() if isinstance(line, bytes) else line).strip()


def _stop(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(5)


@pytest.fixture
def private_bus(tmp_path):
    """Eigener D-Bus-Daemon nur für den Test: (Adresse, Verbindung); startet keine Dienste."""
    if not (shutil.which("dbus-daemon") and _has_gio()):
        pytest.skip("dbus-daemon oder PyGObject (System-Python) fehlt")
    config = tmp_path / "bus.conf"
    config.write_text(BUS_CONFIG)
    daemon = subprocess.Popen(["dbus-daemon", f"--config-file={config}", "--nofork",
                               "--print-address"], stdout=subprocess.PIPE, text=True)
    name = f"labelwerk-test-{uuid.uuid4().hex}"
    try:
        address = _read_line(daemon)
        assert address, "dbus-daemon startet nicht"
        bus = QDBusConnection.connectToBus(address, name)
        assert bus.isConnected(), address
        names = bus.call(QDBusMessage.createMethodCall(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "ListActivatableNames")).arguments()[0]
        assert names == ["org.freedesktop.DBus"], names       # nichts auf dem Testbus startbar
        yield address, bus
    finally:
        QDBusConnection.disconnectFromBus(name)
        _stop(daemon)


@pytest.fixture
def fake_portal(private_bus):
    """Nachgebautes Portal starten: ``fake_portal(art, code, uri) -> Prozess`` (Ausgabe: CALL …)."""
    address, _ = private_bus
    started = []

    def start(mode="normal", code=0, uri="file:///tmp/Bild%20%C3%A4.png"):
        proc = subprocess.Popen([SYSTEM_PYTHON, "-I", str(FAKE), mode, str(code), uri],
                                env={"DBUS_SESSION_BUS_ADDRESS": address},
                                stdout=subprocess.PIPE, bufsize=0)
        started.append(proc)
        assert _read_line(proc) == "READY"
        return proc

    yield start
    for proc in started:
        _stop(proc)


def _take(qtbot, portal):
    with qtbot.waitSignal(portal.finished, timeout=5000) as signal:
        portal.take()
    return signal.args


def test_portal_on_private_bus_delivers_the_file(qtbot, private_bus, fake_portal):
    fake = fake_portal()
    portal = ScreenshotPortal(private_bus[1])
    assert portal.available()
    assert _take(qtbot, portal) == [Path("/tmp/Bild ä.png"), None]
    call = _read_line(fake)
    assert "interactive=True modal=True token=labelwerk_" in call
    assert portal._request is None and portal._path is None          # Abo gelöst


def test_portal_on_private_bus_cancel(qtbot, private_bus, fake_portal):
    fake_portal(code=1, uri="-")
    assert _take(qtbot, ScreenshotPortal(private_bus[1])) == [None, None]


def test_answer_before_the_call_returns_is_not_lost(qtbot, private_bus, fake_portal):
    """Das Portal darf schon antworten, bevor der Aufruf zurückkommt – darum vorher abonniert."""
    fake_portal("early")
    assert _take(qtbot, ScreenshotPortal(private_bus[1])) == [Path("/tmp/Bild ä.png"), None]


def test_older_portal_with_own_request_path(qtbot, private_bus, fake_portal):
    fake_portal("other")
    assert _take(qtbot, ScreenshotPortal(private_bus[1])) == [Path("/tmp/Bild ä.png"), None]


def test_two_answers_give_one_result(qtbot, private_bus, fake_portal):
    fake_portal("twice", uri="file:///tmp/a.png")
    portal = ScreenshotPortal(private_bus[1])
    results = []
    portal.finished.connect(lambda *args: results.append(args))
    portal.take()
    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    qtbot.wait(200)
    assert results == [(Path("/tmp/a.png"), None)]


def test_new_take_drops_the_open_one_even_with_queued_answer(qtbot, private_bus, fake_portal):
    """Die Antwort der ersten Aufnahme steht schon in der Ereignisschlange (Qt verarbeitet
    während ``sleep`` nichts) – gemeldet wird trotzdem nur die zweite."""
    fake_portal(uri="file:///tmp/bild{n}.png")
    portal = ScreenshotPortal(private_bus[1])
    results = []
    portal.finished.connect(lambda *args: results.append(args))
    portal.take()
    time.sleep(0.3)
    portal.take()
    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    qtbot.wait(200)
    assert results == [(Path("/tmp/bild2.png"), None)]


def test_new_take_closes_the_open_selection(qtbot, private_bus, fake_portal):
    """Die Auswahl der ersten Aufnahme bleibt sonst auf dem Bildschirm stehen."""
    fake = fake_portal("never")
    portal = ScreenshotPortal(private_bus[1])
    portal.take()
    first = portal._path
    portal.take()
    lines = [_read_line(fake) for _ in range(3)]       # CALL, CLOSE, CALL
    assert f"CLOSE {first}" in lines and sum(line.startswith("CALL") for line in lines) == 2


class _NoSubscribeAtOwnPath:
    """Bus, auf dem das Abonnieren des abweichenden Request-Pfads (Fake „other“: …/alt1) scheitert."""

    def __init__(self, bus):
        self._bus = bus

    def connect(self, service, path, *args):
        return "/alt" not in path and self._bus.connect(service, path, *args)

    def __getattr__(self, name):
        return getattr(self._bus, name)


def test_failed_resubscribe_closes_the_selection(qtbot, private_bus, fake_portal):
    fake = fake_portal("other")
    portal = ScreenshotPortal(_NoSubscribeAtOwnPath(private_bus[1]))
    path, error = _take(qtbot, portal)
    assert path is None and "nicht abonnierbar" in error
    _read_line(fake)                                   # CALL
    close = _read_line(fake)
    assert close.startswith("CLOSE /org/freedesktop/portal/desktop/request/")
    assert close.endswith("/alt1")


def test_portal_missing_on_private_bus(qtbot, private_bus):
    portal = ScreenshotPortal(private_bus[1])
    assert not portal.available()
    path, error = _take(qtbot, portal)
    assert (path, error) == (None, "Bildschirmfoto fehlgeschlagen – kein Bildschirmfoto-Portal "
                                   "gefunden")
