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


@pytest.mark.parametrize("label", ["pt12", "gibt-es-nicht", 62])
def test_unknown_label_falls_back(tmp_path, label):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"label_id": label}))
    s = load_settings(path)
    assert s.label_id == "62"
    assert len(s.warnings) == 1


@pytest.mark.parametrize("label", ["102", "62red"])
def test_label_of_another_printer_is_kept(tmp_path, label):
    """Ob das Etikett zum angeschlossenen Drucker passt, prüfen GUI und CLI (zwei Drucker)."""
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"label_id": label}))
    s = load_settings(path)
    assert s.label_id == label and s.warnings == []


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


def test_theme_default_and_roundtrip(tmp_path):
    assert Settings().theme == "rawblock"
    path = tmp_path / "s.json"
    save_settings(Settings(theme="classic"), path)
    assert load_settings(path).theme == "classic"


def test_invalid_theme_falls_back_with_warning(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"theme": "neon"}))
    s = load_settings(path)
    assert s.theme == "rawblock" and any("theme" in w for w in s.warnings)


# --- Tastenkürzel -------------------------------------------------------------------
def test_shortcuts_default_empty(tmp_path):
    assert load_settings(tmp_path / "fehlt.json").shortcuts == {}
    assert Settings().shortcuts == {}


def test_shortcuts_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(shortcuts={"file.print": "Ctrl+Shift+P", "edit.delete": ""}), path)
    assert json.loads(path.read_text())["shortcuts"] == {"file.print": "Ctrl+Shift+P",
                                                          "edit.delete": ""}
    s = load_settings(path)
    assert s.shortcuts == {"file.print": "Ctrl+Shift+P", "edit.delete": ""}
    assert s.warnings == []


def test_invalid_shortcuts_dropped_with_warning(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"shortcuts": {"file.print": "Strg+P", "gibt.es_nicht": "Ctrl+Q",
                                              "edit.copy": "Ctrl+Shift+C"}}))
    s = load_settings(path)
    assert s.shortcuts == {"edit.copy": "Ctrl+Shift+C"}
    assert len(s.warnings) == 2


def test_shortcuts_not_a_dict_gives_defaults_and_warning(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"shortcuts": ["Ctrl+P"], "start_zoom": 150}))
    s = load_settings(path)
    assert s.shortcuts == {} and s.start_zoom == 150
    assert len(s.warnings) == 1 and "shortcuts" in s.warnings[0]


def test_settings_default_shortcuts_not_shared():
    a, b = Settings(), Settings()
    a.shortcuts["file.print"] = "F2"
    assert b.shortcuts == {}


def test_shortcuts_null_keeps_defaults_with_warning(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"shortcuts": None, "label_id": "29"}))
    s = load_settings(path)
    assert s.shortcuts == {} and s.label_id == "29"
    assert len(s.warnings) == 1 and "shortcuts" in s.warnings[0]


def test_esc_from_settings_file_is_rejected(tmp_path):
    from labelwerk.settings import load_settings
    path = tmp_path / "settings.json"
    path.write_text('{"shortcuts": {"file.print": "Esc"}}', encoding="utf-8")
    settings = load_settings(path)
    assert settings.shortcuts == {}
    assert any("nicht belegbar" in w for w in settings.warnings)


# --- Bilder einfügen ----------------------------------------------------------------
def test_image_import_defaults_and_roundtrip(tmp_path):
    s = Settings()
    assert (s.image_crop, s.image_rotate) == (True, False)     # zuschneiden, nicht drehen
    path = tmp_path / "s.json"
    save_settings(Settings(image_crop=False, image_rotate=True), path)
    loaded = load_settings(path)
    assert (loaded.image_crop, loaded.image_rotate) == (False, True)
    assert loaded.warnings == []


def test_invalid_image_import_settings_fall_back_with_warning(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"image_crop": "ja", "image_rotate": 1}))
    s = load_settings(path)
    assert (s.image_crop, s.image_rotate) == (True, False)
    assert sum("image_" in w for w in s.warnings) == 2


# --- Symbole ------------------------------------------------------------------------
def test_symbol_lists_default_empty_and_roundtrip(tmp_path):
    s = Settings()
    assert (s.symbols_recent, s.symbols_favorites) == ([], [])
    path = tmp_path / "s.json"
    save_settings(Settings(symbols_recent=["labelwerk/erde", "iso7010/W012"],
                           symbols_favorites=["tabler/outline/home"]), path)
    loaded = load_settings(path)
    assert loaded.symbols_recent == ["labelwerk/erde", "iso7010/W012"]
    assert loaded.symbols_favorites == ["tabler/outline/home"] and loaded.warnings == []


def test_symbol_lists_are_not_shared_between_settings():
    a, b = Settings(), Settings()
    a.symbols_favorites.append("x")
    assert b.symbols_favorites == []


@pytest.mark.parametrize("value", ["labelwerk/erde", None, {"a": 1}])
def test_invalid_symbol_lists_fall_back_with_warning(tmp_path, value):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"symbols_recent": value, "symbols_favorites": value}))
    s = load_settings(path)
    assert (s.symbols_recent, s.symbols_favorites) == ([], [])
    assert sum("symbols_" in w for w in s.warnings) == 2


def test_invalid_entries_are_dropped_singly_and_duplicates_removed(tmp_path):
    """Ein kaputter Eintrag kostet nicht die ganze Liste (sonst wären Favoriten beim nächsten
    Speichern weg)."""
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"symbols_favorites": ["a", 3, "", "b", "a"]}))
    s = load_settings(path)
    assert s.symbols_favorites == ["a", "b"]
    assert any("symbols_favorites" in w for w in s.warnings)


def test_recent_symbols_are_capped_when_loading(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"symbols_recent": [f"s{i}" for i in range(40)]}))
    assert load_settings(path).symbols_recent == [f"s{i}" for i in range(24)]


def test_save_is_atomic_and_leaves_no_temp_files(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    save_settings(Settings(margin_mm=3), path)
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]

    def broken(src, dst):
        raise OSError(28, "Kein Speicherplatz mehr")
    monkeypatch.setattr("labelwerk.settings.os.replace", broken)
    with pytest.raises(OSError, match="konnten nicht gespeichert werden"):
        save_settings(Settings(margin_mm=5), path)
    assert load_settings(path).margin_mm == 3.0          # alte Datei unversehrt
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]


# --- Dateien ------------------------------------------------------------------------
def test_recent_files_and_start_favorite_default_and_roundtrip(tmp_path):
    s = Settings()
    assert (s.recent_files, s.start_favorite) == ([], None)
    path = tmp_path / "s.json"
    save_settings(Settings(recent_files=["/a.labelwerk", "/b.labelwerk"], start_favorite="Absender"),
                  path)
    loaded = load_settings(path)
    assert loaded.recent_files == ["/a.labelwerk", "/b.labelwerk"]
    assert loaded.start_favorite == "Absender" and loaded.warnings == []


def test_recent_files_are_cleaned_when_loading(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"recent_files": [f"/{i}.labelwerk" for i in range(12)] + ["/0.labelwerk", 3]}))
    s = load_settings(path)
    assert s.recent_files == [f"/{i}.labelwerk" for i in range(10)]
    assert any("recent_files" in w for w in s.warnings)


@pytest.mark.parametrize("value", [3, "", "  "])
def test_invalid_start_favorite_falls_back(tmp_path, value):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"start_favorite": value}))
    s = load_settings(path)
    assert s.start_favorite is None and any("start_favorite" in w for w in s.warnings)
