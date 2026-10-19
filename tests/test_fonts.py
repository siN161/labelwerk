import shutil

import pytest

from labelwerk import fonts

needs_fontconfig = pytest.mark.skipif(shutil.which("fc-match") is None, reason="kein fontconfig")


def test_families_contains_default():
    assert fonts.DEFAULT_FAMILY in fonts.families()


@needs_fontconfig
def test_resolve_default_bold_is_dejavu_bold():
    match = fonts.resolve(None, True, False)
    assert match.path.endswith("DejaVuSans-Bold.ttf")
    assert match.family == "DejaVu Sans" and match.bold and not match.italic


@needs_fontconfig
def test_resolve_regular_differs_from_bold():
    assert fonts.resolve("DejaVu Sans", False, False).path != fonts.resolve("DejaVu Sans", True, False).path


@needs_fontconfig
def test_unknown_family_is_substituted():
    match = fonts.resolve("GibtsGarNicht 4711", False, False)
    assert match.family != "GibtsGarNicht 4711"
    assert match.path


def test_without_fontconfig_falls_back_to_dejavu(monkeypatch):
    monkeypatch.setattr(fonts, "_run", lambda *a: None)
    fonts.resolve.cache_clear()
    fonts._families.cache_clear()
    try:
        assert fonts.families() == ["DejaVu Sans"]
        assert fonts.resolve(None, True, False).path.endswith("DejaVuSans-Bold.ttf")
    finally:
        fonts.resolve.cache_clear()
        fonts._families.cache_clear()


def test_load_is_cached():
    path = fonts.resolve(None, True, False).path
    assert fonts.load(path, 40) is fonts.load(path, 40)


def test_escape_maskiert_sonderzeichen():
    assert fonts._escape("A-B:C,D=E\\F") == "A\\-B\\:C\\,D\\=E\\\\F"


@needs_fontconfig
def test_families_ohne_backslash():
    assert not [n for n in fonts.families() if "\\" in n]


@needs_fontconfig
def test_resolve_rundreise_fuer_familien_mit_bindestrich():
    namen = [n for n in fonts.families() if "-" in n]
    if not namen:
        pytest.skip("keine Familie mit Bindestrich installiert")
    for name in namen:
        assert fonts.resolve(name, False, False).family == name


@needs_fontconfig
def test_resolve_dejavu_ohne_kursivdatei_meldet_nicht_kursiv():
    match = fonts.resolve("DejaVu Sans", False, True)
    if match.italic:
        pytest.skip("kursive DejaVu-Datei installiert")
    assert match.italic is False and match.bold is False


def test_load_unloadable_font_raises_fontloaderror(monkeypatch):
    from PIL import ImageFont

    def broken(path, size):
        raise OSError("unknown file format")
    monkeypatch.setattr(ImageFont, "truetype", broken)
    fonts.load.cache_clear()
    with pytest.raises(fonts.FontLoadError) as e:
        fonts.load("/etc/hostname", 20)
    assert isinstance(e.value, ValueError)
    assert "„/etc/hostname“ kann nicht geladen werden" in str(e.value)
    assert "unknown file format" in str(e.value)
    fonts.load.cache_clear()


def test_render_document_with_unloadable_font_raises_valueerror(monkeypatch):
    from PIL import ImageFont

    from labelwerk.document import Document, TextObject
    from labelwerk.render import render_document

    def broken(path, size):
        raise OSError("invalid pixel size")
    monkeypatch.setattr(ImageFont, "truetype", broken)
    fonts.load.cache_clear()
    with pytest.raises(ValueError, match="kann nicht geladen werden"):
        render_document(Document("62", objects=[TextObject.plain("Hallo")]))
    fonts.load.cache_clear()


