"""Translations: .po reader, language choice, numbers, completeness of the language files."""
import importlib.util
import sys
from pathlib import Path

import pytest

from labelwerk import i18n

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("i18n_tool", ROOT / "tools" / "i18n.py")
tool = importlib.util.module_from_spec(_spec)
sys.modules["i18n_tool"] = tool                  # dataclasses need the module
_spec.loader.exec_module(tool)

PO = r'''
msgid ""
msgstr ""
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

#: src/labelwerk/x.py:1
msgid "Label"
msgstr "Etikett"

msgctxt "verb"
msgid "Cut"
msgstr "Schneiden"

msgid "Cut"
msgstr "Ausschneiden"

msgid "{n} label"
msgid_plural "{n} labels"
msgstr[0] "{n} Etikett"
msgstr[1] "{n} Etiketten"

msgid ""
"Two\n"
"lines \"quoted\""
msgstr "Zwei\nZeilen „zitiert“"

msgid "Not yet"
msgstr ""

#, fuzzy
msgid "Unsure"
msgstr "Unsicher"

#~ msgid "Old"
#~ msgstr "Alt"
'''


def test_parse_po():
    catalog = i18n.parse_po(PO, "de")
    assert catalog.messages[("", "Label")] == ["Etikett"]
    assert catalog.messages[("verb", "Cut")] == ["Schneiden"]
    assert catalog.messages[("", "Cut")] == ["Ausschneiden"]
    assert catalog.messages[("", "{n} label")] == ["{n} Etikett", "{n} Etiketten"]
    assert catalog.messages[("", 'Two\nlines "quoted"')] == ["Zwei\nZeilen „zitiert“"]
    assert ("", "Not yet") not in catalog.messages and ("", "Unsure") not in catalog.messages
    assert ("", "Old") not in catalog.messages
    assert (catalog.plural_index(1), catalog.plural_index(0), catalog.plural_index(5)) == (0, 1, 1)


@pytest.mark.parametrize("bad", ['msgid "x"\nmsgstr "y', 'msgid "x"\nfoo "y"', '"lose"',
                                 'msgid ""\nmsgstr "Plural-Forms: nplurals=2; plural=import os;\\n"'])
def test_broken_po_is_an_error(bad):
    with pytest.raises(i18n.PoError):
        i18n.parse_po(bad)


def test_translate_with_context_plural_and_fallback(monkeypatch):
    monkeypatch.setattr(i18n, "_catalog", i18n.parse_po(PO, "de"))
    assert i18n._("Label") == "Etikett" and i18n._("Unknown") == "Unknown"
    assert i18n.pgettext("verb", "Cut") == "Schneiden" and i18n._("Cut") == "Ausschneiden"
    assert i18n.ngettext("{n} label", "{n} labels", 1).format(n=1) == "1 Etikett"
    assert i18n.ngettext("{n} label", "{n} labels", 3).format(n=3) == "3 Etiketten"
    assert i18n.ngettext("{n} box", "{n} boxes", 3) == "{n} boxes"
    assert i18n.N_("Label") == "Label"


@pytest.mark.parametrize("env, code", [({"LANG": "de_DE.UTF-8"}, "de"), ({"LANG": "de_AT"}, "de"),
                                       ({"LANGUAGE": "fr:de", "LANG": "fr_FR"}, "de"),
                                       ({"LC_ALL": "C", "LANG": "de_DE.UTF-8"}, "en"),
                                       ({"LANG": "fr_FR.UTF-8"}, "en"), ({}, "en"),
                                       ({"LC_MESSAGES": "en_GB.UTF-8", "LANG": "de_DE"}, "en")])
def test_system_language(env, code):
    assert i18n.system_language(env) == code


def test_set_language_and_numbers(monkeypatch):
    assert i18n.set_language("en") == "en" and i18n._("Label") == "Label"
    assert i18n.number(3.5) == "3.5" and i18n.number(2, 1) == "2.0" and i18n.decimal() == "."
    assert i18n.set_language("de") == "de"
    assert i18n.number(3.5) == "3,5" and i18n.decimal() == ","
    assert i18n.set_language("xx") == "en"                     # unknown: English
    monkeypatch.setenv("LANGUAGE", "de")
    assert i18n.set_language("") == "de"                       # "" = system language
    assert i18n.available() == ["de", "en"]


def test_broken_language_file_falls_back(tmp_path, monkeypatch, capsys):
    (tmp_path / "de.po").write_text('msgid "x"\nfoo')
    monkeypatch.setattr(i18n, "PO_DIR", tmp_path)
    assert i18n.set_language("de") == "en"
    assert "unreadable" in capsys.readouterr().err


# --- Language files ----------------------------------------------------------------------------
def test_every_text_is_translated():
    assert tool.problems() == []


