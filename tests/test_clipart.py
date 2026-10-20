"""Symbol library (stage 3d-2c): catalogue, licences, search, own folder."""
import zipfile
from xml.etree import ElementTree

import pytest
from PIL import Image

from labelwerk import clipart
from labelwerk.clipart import ALLOWED_LICENSES, GROUPS, Symbol
from labelwerk.i18n import _


def test_groups_in_fixed_order_with_german_names():
    assert [(key, _(name)) for key, name in GROUPS] == [     # names translated on display
        ("elektro", "Elektro"), ("versand", "Versand"), ("sicherheit", "Sicherheit"),
        ("allgemein", "Allgemein"), ("eigene", "Eigene")]


@pytest.mark.parametrize("group, at_least", [("elektro", 20), ("versand", 10),
                                              ("sicherheit", 150), ("allgemein", 4000)])
def test_every_group_is_filled(group, at_least):
    assert len(clipart.symbols(group)) >= at_least


def test_every_symbol_has_source_and_allowed_licence():
    for symbol in clipart.catalog():
        assert symbol.license in ALLOWED_LICENSES, symbol.id
        assert symbol.source and symbol.author and symbol.name, symbol.id


def test_ids_are_unique():
    ids = [s.id for s in clipart.catalog()]
    assert len(ids) == len(set(ids))


def test_every_symbol_is_a_readable_svg_in_the_archive():
    with zipfile.ZipFile(clipart.ARCHIVE) as archive:
        names = set(archive.namelist())
        for symbol in clipart.catalog():
            assert symbol.file in names, symbol.id
            root = ElementTree.fromstring(archive.read(symbol.file))
            assert root.tag.endswith("svg"), symbol.id


def test_no_brand_logos():
    assert not [s for s in clipart.symbols("allgemein") if s.id.startswith("tabler/outline/brand-")]


@pytest.mark.parametrize("name", ["mickey", "lego", "olympics", "playstation-x", "xbox-a",
                                  "bluetooth", "usb", "nfc", "creative-commons", "ce", "steam",
                                  "device-imac", "device-ipad", "pokeball", "currency-tether",
                                  "michelin-star", "michelin-star-green", "michelin-bib-gourmand",
                                  "currency-xrp", "e-passport", "wash", "wash-hand", "wash-dry",
                                  "wash-temperature-3", "wash-tumble-dry", "ironing",
                                  "ironing-steam", "bleach", "bleach-chlorine"])
def test_trademarks_are_left_out(name):
    """Trademarks and protected symbols outside the Tabler category "Brand" are missing too."""
    assert clipart.find(f"tabler/outline/{name}") is None


def test_washing_machine_stays_but_care_symbols_do_not():
    """Textile care symbols are trademarks (GINETEX); the washing machine is not."""
    assert clipart.find("tabler/outline/wash-machine") is not None
    assert not [s for s in clipart.symbols("allgemein")
                if s.id.startswith(("tabler/outline/wash-", "tabler/outline/ironing"))
                and s.id != "tabler/outline/wash-machine"]


def test_licences_file_names_mit_text_and_every_commons_file():
    text = clipart.LICENSES.read_text(encoding="utf-8")
    assert "MIT License" in text and "Paweł Kuna" in text
    for symbol in clipart.catalog():
        if symbol.id.startswith(("iso7000/", "iso7010/")):
            assert symbol.source in text, symbol.id


def test_own_drawings_are_cc0_and_nothing_is_gpl():
    for symbol in clipart.catalog():
        assert symbol.license != "GPL-3.0-or-later"
        if symbol.id.startswith("labelwerk/"):
            assert symbol.license == "CC0", symbol.id


def test_archive_has_no_orphan_files():
    with zipfile.ZipFile(clipart.ARCHIVE) as archive:
        files = set(archive.namelist()) - {"catalog.json"}
    assert files == {s.file for s in clipart.catalog()}


def test_first_aid_sign_is_there():
    assert "iso7010/E003" in _ids(clipart.search("Erste Hilfe"))


def test_data_returns_the_svg_bytes():
    symbol = clipart.find("labelwerk/schutzleiter")
    assert symbol.group == "elektro" and symbol.name == "Schutzleiter (PE)"
    assert clipart.data(symbol).startswith(b"<svg") and clipart.is_vector(symbol)


def test_find_unknown_id_is_none():
    assert clipart.find("gibt/es/nicht") is None


# --- Search ----------------------------------------------------------------------------
def _ids(results):
    return [s.id for s in results]


def test_search_german_name_and_part_of_word():
    assert "iso7000/0621" in _ids(clipart.search("zerbrech"))
    assert "iso7010/W012" in _ids(clipart.search("Spannung"))


def test_search_ignores_case_and_umlaut_spelling():
    assert "iso7000/0626" in _ids(clipart.search("NAESSE"))
    assert "iso7000/0626" in _ids(clipart.search("nässe"))


def test_search_german_synonym_finds_tabler_icon():
    assert _ids(clipart.search("Haus"))[:3].count("tabler/outline/home") == 1


def test_search_english_tag():
    assert "tabler/outline/home" in _ids(clipart.search("house"))


