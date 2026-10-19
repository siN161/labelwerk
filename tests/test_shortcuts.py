"""Tastenkürzel-Verzeichnis ohne Qt (Etappe 3d-1)."""
import re

import pytest

from labelwerk import shortcuts
from labelwerk.i18n import _
from labelwerk.shortcuts import ACTIONS, SCOPES, Action


def _ids():
    return {a.id for a in ACTIONS}


# --- Verzeichnis ------------------------------------------------------------------
def test_actions_have_unique_dotted_ids_and_valid_scopes():
    ids = [a.id for a in ACTIONS]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z]+(\.[a-z0-9_]+)+", i) for i in ids)
    assert all(a.scope in SCOPES for a in ACTIONS)
    assert all(a.name.strip() for a in ACTIONS)
    assert SCOPES == ("global", "canvas", "edit")


def test_actions_cover_all_app_shortcuts():
    expected = {
        "file.print", "app.settings", "view.zoom_in", "view.zoom_out", "view.zoom_reset",
        "text.bold", "text.italic", "text.underline", "text.end_edit", "tool.select", "tool.text",
        "edit.cut", "edit.copy", "edit.paste", "edit.duplicate", "edit.delete",
        "edit.select_all", "edit.undo", "edit.redo",
        "object.nudge_left", "object.nudge_right", "object.nudge_up", "object.nudge_down",
        "object.nudge_left_coarse", "object.nudge_right_coarse",
        "object.nudge_up_coarse", "object.nudge_down_coarse",
        "object.rotate_left", "object.rotate_right",
        "object.bring_forward", "object.send_backward",
        "align.left", "align.hcenter", "align.right", "align.top", "align.vcenter",
        "align.bottom", "align.paper_left", "align.paper_hcenter", "align.paper_right",
        "align.paper_top", "align.paper_vcenter", "align.paper_bottom",
    }
    assert expected <= _ids()


@pytest.mark.parametrize("action_id, default", [
    ("text.bold", "Ctrl+B"), ("text.italic", "Ctrl+I"), ("text.underline", "Ctrl+U"),
    ("edit.copy", "Ctrl+C"), ("edit.delete", "Del"), ("edit.redo", "Ctrl+Shift+Z"),
    ("object.nudge_left", "Left"), ("object.nudge_up_coarse", "Shift+Up"),
    ("align.paper_left", ""),
])
def test_known_defaults(action_id, default):
    assert shortcuts.action(action_id).default == default


def test_action_lookup_unknown_raises():
    with pytest.raises(KeyError):
        shortcuts.action("gibt.es_nicht")


def test_all_defaults_are_well_formed_and_conflict_free():
    defaults = shortcuts.effective({})
    assert shortcuts.validate(defaults) == (defaults, [])
    assert shortcuts.conflicts(defaults) == []


# --- Wirksame Kürzel --------------------------------------------------------------
def test_effective_without_overrides_is_defaults():
    assert shortcuts.effective({}) == {a.id: a.default for a in ACTIONS}


def test_effective_applies_overrides_and_empty_removes():
    mapping = shortcuts.effective({"file.print": "Ctrl+Shift+P", "edit.delete": ""})
    assert mapping["file.print"] == "Ctrl+Shift+P"
    assert mapping["edit.delete"] == ""
    assert mapping["edit.copy"] == "Ctrl+C"


def test_effective_ignores_unknown_ids():
    assert "gibt.es_nicht" not in shortcuts.effective({"gibt.es_nicht": "Ctrl+Q"})


# --- Normalisieren ----------------------------------------------------------------
@pytest.mark.parametrize("a, b", [
    ("Ctrl+B", "ctrl+b"),
    ("Ctrl+Shift+Z", "Shift+Ctrl+Z"),
    ("Del", "Delete"),
    ("Ctrl++", "ctrl++"),
    ("Esc", "Escape"),
    ("PgUp", "PageUp"),
])
def test_normalize_is_case_and_order_insensitive(a, b):
    assert shortcuts.normalize(a) == shortcuts.normalize(b)


def test_normalize_distinguishes_modifiers():
    assert shortcuts.normalize("Ctrl+Z") != shortcuts.normalize("Ctrl+Shift+Z")
    assert shortcuts.normalize("Left") != shortcuts.normalize("Shift+Left")


