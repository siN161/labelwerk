import json

import pytest

from labelwerk.settings import Settings, load_settings, new_document, save_settings, settings_path


def test_defaults_match_todays_behavior(tmp_path):
    s = load_settings(tmp_path / "fehlt.json")
    assert (s.label_id, s.orientation, s.margin_mm, s.font_size_pt) == ("62", "vertical", 1.0, None)
    assert s.check_media_on_start is True and s.start_zoom == 200
    assert s.warnings == []


def test_path_follows_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert settings_path() == tmp_path / "labelwerk" / "settings.json"


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "cfg" / "settings.json"
    save_settings(Settings(label_id="62x29", orientation="horizontal", margin_mm=3,
                           font_size_pt=19, check_media_on_start=False, start_zoom=150), path)
    s = load_settings(path)
    assert (s.label_id, s.orientation, s.margin_mm, s.font_size_pt) == ("62x29", "horizontal", 3.0, 19)
    assert (s.check_media_on_start, s.start_zoom) == (False, 150)
    assert "warnings" not in json.loads(path.read_text())


def test_invalid_values_fall_back_with_warning(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"label_id": "999", "orientation": "schräg", "margin_mm": 99,
                                "font_size_pt": "groß", "start_zoom": True, "unbekannt": 1,
                                "check_media_on_start": False}))
    s = load_settings(path)
    assert (s.label_id, s.orientation, s.margin_mm, s.font_size_pt, s.start_zoom) == \
        ("62", "vertical", 1.0, None, 200)
    assert s.check_media_on_start is False                 # gültige Werte bleiben
    assert len(s.warnings) == 5
    assert all("ungültig" in w for w in s.warnings)


def test_broken_json_gives_defaults_and_warning(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{kaputt")
    s = load_settings(path)
    assert s.label_id == "62"
    assert len(s.warnings) == 1 and "nicht lesbar" in s.warnings[0]


def test_save_error_has_clear_message(tmp_path):
    blocker = tmp_path / "datei"
    blocker.write_text("x")                                # Ordner kann nicht angelegt werden
    with pytest.raises(OSError, match="nicht gespeichert"):
        save_settings(Settings(), blocker / "settings.json")


def test_new_document_uses_settings():
    doc = new_document(Settings(label_id="62x29", orientation="horizontal", margin_mm=3, font_size_pt=19))
    assert (doc.label_id, doc.orientation, doc.margin_mm) == ("62x29", "horizontal", 3)
    assert doc.objects[0].size_pt == 19 and doc.objects[0].text == ""


import pytest


@pytest.mark.parametrize("label", ["102", "62red"])
def test_label_not_in_model_list_falls_back(tmp_path, label):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"label_id": label}))
    s = load_settings(path)
    assert s.label_id == "62"
    assert len(s.warnings) == 1


def test_unreadable_config_dir_gives_warning_not_exception(tmp_path, monkeypatch):
    from pathlib import Path

    def denied(self, *a, **kw):
        raise PermissionError(13, "Keine Berechtigung")
    monkeypatch.setattr(Path, "exists", denied)
    monkeypatch.setattr(Path, "read_text", denied)
    s = load_settings(tmp_path / "settings.json")
    assert s == Settings()
    assert any("nicht lesbar" in w for w in s.warnings)


def test_old_font_size_in_dots_is_converted_to_pt(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"font_size": 80}))
    s = load_settings(path)
    assert s.font_size_pt == 19
    assert any("umgerechnet" in w for w in s.warnings)
    save_settings(s, path)
    assert "font_size" not in json.loads(path.read_text()) and \
        json.loads(path.read_text())["font_size_pt"] == 19


def test_font_family_setting(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"font_family": "Liberation Sans"}))
    assert load_settings(path).font_family == "Liberation Sans"
    path.write_text(json.dumps({"font_family": 42}))
    s = load_settings(path)
    assert s.font_family == "DejaVu Sans" and s.warnings


def test_new_document_uses_font_family():
    doc = new_document(Settings(font_family="Liberation Sans"))
    assert doc.objects[0].paragraphs[0].spans[0].family == "Liberation Sans"
    assert new_document(Settings()).objects[0].paragraphs[0].spans[0].family is None


def test_font_family_is_stripped(tmp_path):
    path = tmp_path / "s.json"
    path.write_text('{"font_family": "  Liberation Sans "}', encoding="utf-8")
    assert load_settings(path).font_family == "Liberation Sans"