def test_search_all_words_must_match():
    results = clipart.search("warnung spannung")
    assert results
    for s in results:
        text = (s.name + " " + s.subgroup + " " + " ".join(s.keywords)).lower()
        assert "warn" in text and "spannung" in text


@pytest.mark.parametrize("text, wanted", [("PE", "labelwerk/schutzleiter"),
                                          ("AC", "labelwerk/wechselstrom"),
                                          ("Erde", "labelwerk/schutzleiter"),
                                          ("LED", "labelwerk/diode")])
def test_exact_terms_come_first(text, wanted):
    """Technical abbreviations: exact hit (name word, search term) before partial words ("pe" in "pencil")."""
    assert wanted in _ids(clipart.search(text))[:3]


def test_search_within_group():
    assert all(s.group == "elektro" for s in clipart.search("blitz", "elektro"))
    assert clipart.search("blitz", "elektro")


def test_names_first():
    """Hits in the name before hits only in search terms."""
    results = clipart.search("motor")
    assert results[0].name.lower().startswith("motor")


def test_empty_search_is_the_whole_group():
    assert clipart.search("", "versand") == clipart.symbols("versand")


# --- own folder -------------------------------------------------------------------
def test_own_folder_follows_xdg_data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert clipart.own_dir() == tmp_path / "labelwerk" / "symbole"


def test_own_symbols_svg_and_png(tmp_path):
    (tmp_path / "Firma.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
    Image.new("RGB", (8, 8), "black").save(tmp_path / "stempel.PNG")
    (tmp_path / "notiz.txt").write_text("kein Symbol")
    own = clipart.own_symbols(tmp_path)
    assert [(s.name, s.group, s.id) for s in own] == [
        ("Firma", "eigene", "ordner/Firma.svg"), ("stempel", "eigene", "ordner/stempel.PNG")]
    assert clipart.is_vector(own[0]) and not clipart.is_vector(own[1])
    assert clipart.data(own[1]).startswith(b"\x89PNG")


def test_own_symbols_skip_hidden_files_and_sort_without_case(tmp_path):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
    for name in ("Zebra.svg", "apfel.svg", ".versteckt.svg", "._apfel.svg"):
        (tmp_path / name).write_text(svg)
    assert [s.name for s in clipart.own_symbols(tmp_path)] == ["apfel", "Zebra"]


def test_own_symbols_in_missing_folder_are_empty(tmp_path):
    assert clipart.own_symbols(tmp_path / "fehlt") == []


def test_own_symbols_are_found_by_search(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    folder = clipart.own_dir()
    folder.mkdir(parents=True)
    (folder / "Werkstatt-Logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    assert _ids(clipart.search("werkstatt")) == ["ordner/Werkstatt-Logo.svg"]
    assert clipart.find("ordner/Werkstatt-Logo.svg").name == "Werkstatt-Logo"


# --- Recently used --------------------------------------------------------------
def test_add_recent_puts_newest_first_without_duplicates_and_limit():
    recent = [f"s{i}" for i in range(24)]
    assert clipart.add_recent(recent, "s5")[:2] == ["s5", "s0"]
    assert len(clipart.add_recent(recent, "neu")) == 24
    assert clipart.add_recent(recent, "neu")[0] == "neu" and "s23" not in clipart.add_recent(recent, "neu")


def test_resolve_skips_unknown_ids():
    assert [s.id for s in clipart.resolve(["labelwerk/erde", "weg/da", "iso7000/0621"])] == [
        "labelwerk/erde", "iso7000/0621"]


def test_symbol_is_hashable_value():
    a = clipart.find("labelwerk/erde")
    assert isinstance(a, Symbol) and {a: 1}[clipart.find("labelwerk/erde")] == 1


def test_names_in_the_language_and_search_in_both():
    from labelwerk import i18n
    i18n.set_language("en")
    earth = clipart.find("labelwerk/erde")
    assert (earth.name, earth.subgroup) == ("Earth", "Electrical")
    assert clipart.find("iso7000/0621").name == "Fragile"
    found = [s.id for s in clipart.search("erde", "elektro")]
    assert found[0] == "labelwerk/erde"                     # searched in German, displayed in English
    i18n.set_language("de")
    earth = clipart.find("labelwerk/erde")
    assert (earth.name, earth.subgroup) == ("Erde", "Elektro")
    assert clipart.search("earth", "elektro")[0].id == "labelwerk/erde"
    assert clipart.search("fragile", "versand")[0].id == "iso7000/0621"
    tabler = clipart.find("tabler/filled/home")
    assert tabler.name == "home (gefüllt)" and "home (filled)" in tabler.names


def test_every_symbol_has_both_languages():
    import json
    import zipfile
    entries = json.loads(zipfile.ZipFile(clipart.ARCHIVE).read("catalog.json"))["symbols"]
    for e in entries:
        assert set(e["names"]) == {"de", "en"} and all(e["names"].values()), e["id"]
        assert set(e["subgroups"]) == {"de", "en"} and all(e["subgroups"].values()), e["id"]


def test_own_drawings_show_their_source_in_the_language():
    from labelwerk import i18n
    i18n.set_language("en")
    assert clipart.find("labelwerk/erde").source == "labelwerk (own drawing)"
    i18n.set_language("de")
    assert clipart.find("labelwerk/erde").source == "labelwerk (eigene Zeichnung)"
