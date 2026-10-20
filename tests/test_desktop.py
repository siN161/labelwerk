import functools

import pytest

from labelwerk import desktop

# without external programs (update-mime-database …): nothing found
install = functools.partial(desktop.install, which=lambda name: None)
uninstall = functools.partial(desktop.uninstall, which=lambda name: None)


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
    assert {entry, icon} <= set(paths)
    text = entry.read_text()
    assert f'Exec="{gui_exe}" %f\n' in text
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
    assert uninstall(data) == []                       # second time: nothing to do


def test_display_name_comes_from_app_name(tmp_path, gui_exe, monkeypatch):
    monkeypatch.setattr(desktop, "APP_NAME", "Neuer Name")
    assert "Name=Neuer Name\n" in desktop.desktop_entry(gui_exe)


# --- File type *.labelwerk (stage 3c) ---------------------------------------------------
class Runner:
    """Replacement for external programs: records the calls, starts nothing."""

    def __init__(self, available=True):
        self.calls = []
        self.available = available

    def which(self, name):
        return f"/usr/bin/{name}" if self.available else None

    def run(self, args, **kwargs):
        self.calls.append(args)


def test_install_registers_the_file_type(tmp_path, gui_exe):
    data = tmp_path / "share"
    runner = Runner()
    paths = desktop.install(gui_exe, data, which=runner.which, run=runner.run)
    mime = data / "mime" / "packages" / "labelwerk.xml"
    mime_icon = data / "icons" / "hicolor" / "scalable" / "mimetypes" / "application-x-labelwerk.svg"
    assert mime in paths and mime_icon in paths
    xml = mime.read_text()
    assert 'type="application/x-labelwerk"' in xml and 'pattern="*.labelwerk"' in xml
    entry = (data / "applications" / "labelwerk.desktop").read_text()
    assert f'Exec="{gui_exe}" %f\n' in entry and "MimeType=application/x-labelwerk;\n" in entry
    assert runner.calls == [["/usr/bin/update-mime-database", str(data / "mime")],
                            ["/usr/bin/update-desktop-database", str(data / "applications")]]


def test_install_without_update_tools_still_works(tmp_path, gui_exe):
    runner = Runner(available=False)
    desktop.install(gui_exe, tmp_path / "share", which=runner.which, run=runner.run)
    assert runner.calls == []


def test_uninstall_removes_the_file_type(tmp_path, gui_exe):
    data = tmp_path / "share"
    runner = Runner()
    desktop.install(gui_exe, data, which=runner.which, run=runner.run)
    runner.calls.clear()
    removed = desktop.uninstall(data, which=runner.which, run=runner.run)
    assert data / "mime" / "packages" / "labelwerk.xml" in removed
    assert not (data / "mime" / "packages" / "labelwerk.xml").exists()
    assert ["/usr/bin/update-mime-database", str(data / "mime")] in runner.calls


def test_failing_update_tool_is_no_error(tmp_path, gui_exe):
    import subprocess

    def broken(args, **kwargs):
        raise subprocess.CalledProcessError(1, args)
    desktop.install(gui_exe, tmp_path / "share", which=Runner().which, run=broken)


def test_exec_path_with_spaces_and_special_characters_is_quoted(tmp_path):
    """Desktop Entry specification: path in quotes, \\ " ` $ escaped, % doubled."""
    exe = tmp_path / "mein Ordner $x 100%" / "labelwerk-gui"
    exe.parent.mkdir()
    exe.write_text("#!/bin/sh\n")
    entry = desktop.desktop_entry(exe)
    quoted = str(exe).replace("$", "\\\\$").replace("%", "%%")
    assert f'Exec="{quoted}" %f\n' in entry


def test_uninstall_updates_both_databases_and_nothing_installed_does_nothing(tmp_path, gui_exe):
    data = tmp_path / "share"
    runner = Runner()
    assert desktop.uninstall(data, which=runner.which, run=runner.run) == []
    assert runner.calls == []
    desktop.install(gui_exe, data, which=runner.which, run=runner.run)
    runner.calls.clear()
    desktop.uninstall(data, which=runner.which, run=runner.run)
    assert ["/usr/bin/update-desktop-database", str(data / "applications")] in runner.calls


@pytest.mark.parametrize("error", [OSError("fehlt"), "timeout"])
def test_failing_update_tool_is_reported(tmp_path, gui_exe, error):
    import subprocess

    def broken(args, **kwargs):
        if error == "timeout":
            raise subprocess.TimeoutExpired(args, kwargs.get("timeout"))
        raise error
    failed = desktop.update_databases(tmp_path, which=Runner().which, run=broken)
    assert failed == []                                  # folders missing: nothing called
    desktop.install(gui_exe, tmp_path / "share", which=lambda n: None)
    failed = desktop.update_databases(tmp_path / "share", which=Runner().which, run=broken)
    assert failed == ["update-mime-database", "update-desktop-database"]


def test_mime_comment_has_english_fallback_and_german(tmp_path):
    xml = desktop.mime_xml()
    assert "<comment>labelwerk label</comment>" in xml
    assert '<comment xml:lang="de">labelwerk-Etikett</comment>' in xml
