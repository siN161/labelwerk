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
    fonts.families.cache_clear()
    try:
        assert fonts.families() == ["DejaVu Sans"]
        assert fonts.resolve(None, True, False).path.endswith("DejaVuSans-Bold.ttf")
    finally:
        fonts.resolve.cache_clear()
        fonts.families.cache_clear()


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
