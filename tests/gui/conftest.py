import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"   # always, even if the session prescribes wayland/xcb
# Session bus pointed at nothing: no test reaches real services (the screenshot portal opened a
# selection on screen); tests with D-Bus use their own bus with its own address
os.environ["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/nonexistent/labelwerk-test-bus"

try:
    import PySide6  # noqa: F401
except ImportError:  # pure CLI environment: skip GUI tests
    collect_ignore_glob = ["test_*.py"]
else:
    import pytest

    @pytest.fixture(autouse=True)
    def german_numbers(qapp):
        """Number fields as in a German session (comma) – matching the tests' language."""
        from PySide6.QtCore import QLocale
        QLocale.setDefault(QLocale("de"))
        yield
        QLocale.setDefault(QLocale("de"))

    @pytest.fixture(autouse=True)
    def no_leftover_theme(qapp):
        """Saving the settings sets the design of the whole application – reset afterwards,
        so that every test starts in the basic Qt style."""
        yield
        qapp.setStyleSheet("")

    @pytest.fixture(autouse=True)
    def empty_clipboard(qapp):
        """Every test starts with an empty system clipboard – “Paste” follows it."""
        qapp.clipboard().clear()
        yield

    @pytest.fixture(autouse=True)
    def no_session_bus(monkeypatch):
        """In addition to the address pointing at nothing: the screenshot module gets a never-connected
        connection instead of the session bus."""
        from PySide6.QtDBus import QDBusConnection
        monkeypatch.setattr("labelwerk.gui.screenshot.session_bus",
                            lambda: QDBusConnection("labelwerk-test-kein-bus"))

    @pytest.fixture(autouse=True, scope="session")
    def discard_changes_on_close():
        """Closing with changes asks – in tests without a dialog: discard (individual tests
        replace the answer themselves). For the whole session: windows that are only closed at the
        end must not open a real dialog either (it would hang)."""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("labelwerk.gui.file_session.FileSession.ask_save_changes",
                          lambda self: "discard")
            yield

    @pytest.fixture(autouse=True, scope="session")
    def no_real_file_dialog():
        """No test opens a real (modal) file dialog – it would hang; tests that need
        one replace ``exec_dialog`` themselves."""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("labelwerk.gui.file_dialog.exec_dialog",
                          lambda dialog: pytest.fail("echter Dateidialog"))
            yield

    @pytest.fixture(autouse=True)
    def no_file_manager(monkeypatch):
        """No test opens the real file manager (opening a folder is otherwise replaced)."""
        monkeypatch.setattr("PySide6.QtGui.QDesktopServices.openUrl",
                            lambda url: pytest.fail(f"Dateimanager geöffnet: {url}"))

    @pytest.fixture(autouse=True)
    def no_printer(monkeypatch):
        """No test reads real printer data from /sys."""
        for module in ("labelwerk.gui.print_worker", "labelwerk.gui.media_worker"):
            monkeypatch.setattr(f"{module}.find_brother_lp", lambda: None)
            monkeypatch.setattr(f"{module}.brother_busy", lambda: False)
        monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [])
        monkeypatch.setattr("labelwerk.gui.main_window.brother_busy", lambda: False)

        calls = []

        def no_hardware(printer):
            # The worker swallows exceptions, so remember the call and fail in teardown
            calls.append(printer)
            raise RuntimeError("Test darf den Drucker nicht abfragen")
        monkeypatch.setattr("labelwerk.gui.media_worker.read_media", no_hardware)
        yield
        assert not calls, "Test hat den Drucker abgefragt"
