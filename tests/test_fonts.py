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
