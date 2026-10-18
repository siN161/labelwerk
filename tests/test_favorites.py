"""Favoriten (Etappe 3c): gespeicherte Etiketten im Favoriten-Ordner."""
import pytest

from labelwerk import favorites
from labelwerk.document import Document, TextObject
from labelwerk.storage import load


def _doc(text="Absender"):
    return Document("62", objects=[TextObject(text)])


def test_folder_follows_xdg_data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert favorites.favorites_dir() == tmp_path / "labelwerk" / "favoriten"


def test_no_folder_no_favorites():
    assert favorites.favorites() == []


def test_add_and_list_sorted_without_case():
    favorites.add(_doc("Z"), "zebra")
    favorites.add(_doc("A"), "Absender")
    favorites.add(_doc("R"), "regal")
    assert [f.name for f in favorites.favorites()] == ["Absender", "regal", "zebra"]
    assert load(favorites.find("Absender").path).objects[0].text == "A"


def test_add_existing_name_needs_overwrite():
    favorites.add(_doc("alt"), "Absender")
    with pytest.raises(FileExistsError):
        favorites.add(_doc("neu"), "Absender")
    favorites.add(_doc("neu"), "Absender", overwrite=True)
    assert load(favorites.find("Absender").path).objects[0].text == "neu"


@pytest.mark.parametrize("name", ["", "   ", "a/b", ".versteckt", "a\\b", "x" * 201])
def test_invalid_names(name):
    with pytest.raises(ValueError, match="Name"):
        favorites.add(_doc(), name)


def test_name_is_trimmed():
    favorite = favorites.add(_doc(), "  Regal 3  ")
    assert favorite.name == "Regal 3" and favorite.path.name == "Regal 3.labelwerk"


def test_rename_and_remove():
    favorite = favorites.add(_doc(), "alt")
    renamed = favorites.rename(favorite, "neu")
    assert [f.name for f in favorites.favorites()] == ["neu"] and renamed.name == "neu"
    favorites.add(_doc(), "anderer")
    with pytest.raises(FileExistsError):
        favorites.rename(renamed, "anderer")
    favorites.remove(renamed)
    assert [f.name for f in favorites.favorites()] == ["anderer"]


def test_other_files_and_hidden_files_are_not_favorites():
    folder = favorites.favorites_dir()
    folder.mkdir(parents=True)
    (folder / "notiz.txt").write_text("x")
    (folder / ".versteckt.labelwerk").write_text("{}")
    favorites.add(_doc(), "echt")
    assert [f.name for f in favorites.favorites()] == ["echt"]


def test_find_unknown_is_none():
    assert favorites.find("gibt es nicht") is None


@pytest.mark.parametrize("name", ["a\nb", "a\x07b", "😀" * 60])
def test_control_characters_and_too_long_names_in_bytes(name):
    with pytest.raises(ValueError, match="Name"):
        favorites.add(_doc(), name)


def test_names_are_normalized_nfc():
    favorites.add(_doc(), "Café")
    assert [f.name for f in favorites.favorites()] == ["Café"]
    with pytest.raises(FileExistsError):
        favorites.add(_doc(), "Café")


def test_sorting_is_stable_for_case_variants():
    favorites.add(_doc(), "absender")
    favorites.add(_doc(), "Absender")
    assert [f.name for f in favorites.favorites()] == ["Absender", "absender"]


def test_rename_missing_favorite_gives_german_message():
    favorite = favorites.add(_doc(), "weg")
    favorites.remove(favorite)
    with pytest.raises(OSError, match="nicht gefunden"):
        favorites.rename(favorite, "neu")