# --- kurze Liste (fontconfig-Ausgabe gefälscht) --------------------------------------
_GERMAN = "\n".join([
    "DejaVu Sans|False", "DejaVu Sans|False", "Liberation Sans|False", "Fira Sans Condensed|False",
    "DejaVu Sans Mono for Powerline|False", "Ubuntu Mono derivative Powerline|False",
    "Hack Nerd Font|False", "Hack Nerd Font Mono|False", "Twemoji|True",
    "D050000L|False", "Standard Symbols PS|False", "OpenSymbol|False", "Wingdings 3|False",
    "AR PL UKai TW MBE|False", "AR PL UMing CN|False", "Noto Sans CJK JP|False",
    "Noto Serif CJK TC|False", "Noto Sans Mono CJK KR|False", "Noto Sans|", "Ubuntu|False", ""])
_ALL = "Sans Serif\nNoto Sans Arabic\nDejaVu Sans\nNoto Sans CJK JP\nDejaVu Sans\n"


@pytest.fixture
def fake_fc(monkeypatch):
    calls = []

    def run(*args):
        calls.append(args)
        return _ALL if args[-1] == ":" else _GERMAN
    monkeypatch.setattr(fonts, "_run", run)
    fonts._families.cache_clear()
    yield calls
    fonts._families.cache_clear()


def test_short_list_only_german_fonts_without_copies_symbols_and_cjk_regions(fake_fc):
    assert fonts.families() == ["DejaVu Sans", "Fira Sans Condensed", "Liberation Sans",
                                "Noto Sans", "Ubuntu"]
    assert fake_fc[0][-1] == ":lang=de"                  # nur Schriften mit deutschen Zeichen


def test_all_fonts_lists_every_family(fake_fc):
    assert fonts.families(all=True) == ["DejaVu Sans", "Noto Sans Arabic", "Noto Sans CJK JP",
                                        "Sans Serif"]
    assert fake_fc[0][-1] == ":"


def test_short_list_keeps_default_when_everything_is_filtered(monkeypatch):
    monkeypatch.setattr(fonts, "_run", lambda *a: "Hack Nerd Font|False\n")
    fonts._families.cache_clear()
    try:
        assert fonts.families() == [fonts.DEFAULT_FAMILY]
    finally:
        fonts._families.cache_clear()


@needs_fontconfig
def test_short_list_is_part_of_all_fonts():
    short = fonts.families()
    assert short and set(short) <= set(fonts.families(all=True))
    assert not [n for n in short if "Powerline" in n]


def test_families_cache_one_entry_per_list_however_called(fake_fc):
    for call in (lambda: fonts.families(), lambda: fonts.families(False),
                 lambda: fonts.families(all=False), lambda: fonts.families(True),
                 lambda: fonts.families(all=True), lambda: fonts.families(all=1)):
        call()
    assert len(fake_fc) == 2                         # je Liste ein fc-list-Aufruf


# --- alte Qt-Namen „Name [Hersteller]“ (aus QFontComboBox in Dateien/Einstellungen) --------
def test_canonical_strips_foundry_of_installed_family(monkeypatch):
    monkeypatch.setattr(fonts, "families",
                        lambda all=False: ["C059", "Nimbus Sans", "Foo [Bar]"] if all else ["C059"])
    assert fonts.canonical("C059 [UKWN]") == "C059"
    assert fonts.canonical("Nimbus Sans [urw]") == "Nimbus Sans"   # auch nicht in der kurzen Liste
    assert fonts.canonical("Foo [Bar]") == "Foo [Bar]"             # heißt wirklich so
    assert fonts.canonical("Fehlt [urw]") == "Fehlt [urw]"         # Name ohne Hersteller fehlt auch
    assert fonts.canonical("Sans Serif") == "Sans Serif"           # Qt-Sammelname bleibt fremd
    assert fonts.canonical(None) is None


@needs_fontconfig
def test_resolve_and_warnings_understand_qt_foundry_names():
    from labelwerk.document import Document, Paragraph, Span, TextObject
    from labelwerk.render import font_warnings
    fonts.resolve.cache_clear()
    assert fonts.resolve("DejaVu Serif [PfEd]", False, False).family == "DejaVu Serif"
    doc = Document(objects=[TextObject([Paragraph([Span("A", family="DejaVu Serif [PfEd]"),
                                                   Span("B", family="Sans Serif")])])])
    warnings = font_warnings(doc)
    assert len(warnings) == 1 and "Sans Serif" in warnings[0]       # nur der Sammelname