def test_extract_finds_all_kinds(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m.py").write_text(
        'from labelwerk.i18n import _, N_, ngettext, pgettext\n'
        'A = N_("Table")\n'
        'def f(n):\n'
        '    return _("Hello {name}"), ngettext("{n} file", "{n} files", n), pgettext("verb", "Cut"),'
        ' _(variable)\n')
    found = tool.extract(tmp_path / "pkg")
    assert sorted(found) == [("", "Hello {name}"), ("", "Table"), ("", "{n} file"), ("verb", "Cut")]
    assert found[("", "{n} file")].plural == "{n} files"


def test_placeholders_must_match():
    assert tool.placeholders("{label!r} passt nicht ({model})") == ["{label!r}", "{model}"]
    assert tool.placeholders("100 %") == [] and tool.placeholders("{{wörtlich}}") == []


def test_numbers_follow_the_language():
    from labelwerk.labels import format_mm, mm_text
    from labelwerk.series import numbering_table
    i18n.set_language("de")
    assert (format_mm(300), mm_text(101.6), i18n.thousands(10000)) == ("25,4", "101,6", "10.000")
    i18n.set_language("en")
    assert (format_mm(300), mm_text(101.6), i18n.thousands(10000)) == ("25.4", "101.6", "10,000")
    assert i18n.parse_number("3,5") == i18n.parse_number("3.5") == 3.5


def test_no_german_text_outside_the_translation():
    assert tool.german_leftovers() == []


def test_english_samples(monkeypatch):
    """Spot checks: messages in English when the language is English."""
    from labelwerk import zpl
    from labelwerk.labels import get_label
    from labelwerk.printer import PrintError, print_image
    from PIL import Image

    def never(*args):
        raise AssertionError("darf nichts senden")
    monkeypatch.setattr(zpl, "send", never)
    i18n.set_language("en")
    assert get_label("54x25mm@300").description == "54 × 25 mm · 300 dpi"
    with pytest.raises(PrintError, match="does not fit the printer"):
        print_image(Image.new("1", (10, 10), 1), "62", model="zpl:203", printer="zpl+tcp://x")


def test_update_keeps_translator_work(tmp_path, monkeypatch):
    """``update`` keeps the translators' comments, uncertain (fuzzy) and obsolete entries."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m.py").write_text('from labelwerk.i18n import _\nA = _("Hello")\nB = _("New")\n')
    po_dir = tmp_path / "po"
    po_dir.mkdir()
    (po_dir / "de.po").write_text('msgid ""\nmsgstr ""\n"Language: de\\n"\n"Plural-Forms: nplurals=2; '
                                  'plural=(n != 1);\\n"\n\n# geprüft von Anna\n#, fuzzy\nmsgid "Hello"\n'
                                  'msgstr "Hallo"\n\nmsgid "Gone"\nmsgstr "Weg"\n', encoding="utf-8")
    monkeypatch.setattr(tool, "PO_DIR", po_dir)
    monkeypatch.setattr(tool, "POT", po_dir / "labelwerk.pot")
    monkeypatch.setattr(tool, "SRC", tmp_path / "pkg")
    monkeypatch.setattr(tool, "extract", lambda src=None, real=tool.extract: real(tmp_path / "pkg"))
    tool.update()
    text = (po_dir / "de.po").read_text(encoding="utf-8")
    assert "# geprüft von Anna\n" in text and "#, fuzzy\nmsgid \"Hello\"\nmsgstr \"Hallo\"" in text
    assert 'msgid "New"\nmsgstr ""' in text and '#~ msgid "Gone"\n#~ msgstr "Weg"' in text


def test_po_escapes_like_c():
    assert i18n.unquote(r'"a\nb \"q\" \101 \x42 \\"', "") == 'a\nb "q" A B \\'
    with pytest.raises(i18n.PoError):
        i18n.unquote('"a \\q"', "")
    with pytest.raises(i18n.PoError):
        i18n.unquote('"a" "b"', "")                 # not Python syntax


@pytest.mark.parametrize("env, code", [({"LANGUAGE": "de", "LC_ALL": "C"}, "en"),
                                       ({"LANGUAGE": "de"}, "en"),
                                       ({"LANGUAGE": "de", "LANG": "en_US.UTF-8"}, "de")])
def test_system_language_like_gnu(env, code):
    assert i18n.system_language(env) == code


def test_numbers_in_label_content_follow_the_region():
    assert i18n.content_decimal({"LC_ALL": "de_DE.UTF-8"}) == ","
    assert i18n.content_decimal({"LANG": "en_US.UTF-8", "LC_NUMERIC": "fr_FR.UTF-8"}) == ","
    assert i18n.content_decimal({"LANG": "en_GB.UTF-8"}) == "." and i18n.content_decimal({}) == "."


def test_restart_pending():
    from labelwerk.settings import restart_pending
    started = {"language": "de", "start_zoom": 200, "start_tool": "paper",
               "system_file_dialog": False}

    def pending(**changed):
        return restart_pending({**started, **changed}, started)
    assert not pending(language="")                           # automatic = system language (de)
    assert not pending()
    assert pending(language="en")
    assert pending(start_zoom=150)
    assert pending(start_tool="last")
    assert pending(system_file_dialog=True)
