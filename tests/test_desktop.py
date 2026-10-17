import pytest

from labelwerk.desktop import install, uninstall


@pytest.fixture
def gui_exe(tmp_path):
    exe = tmp_path / "bin" / "labelwerk-gui"
    exe.parent.mkdir()
    exe.write_text("#!/bin/sh\n")
    return exe


def test_install_writes_desktop_entry_and_icon(tmp_path, gui_exe):
    data = tmp_path / "share"
    paths = install(gui_exe, data)
    entry = data / "applications" / "labelwerk.desktop"
    icon = data / "icons" / "hicolor" / "scalable" / "apps" / "labelwerk.svg"
    assert set(paths) == {entry, icon}
    text = entry.read_text()
    assert f"Exec={gui_exe}\n" in text
    assert "Icon=labelwerk\n" in text
    assert "StartupWMClass=labelwerk\n" in text
    assert icon.read_text().lstrip().startswith("<svg")


def test_install_twice_overwrites(tmp_path, gui_exe):
    data = tmp_path / "share"
    install(gui_exe, data)
    install(gui_exe, data)
    assert len(list((data / "applications").iterdir())) == 1


def test_install_without_gui_raises(tmp_path):
    with pytest.raises(ValueError, match="labelwerk-gui nicht gefunden"):
        install(tmp_path / "fehlt" / "labelwerk-gui", tmp_path / "share")


def test_uninstall_removes_files(tmp_path, gui_exe):
    data = tmp_path / "share"
    installed = install(gui_exe, data)
    assert set(uninstall(data)) == set(installed)
    assert not any(p.exists() for p in installed)
    assert uninstall(data) == []                       # zweites Mal: nichts zu tun


def test_display_name_comes_from_app_name(tmp_path, gui_exe, monkeypatch):
    import labelwerk.desktop as desktop
    monkeypatch.setattr(desktop, "APP_NAME", "Neuer Name")
    assert "Name=Neuer Name\n" in desktop.desktop_entry(gui_exe)