@pytest.mark.parametrize("seq", ["Ctrl+B", "Del", "Shift+Left", "Ctrl++", "Ctrl+-", "Ctrl+,",
                                 "Meta+Alt+F1", "+", "Ctrl+Shift+PgDown"])
def test_well_formed(seq):
    assert shortcuts.is_well_formed(seq)


@pytest.mark.parametrize("seq", ["Ctrl+", "+B", "Ctrl++B", "Strg+B", "Ctrl+Ctrl+B", "Ctrl+Shift",
                                 "Ctrl+B+C", " ", "Ctrl+ +B", "++", "+++", "Ctrl+++"])
def test_malformed(seq):
    assert not shortcuts.is_well_formed(seq)


def test_empty_means_no_shortcut_and_is_allowed():
    assert shortcuts.is_well_formed("")
    assert shortcuts.normalize("") == ""


# --- Konflikte --------------------------------------------------------------------
def test_conflict_in_same_scope():
    mapping = shortcuts.effective({"edit.duplicate": "Ctrl+C"})
    assert shortcuts.conflicts(mapping) == [("Ctrl+C", ["edit.copy", "edit.duplicate"])]


def test_conflict_detected_case_insensitive():
    mapping = shortcuts.effective({"edit.duplicate": "ctrl+c"})
    assert shortcuts.conflicts(mapping) == [("Ctrl+C", ["edit.copy", "edit.duplicate"])]


def test_no_conflict_between_canvas_and_edit_mode():
    # Strg+B auf der Arbeitsfläche stört Fett im Schreibmodus nicht – nie beide gleichzeitig aktiv
    mapping = shortcuts.effective({"edit.duplicate": "Ctrl+B"})
    assert shortcuts.conflicts(mapping) == []


def test_edit_mode_conflicts_with_itself_and_global():
    mapping = shortcuts.effective({"text.italic": "Ctrl+B"})
    assert shortcuts.conflicts(mapping) == [("Ctrl+B", ["text.bold", "text.italic"])]
    mapping = shortcuts.effective({"view.zoom_reset": "Ctrl+U"})
    assert shortcuts.conflicts(mapping) == [("Ctrl+U", ["text.underline", "view.zoom_reset"])]


def test_formatting_and_end_edit_belong_to_edit_mode():
    for action_id in ("text.bold", "text.italic", "text.underline", "text.end_edit"):
        assert shortcuts.action(action_id).scope == "edit"
    end = shortcuts.action("text.end_edit")
    assert (_(end.name), end.default, end.fixed) == ("Schreibmodus beenden", "Esc", True)
    assert not shortcuts.action("text.bold").fixed


def test_fixed_shortcut_cannot_be_overridden():
    assert shortcuts.effective({"text.end_edit": "Ctrl+Q"})["text.end_edit"] == "Esc"
    clean, warnings = shortcuts.validate({"text.end_edit": "Ctrl+Q", "text.bold": "Ctrl+Q"})
    assert clean == {"text.bold": "Ctrl+Q"}
    assert len(warnings) == 1 and "fest" in warnings[0]


def test_global_conflicts_with_every_scope():
    mapping = shortcuts.effective({"file.print": "Ctrl+B"})
    assert shortcuts.conflicts(mapping) == [("Ctrl+B", ["file.print", "text.bold"])]
    mapping = shortcuts.effective({"file.print": "Del"})
    assert shortcuts.conflicts(mapping) == [("Del", ["edit.delete", "file.print"])]


def test_empty_shortcuts_never_conflict():
    mapping = shortcuts.effective({"edit.copy": "", "edit.cut": "", "file.print": ""})
    assert shortcuts.conflicts(mapping) == []


def test_conflicts_ignore_unknown_ids_and_report_each_sequence_once():
    mapping = shortcuts.effective({"edit.cut": "Ctrl+C", "edit.duplicate": "Ctrl+C"})
    mapping["gibt.es_nicht"] = "Ctrl+C"
    assert shortcuts.conflicts(mapping) == [("Ctrl+C", ["edit.copy", "edit.cut", "edit.duplicate"])]


# --- Prüfen -----------------------------------------------------------------------
def test_validate_keeps_good_entries():
    clean, warnings = shortcuts.validate({"file.print": "Ctrl+Shift+P", "edit.delete": ""})
    assert clean == {"file.print": "Ctrl+Shift+P", "edit.delete": ""}
    assert warnings == []


