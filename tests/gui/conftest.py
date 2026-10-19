import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"   # immer, auch wenn die Sitzung wayland/xcb vorgibt
# Sitzungsbus ins Leere: kein Test erreicht echte Dienste (Bildschirmfoto-Portal öffnete eine
# Auswahl auf dem Bildschirm); Tests mit D-Bus nutzen einen eigenen Bus mit eigener Adresse
os.environ["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/nonexistent/labelwerk-test-bus"

try:
    import PySide6  # noqa: F401
except ImportError:  # reine CLI-Umgebung: GUI-Tests überspringen
    collect_ignore_glob = ["test_*.py"]
else:
    import pytest

    @pytest.fixture(autouse=True)
    def german_numbers(qapp):
        """Zahlenfelder wie in einer deutschen Sitzung (Komma) – passend zur Sprache der Tests."""
        from PySide6.QtCore import QLocale
        QLocale.setDefault(QLocale("de"))
        yield
        QLocale.setDefault(QLocale("de"))

    @pytest.fixture(autouse=True)
    def no_leftover_theme(qapp):
        """Speichern der Einstellungen setzt das Design der ganzen Anwendung – danach zurück,
        damit jeder Test im Qt-Grundstil startet."""
        yield
        qapp.setStyleSheet("")

    @pytest.fixture(autouse=True)
    def empty_clipboard(qapp):
        """Jeder Test beginnt mit leerer Zwischenablage des Systems – „Einfügen“ folgt ihr."""
        qapp.clipboard().clear()
        yield

    @pytest.fixture(autouse=True)
    def no_session_bus(monkeypatch):
        """Zusätzlich zur Adresse ins Leere: das Bildschirmfoto-Modul bekommt statt des
        Sitzungsbusses eine nie verbundene Verbindung."""
        from PySide6.QtDBus import QDBusConnection
        monkeypatch.setattr("labelwerk.gui.screenshot.session_bus",
                            lambda: QDBusConnection("labelwerk-test-kein-bus"))

    @pytest.fixture(autouse=True, scope="session")
    def discard_changes_on_close():
        """Schließen mit Änderungen fragt nach – in Tests ohne Dialog: verwerfen (einzelne Tests
        ersetzen die Antwort selbst). Für die ganze Sitzung: auch Fenster, die erst am Ende
        geschlossen werden, dürfen keinen echten Dialog öffnen (der hinge)."""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("labelwerk.gui.file_session.FileSession.ask_save_changes",
                          lambda self: "discard")
            yield

    @pytest.fixture(autouse=True, scope="session")
    def no_real_file_dialog():
        """Kein Test öffnet einen echten (modalen) Dateidialog – er hinge; Tests, die ihn
        brauchen, ersetzen ``exec_dialog`` selbst."""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("labelwerk.gui.file_dialog.exec_dialog",
                          lambda dialog: pytest.fail("echter Dateidialog"))
            yield

    @pytest.fixture(autouse=True)
    def no_file_manager(monkeypatch):
        """Kein Test öffnet den echten Dateimanager (Ordner öffnen ist sonst ersetzt)."""
        monkeypatch.setattr("PySide6.QtGui.QDesktopServices.openUrl",
                            lambda url: pytest.fail(f"Dateimanager geöffnet: {url}"))

    @pytest.fixture(autouse=True)
    def no_printer(monkeypatch):
        """Kein Test liest echte Druckerdaten aus /sys."""
        for module in ("labelwerk.gui.print_worker", "labelwerk.gui.media_worker"):
            monkeypatch.setattr(f"{module}.find_brother_lp", lambda: None)
            monkeypatch.setattr(f"{module}.brother_busy", lambda: False)
        monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [])
        monkeypatch.setattr("labelwerk.gui.main_window.brother_busy", lambda: False)

        calls = []

        def no_hardware(printer):
            # Der Worker schluckt Exceptions, daher Aufruf merken und im Teardown scheitern
            calls.append(printer)
            raise RuntimeError("Test darf den Drucker nicht abfragen")
        monkeypatch.setattr("labelwerk.gui.media_worker.read_media", no_hardware)
        yield
        assert not calls, "Test hat den Drucker abgefragt"
