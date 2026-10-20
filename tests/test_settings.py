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
    assert s.check_media_on_start is False                 # valid values stay
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
    blocker.write_text("x")                                # folder cannot be created
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
    """Whether the label fits the connected printer is checked by GUI and CLI (two printers)."""
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


# --- Shortcuts -------------------------------------------------------------------
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


# --- Insert images ----------------------------------------------------------------
def test_image_import_defaults_and_roundtrip(tmp_path):
    s = Settings()
    assert (s.image_crop, s.image_rotate) == (True, False)     # crop, do not rotate
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


# --- Symbols ------------------------------------------------------------------------
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
    """A broken entry does not cost the whole list (otherwise favourites would be gone on the next
    save)."""
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
    assert load_settings(path).margin_mm == 3.0          # old file intact
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]


# --- Files ------------------------------------------------------------------------
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


def test_cups_printer_and_its_options_are_kept(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(printer="cups:Dymo", last_model="cups:Dymo", label_id="57x32mm@300",
                           printer_options={"cups:Dymo": {"CutMedia": "EndOfJob"}}), path)
    s = load_settings(path)
    assert (s.printer, s.last_model, s.label_id) == ("cups:Dymo", "cups:Dymo", "57x32mm@300")
    assert s.printer_options == {"cups:Dymo": {"CutMedia": "EndOfJob"}} and s.warnings == []


def test_show_all_cups_printers(tmp_path):
    path = tmp_path / "settings.json"
    assert Settings().cups_all is False                # office printers hidden by default
    save_settings(Settings(cups_all=True), path)
    assert load_settings(path).cups_all is True
    path.write_text(json.dumps({"cups_all": "ja"}))
    s = load_settings(path)
    assert s.cups_all is False and any("cups_all" in w for w in s.warnings)


@pytest.mark.parametrize("bad", [[], {"cups:Dymo": "x"}, {"cups:Dymo": {"CutMedia": 3}},
                                 {"cups:Dymo": {"CutMedia": "Off -o x=y"}},
                                 {"cups:Dymo": {"": "x"}}])
def test_bad_printer_options_fall_back(tmp_path, bad):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"printer_options": bad}))
    s = load_settings(path)
    assert s.printer_options == {} and s.warnings


def test_network_zebra_is_kept(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"network_printers": [
        {"name": "Lager", "host": "10.0.0.8", "model": "zpl:203"},
        {"name": "x", "host": "10.0.0.9", "model": "zpl:250"}]}))
    s = load_settings(path)
    assert s.network_printers == [{"name": "Lager", "host": "10.0.0.8", "model": "zpl:203"}]
    assert s.warnings


def test_zebra_printer_and_empty_mode_are_kept(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(printer="zpl+file:///dev/usb/lp2", printer_options={
        "zpl:203": {"mode": ""}, "cups:Dymo": {"CutMedia": "EndOfJob"}}), path)
    s = load_settings(path)
    assert s.printer == "zpl+file:///dev/usb/lp2" and s.warnings == []
    assert s.printer_options == {"zpl:203": {"mode": ""}, "cups:Dymo": {"CutMedia": "EndOfJob"}}


def test_one_bad_printer_option_keeps_the_others(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"printer_options": {
        "cups:Dymo": {"CutMedia": "EndOfJob", "X": "a b"}, "zpl:203": "kaputt"}}))
    s = load_settings(path)
    assert s.printer_options == {"cups:Dymo": {"CutMedia": "EndOfJob"}} and s.warnings


def test_fonts_all_default_and_validation(tmp_path):
    path = tmp_path / "s.json"
    assert load_settings(path).fonts_all is False              # short font list
    save_settings(Settings(fonts_all=True), path)
    assert load_settings(path).fonts_all is True
    path.write_text(json.dumps({"fonts_all": "ja"}))
    s = load_settings(path)
    assert s.fonts_all is False and s.warnings


