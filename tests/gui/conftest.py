import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"   # immer, auch wenn die Sitzung wayland/xcb vorgibt

try:
    import PySide6  # noqa: F401
except ImportError:  # reine CLI-Umgebung: GUI-Tests überspringen
    collect_ignore_glob = ["test_*.py"]
else:
    import pytest

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
    def no_printer(monkeypatch):
        """Kein Test liest echte Druckerdaten aus /sys."""
        for module in ("labelwerk.gui.main_window", "labelwerk.gui.print_worker",
                       "labelwerk.gui.media_worker"):
            monkeypatch.setattr(f"{module}.find_brother_lp", lambda: None)
            monkeypatch.setattr(f"{module}.brother_busy", lambda: False)

        calls = []

        def no_hardware(printer):
            # Der Worker schluckt Exceptions, daher Aufruf merken und im Teardown scheitern
            calls.append(printer)
            raise RuntimeError("Test darf den Drucker nicht abfragen")
        monkeypatch.setattr("labelwerk.gui.media_worker.read_media", no_hardware)
        yield
        assert not calls, "Test hat den Drucker abgefragt"