def test_validate_drops_bad_entries_with_german_warnings():
    clean, warnings = shortcuts.validate({
        "gibt.es_nicht": "Ctrl+Q",
        "edit.copy": 5,
        "edit.cut": "Strg+X",
        "edit.paste": "Ctrl+",
        "file.print": "Ctrl+Shift+P",
    })
    assert clean == {"file.print": "Ctrl+Shift+P"}
    assert len(warnings) == 4
    assert "unbekannte Aktion" in warnings[0] and "gibt.es_nicht" in warnings[0]
    assert all("ungültig" in w for w in warnings[1:])
    assert all("Standard" in w for w in warnings[1:])


def test_validate_rejects_non_dict():
    clean, warnings = shortcuts.validate(["Ctrl+B"])
    assert clean == {} and len(warnings) == 1


def test_action_is_immutable():
    with pytest.raises(AttributeError):
        Action("a.b", "A", "", "global").default = "X"


@pytest.mark.parametrize("seq", [None, 5, ["Ctrl+B"], {"a": 1}])
def test_non_strings_are_not_well_formed(seq):
    assert not shortcuts.is_well_formed(seq)
    with pytest.raises(ValueError, match="Ungültiges Tastenkürzel"):
        shortcuts.normalize(seq)


def test_conflicts_skip_non_strings():
    mapping = shortcuts.effective({"edit.copy": None, "edit.cut": 5})
    assert shortcuts.conflicts({**mapping, "edit.paste": ["Ctrl+V"]}) == []


# --- Doppelbelegung aus settings.json auflösen -----------------------------------------
def test_without_conflicts_keeps_defaults_untouched():
    defaults = shortcuts.effective({})
    assert shortcuts.without_conflicts(defaults) == (defaults, [])


def test_without_conflicts_clears_the_later_action():
    mapping = shortcuts.effective({"edit.duplicate": "Ctrl+C"})
    clean, warnings = shortcuts.without_conflicts(mapping)
    assert clean["edit.copy"] == "Ctrl+C" and clean["edit.duplicate"] == ""
    assert shortcuts.conflicts(clean) == []
    assert warnings == ["Tastenkürzel doppelt belegt: Ctrl+C (Kopieren, Duplizieren) – "
                        "„Duplizieren“ ohne Kürzel."]
    assert mapping["edit.duplicate"] == "Ctrl+C"            # Eingabe bleibt unverändert


def test_without_conflicts_global_wins_by_order_and_other_scopes_stay():
    mapping = shortcuts.effective({"tool.text": "Ctrl+Y", "text.bold": "Ctrl+Y",
                                   "file.print": "Ctrl+Y"})
    clean, warnings = shortcuts.without_conflicts(mapping)
    assert clean["file.print"] == "Ctrl+Y"                  # steht im Verzeichnis zuerst
    assert clean["tool.text"] == clean["text.bold"] == ""
    assert len(warnings) == 2 and shortcuts.conflicts(clean) == []


def test_without_conflicts_compares_normalized_forms():
    mapping = shortcuts.effective({"edit.duplicate": "ctrl+c"})
    clean, _ = shortcuts.without_conflicts(mapping)
    assert clean["edit.duplicate"] == ""


def test_fixed_shortcut_always_keeps_its_key():
    mapping = shortcuts.effective({})
    mapping["file.print"] = "Esc"                  # global: kollidiert mit jedem Bereich
    clean, warnings = shortcuts.without_conflicts(mapping)
    assert clean["text.end_edit"] == "Esc"         # fest – gewinnt immer
    assert clean["file.print"] == ""
    assert clean["tool.select"] == "Esc"           # Arbeitsfläche: kein Konflikt mit dem Schreibmodus
    assert len(warnings) == 1 and "Drucken" in warnings[0]


@pytest.mark.parametrize("seq", ["Esc", "Return", "Enter", "Tab", "Shift+Tab", "Backtab"])
def test_keys_reserved_for_editing_are_rejected(seq):
    clean, warnings = shortcuts.validate({"file.print": seq})
    assert clean == {}
    assert len(warnings) == 1 and "nicht belegbar" in warnings[0]


def test_reserved_key_is_fine_as_the_actions_own_default():
    assert shortcuts.validate({"tool.select": "Esc"}) == ({"tool.select": "Esc"}, [])