def test_image_defaults_for_new_images(tmp_path):
    s = Settings()
    assert (s.image_mode, s.image_threshold) == ("line", 128)  # as before: line, middle
    path = tmp_path / "s.json"
    save_settings(Settings(image_mode="photo", image_threshold=90), path)
    loaded = load_settings(path)
    assert (loaded.image_mode, loaded.image_threshold) == ("photo", 90)
    assert loaded.warnings == []


@pytest.mark.parametrize("raw", [{"image_mode": "grau"}, {"image_threshold": 256},
                                 {"image_threshold": -1}, {"image_threshold": True},
                                 {"image_threshold": 12.5}, {"image_threshold": "90"}])
def test_invalid_image_defaults_fall_back_with_warning(tmp_path, raw):
    path = tmp_path / "s.json"
    path.write_text(json.dumps(raw))
    s = load_settings(path)
    assert (s.image_mode, s.image_threshold) == ("line", 128)
    assert len(s.warnings) == 1 and next(iter(raw)) in s.warnings[0]


# --- Tab at start --------------------------------------------------------------
def test_start_tool_defaults_and_roundtrip(tmp_path):
    from labelwerk.settings import START_TOOLS
    s = Settings()
    assert (s.start_tool, s.last_tool) == ("paper", "")         # as before: paper
    assert START_TOOLS[0] == "last" and "paper" in START_TOOLS
    path = tmp_path / "s.json"
    save_settings(Settings(start_tool="last", last_tool="series"), path)
    loaded = load_settings(path)
    assert (loaded.start_tool, loaded.last_tool) == ("last", "series")
    assert loaded.warnings == []


@pytest.mark.parametrize("raw", [{"start_tool": "druck"}, {"start_tool": ""}, {"start_tool": 3}])
def test_invalid_start_tool_falls_back_with_warning(tmp_path, raw):
    path = tmp_path / "s.json"
    path.write_text(json.dumps(raw))
    s = load_settings(path)
    assert s.start_tool == "paper"
    assert len(s.warnings) == 1 and "start_tool" in s.warnings[0]


@pytest.mark.parametrize("value", ["last", "druck", 3, None])
def test_invalid_last_tool_is_dropped_quietly(tmp_path, value):
    """Last used tab is only a remembered value: invalid → empty, without notice."""
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"last_tool": value}))
    s = load_settings(path)
    assert s.last_tool == "" and s.warnings == []


def test_start_tool_needs_a_restart():
    from labelwerk.settings import RESTART_KEYS, restart_pending, started_values
    assert "start_tool" in RESTART_KEYS
    started = started_values(Settings(start_tool="paper"))
    assert started["start_tool"] == "paper"
    language = started["language"]
    assert not restart_pending({**started, "start_tool": "paper"}, started)
    assert restart_pending({**started, "start_tool": "last"}, started)


# --- System file dialog ---------------------------------------------------------
def test_system_file_dialog_default_validation_and_restart(tmp_path):
    from labelwerk.settings import RESTART_KEYS, started_values
    path = tmp_path / "s.json"
    assert load_settings(path).system_file_dialog is False       # own dialog with preview
    save_settings(Settings(system_file_dialog=True), path)
    assert load_settings(path).system_file_dialog is True
    path.write_text(json.dumps({"system_file_dialog": "ja"}))
    s = load_settings(path)
    assert s.system_file_dialog is False and s.warnings
    assert "system_file_dialog" in RESTART_KEYS
    assert started_values(Settings(system_file_dialog=True))["system_file_dialog"] is True


@pytest.mark.parametrize("raw, expected", [({"system_file_dialog": True}, True),
                                           ({"system_file_dialog": False}, False),
                                           ({"system_file_dialog": "ja"}, False), ([], False),
                                           (None, False)])
def test_configured_file_dialog_is_read_before_everything(tmp_path, raw, expected):
    from labelwerk.settings import configured_file_dialog
    path = tmp_path / "s.json"
    if raw is not None:
        path.write_text(json.dumps(raw))
    assert configured_file_dialog(path) is expected


