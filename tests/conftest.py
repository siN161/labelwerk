import pytest


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path_factory):
    """Kein Test liest oder schreibt die echten Einstellungen oder Daten (eigene Symbole) des
    Nutzers."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("config")))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path_factory.mktemp("data")))


@pytest.fixture(autouse=True)
def no_leftover_rasterizer():
    """Das Hauptfenster meldet die Qt-Raster-Funktion für Vektorbilder an – danach wieder ohne,
    damit jeder Test im Kern-Zustand startet."""
    yield
    from labelwerk.render import set_svg_rasterizer
    set_svg_rasterizer(None)


@pytest.fixture(autouse=True)
def no_real_hardware(monkeypatch):
    """Sicherheitsnetz: Erreichen die echten Low-Level-Funktionen den Drucker, scheitert der Test.

    Tests ersetzen höhere Funktionen (read_media, print_image) selbst; nur wenn dabei
    doch `query_status` oder brother_qls `send` erreicht wird, schlägt das Netz an.
    """
    calls = []

    def guard(name):
        def blocked(*args, **kwargs):
            calls.append(name)
            raise RuntimeError(f"Test darf nicht auf den Drucker zugreifen ({name})")
        return blocked
    monkeypatch.setattr("labelwerk.media.query_status", guard("query_status"))
    monkeypatch.setattr("labelwerk.printer.send", guard("send"))
    yield
    assert not calls, f"Test hat echte Hardware-Funktionen erreicht: {calls}"
