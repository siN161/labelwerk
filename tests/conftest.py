import pytest


@pytest.fixture(autouse=True)
def german(monkeypatch):
    """Tests run in German (their expectations are the German texts), even if CLI/GUI take the
    system language (``LANGUAGE``); whoever tests another language sets it themselves –
    afterwards German applies again."""
    from labelwerk import i18n
    monkeypatch.setenv("LANGUAGE", "de")
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")      # locale “C” would mean English
    i18n.set_language("de")
    yield
    i18n.set_language("de")


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path_factory):
    """No test reads or writes the user's real settings or data (own symbols)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("config")))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path_factory.mktemp("data")))


@pytest.fixture(autouse=True)
def no_real_sysfs(monkeypatch, tmp_path_factory):
    """No test sees real printers in /sys (detection via ``printers.usb_printers``)."""
    monkeypatch.setattr("labelwerk.printers.SYS_ROOT", str(tmp_path_factory.mktemp("usbmisc")))


@pytest.fixture(autouse=True)
def no_real_cups(monkeypatch, tmp_path_factory):
    """No test calls real CUPS commands (lpstat, lpoptions, lp) or reads real PPDs: without
    its own replacement there are no queues."""
    from labelwerk import cups
    monkeypatch.setattr(cups, "PPD_DIR", tmp_path_factory.mktemp("ppd"))
    monkeypatch.setattr(cups, "_run", lambda *args, **kw: "")
    monkeypatch.setattr(cups, "BACKGROUND", False)
    cups.forget()                       # anything remembered from an earlier test does not count


@pytest.fixture(autouse=True)
def no_leftover_rasterizer():
    """The main window registers the Qt rasteriser for vector images – afterwards reset to none,
    so that every test starts in the core state."""
    yield
    from labelwerk.render import set_svg_rasterizer
    set_svg_rasterizer(None)


@pytest.fixture(autouse=True)
def no_real_hardware(monkeypatch):
    """Safety net: if the real low-level functions reach the printer, the test fails.

    Tests replace higher-level functions (read_media, print_image) themselves; only if
    `query_status` or brother_ql's `send` is reached after all does the net trigger.
    """
    calls = []

    def guard(name):
        def blocked(*args, **kwargs):
            calls.append(name)
            raise RuntimeError(f"Test darf nicht auf den Drucker zugreifen ({name})")
        return blocked
    monkeypatch.setattr("labelwerk.media.query_status", guard("query_status"))
    monkeypatch.setattr("labelwerk.printer.send", guard("send"))
    monkeypatch.setattr("labelwerk.printer.socket.create_connection", guard("create_connection"))
    yield
    assert not calls, f"Test hat echte Hardware-Funktionen erreicht: {calls}"