# --- silent saving of single fields ------------------------------------------------
def test_update_settings_keeps_what_another_instance_saved(tmp_path):
    """Instance A silently remembers the tab; instance B has meanwhile saved the theme –
    A writes only its field and leaves B's change alone."""
    from labelwerk.settings import update_settings
    path = tmp_path / "s.json"
    save_settings(Settings(theme="rawblock"), path)
    a = load_settings(path)                                    # instance A starts
    save_settings(Settings(theme="classic"), path)              # instance B saves
    a.last_tool = "series"
    update_settings(path, last_tool=a.last_tool)
    s = load_settings(path)
    assert (s.theme, s.last_tool) == ("classic", "series")


def test_update_settings_keeps_unknown_and_replaces_invalid_entries(tmp_path):
    """Fields of a newer version stay in the file as they are; invalid values become
    the default (without in-memory state) – the message on loading would otherwise come every time."""
    from labelwerk.settings import update_settings
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"theme": "classic", "neu": [1, 2], "start_zoom": 9999}))
    update_settings(path, recent_files=["/a.labelwerk"])
    raw = json.loads(path.read_text())
    assert raw == {"theme": "classic", "neu": [1, 2], "start_zoom": 200,
                   "recent_files": ["/a.labelwerk"]}


def test_update_settings_without_file_writes_base(tmp_path):
    from labelwerk.settings import update_settings
    path = tmp_path / "neu" / "s.json"
    update_settings(path, base=Settings(theme="classic"), last_tool="text")
    s = load_settings(path)
    assert (s.theme, s.last_tool) == ("classic", "text")


def test_update_settings_with_unreadable_file_writes_base(tmp_path):
    """Broken file: nothing to merge – the in-memory state (``base``) applies."""
    from labelwerk.settings import update_settings
    path = tmp_path / "s.json"
    path.write_text("{kaputt")
    update_settings(path, base=Settings(theme="classic"), last_tool="text")
    s = load_settings(path)
    assert (s.theme, s.last_tool, s.warnings) == ("classic", "text", [])


def test_update_settings_rejects_unknown_fields(tmp_path):
    from labelwerk.settings import update_settings
    with pytest.raises(KeyError):
        update_settings(tmp_path / "s.json", gibtsnicht=1)


def test_update_settings_cleans_invalid_and_old_keys(tmp_path):
    """Silent saving cleans up what loading only reported: invalid values become
    the in-memory value, the old font size is converted – unknown fields stay."""
    from labelwerk.settings import update_settings
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"font_size": 100, "theme": "nope", "zukunft": 1}))
    base = load_settings(path)
    assert base.warnings                                     # reported on loading
    update_settings(path, base, last_tool="text")
    data = json.loads(path.read_text())
    assert "font_size" not in data and data["font_size_pt"] == 24
    assert data["theme"] == base.theme == "rawblock"
    assert data["zukunft"] == 1 and data["last_tool"] == "text"
    assert load_settings(path).warnings == []


# --- Hide tabs --------------------------------------------------------------
def test_hidden_tools_default_and_roundtrip(tmp_path):
    from labelwerk.settings import HIDEABLE_TOOLS
    assert Settings().hidden_tools == [] and "file" not in HIDEABLE_TOOLS
    path = tmp_path / "s.json"
    save_settings(Settings(hidden_tools=["series", "barcode"]), path)
    loaded = load_settings(path)
    assert loaded.hidden_tools == ["series", "barcode"] and loaded.warnings == []


@pytest.mark.parametrize("raw, expected", [
    (["file", "paper", "series"], ["series"]),          # FILE/PAPER always stay
    (["druck", 3, None, "text", "text"], ["text"]),     # unknown, duplicate
    ("series", []), (None, []), ({"a": 1}, []),
])
def test_invalid_hidden_tools_are_dropped_quietly(tmp_path, raw, expected):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"hidden_tools": raw}))
    s = load_settings(path)
    assert s.hidden_tools == expected and s.warnings == []


def test_update_settings_cleans_hidden_tools(tmp_path):
    from labelwerk.settings import update_settings
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"hidden_tools": ["paper", "layout"]}))
    update_settings(path, Settings(), last_tool="text")
    assert json.loads(path.read_text())["hidden_tools"] == ["layout"]
