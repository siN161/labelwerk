import pytest


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path_factory):
    """Kein Test liest oder schreibt die echten Einstellungen des Nutzers."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("config")))
