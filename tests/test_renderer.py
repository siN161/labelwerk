"""Inkrementeller Renderer (``render.Renderer``): nur Geändertes neu, Druckbild = render_document."""
import copy
import random

import pytest

from labelwerk import render
from labelwerk.document import Document, ImageObject, Paragraph, Span, TextObject
from labelwerk.render import Rendered, Renderer, label_size, render_document, render_object


def _doc(**kw) -> Document:
    return Document("62", length_mm=40, objects=[
        TextObject("Eins", size_pt=12, x_mm=3, y_mm=4),
        TextObject("Zwei", size_pt=14, x_mm=6, y_mm=20)], **kw)


@pytest.fixture
def calls(monkeypatch):
    """Zählt das Messen (``_prepare``) und Zeichnen (``_finish``) je Objekttext."""
    seen = []
    for name in ("_prepare", "_finish"):
        real = getattr(render, name)

        def counting(item, *args, _real=real, _name=name, **kwargs):
            seen.append((_name, getattr(item, "obj", item).text))
            return _real(item, *args, **kwargs)
        monkeypatch.setattr(render, name, counting)
    return seen


def test_render_gives_size_objects_and_print_image():
    doc = _doc()
    result = Renderer().render(doc, "QL-600")
    assert isinstance(result, Rendered)
    assert result.size == label_size(doc)
    assert result.objects == [render_object(obj, doc) for obj in doc.objects]
    assert result.image.tobytes() == render_document(doc).tobytes()


def test_unchanged_document_renders_nothing_and_keeps_image(calls):
    renderer, doc = Renderer(), _doc()
    first = renderer.render(doc, "QL-600")
    calls.clear()
    second = renderer.render(doc, "QL-600")
    assert calls == []
    assert second.image is first.image
    assert all(a is b for a, b in zip(second.objects, first.objects))


def test_only_changed_object_is_rendered_again(calls):
    renderer, doc = Renderer(), _doc()
    renderer.render(doc, "QL-600")
    calls.clear()
    doc.objects[1].x_mm = 10                       # in place geändert: Schnappschuss erkennt es
    result = renderer.render(doc, "QL-600")
    assert calls == [("_prepare", "Zwei"), ("_finish", "Zwei")]
    assert result.image.tobytes() == render_document(doc).tobytes()


def test_replaced_object_is_rendered_again(calls):
    renderer, doc = Renderer(), _doc()
    renderer.render(doc, "QL-600")
    calls.clear()
    doc.objects[0] = TextObject("Neu", size_pt=12, x_mm=3, y_mm=4)
    renderer.render(doc, "QL-600")
    assert calls == [("_prepare", "Neu"), ("_finish", "Neu")]


def test_object_replaced_by_equal_copy_is_rendered_again(calls):
    """Gleicher Inhalt, aber ein anderes Objekt: neu messen (der Cache hält das alte fest)."""
    renderer, doc = Renderer(), _doc()
    renderer.render(doc, "QL-600")
    calls.clear()
    doc.objects[0] = copy.deepcopy(doc.objects[0])
    result = renderer.render(doc, "QL-600")
    assert calls == [("_prepare", "Eins"), ("_finish", "Eins")]
    assert result.image.tobytes() == render_document(doc).tobytes()


def test_same_object_twice_in_list_renders_twice():
    doc = _doc()
    doc.objects.append(doc.objects[0])
    renderer = Renderer()
    result = renderer.render(doc, "QL-600")
    assert len(result.objects) == 3 and result.objects[2] == result.objects[0]
    assert result.image.tobytes() == render_document(doc).tobytes()
    doc.objects[0].x_mm = 12                       # beide Einträge ändern sich mit
    result = renderer.render(doc, "QL-600")
    assert result.objects[2] == result.objects[0]
    assert result.image.tobytes() == render_document(doc).tobytes()


def test_context_change_renders_everything_again(calls):
    renderer, doc = Renderer(), _doc()
    renderer.render(doc, "QL-600")
    calls.clear()
    doc.margin_mm = 4
    result = renderer.render(doc, "QL-600")
    assert sorted(calls) == [("_finish", "Eins"), ("_finish", "Zwei"),
                             ("_prepare", "Eins"), ("_prepare", "Zwei")]
    assert result.image.tobytes() == render_document(doc).tobytes()


def test_growing_label_redraws_unpositioned_objects_without_measuring_again(calls):
    renderer = Renderer()
    doc = _doc()
    doc.length_mm = None                           # automatische Länge: wächst mit
    doc.objects.append(TextObject("Mitte"))        # ohne Position: hängt an der Etikettgröße
    before = renderer.render(doc, "QL-600")
    calls.clear()
    doc.objects[1].y_mm = 80
    result = renderer.render(doc, "QL-600")
    assert result.size != before.size
    assert sorted(calls) == [("_finish", "Mitte"), ("_finish", "Zwei"), ("_prepare", "Zwei")]
    assert result.image.tobytes() == render_document(doc).tobytes()


def test_failed_render_keeps_cache(calls):
    renderer, doc = Renderer(), _doc()
    renderer.render(doc, "QL-600")
    doc.objects.append(TextObject("Viel zu groß", size_pt=200))   # ohne Position: zu groß
    with pytest.raises(ValueError):
        renderer.render(doc, "QL-600")
    del doc.objects[-1]
    calls.clear()
    renderer.render(doc, "QL-600")
    assert calls == []


def test_empty_document_is_byte_identical():
    for doc in (Document("62"), Document("62", objects=[TextObject("")]),
                Document("29", orientation="horizontal")):
        result = Renderer().render(doc, "QL-600")
        assert result.image.tobytes() == render_document(doc).tobytes()


def test_random_documents_are_byte_identical_also_incrementally():
    rng = random.Random(7)
    renderer = Renderer()
    doc = Document("62")
    for _ in range(60):
        doc.label_id = rng.choice([doc.label_id] * 4 + ["62", "29", "62x29"])
        doc.orientation = rng.choice([doc.orientation] * 4 + ["vertical", "horizontal"])
        doc.length_mm = rng.choice([doc.length_mm] * 4 + [None, 50])
        action = rng.random()
        if action < 0.4 or not doc.objects:
            text = "".join(rng.choice("JjfgQyAa W_") for _ in range(rng.randint(1, 8)))
            positioned = rng.random() < 0.7
            doc.objects.append(TextObject(
                [Paragraph([Span(text, bold=rng.random() < 0.5)],
                           rng.choice(["left", "center", "right"]))],
                size_pt=rng.choice([8, 10, 14]),
                x_mm=rng.uniform(0, 30) if positioned else None,
                y_mm=rng.uniform(0, 20) if positioned else None,
                rotation=rng.choice([0, 0, 90, 180, 270])))
        elif action < 0.7:
            obj = rng.choice(doc.objects)
            if obj.positioned:
                obj.x_mm = rng.uniform(0, 30)
        elif action < 0.85:
            del doc.objects[rng.randrange(len(doc.objects))]
        else:
            rng.shuffle(doc.objects)
        try:
            expected = render_document(doc)
        except ValueError:
            with pytest.raises(ValueError):
                renderer.render(doc, "QL-600")
            continue
        result = renderer.render(doc, "QL-600")
        assert result.image.size == expected.size
        assert result.image.tobytes() == expected.tobytes()


# --- Bilder -------------------------------------------------------------------------
def _with_images() -> Document:
    from PIL import Image
    doc = _doc()
    for x in (20, 40):
        img = Image.new("RGB", (200, 100), (120, 120, 120))
        doc.objects.append(ImageObject.from_image(img, 300, "grau.png"))
        doc.objects[-1].x_mm, doc.objects[-1].y_mm = x, 25
    return doc


@pytest.fixture
def finished(monkeypatch):
    """Zählt das Zeichnen (``_finish``) je Objekt (Index in ``_with_images``)."""
    seen = []
    real = render._finish

    def counting(prep, *args, **kwargs):
        seen.append(prep.obj)
        return real(prep, *args, **kwargs)
    monkeypatch.setattr(render, "_finish", counting)
    return seen


def test_changing_threshold_redraws_only_that_image(finished):
    renderer, doc = Renderer(), _with_images()
    renderer.render(doc, "QL-600")
    finished.clear()
    doc.objects[3].threshold = 100
    result = renderer.render(doc, "QL-600")
    assert finished == [doc.objects[3]]
    assert result.image.tobytes() == render_document(doc).tobytes()


@pytest.mark.parametrize("change", [
    {"mode": "photo"}, {"invert": True}, {"keep_ratio": False}, {"rotation": 90},
    {"crop": (0, 0, 50, 50)}, {"w_mm": 5.0}, {"x_mm": 1.0}, {"page": 2}, {"source": "neu.png"}])
def test_every_image_setting_is_part_of_the_cache_key(finished, change):
    renderer, doc = Renderer(), _with_images()
    renderer.render(doc, "QL-600")
    finished.clear()
    for key, value in change.items():
        setattr(doc.objects[2], key, value)
    renderer.render(doc, "QL-600")
    assert finished == [doc.objects[2]]


def test_new_png_bytes_redraw_the_image(finished):
    from PIL import Image
    renderer, doc = Renderer(), _with_images()
    renderer.render(doc, "QL-600")
    finished.clear()
    doc.objects[2].png = ImageObject.from_image(Image.new("RGB", (200, 100)), 300, "x").png
    result = renderer.render(doc, "QL-600")
    assert finished == [doc.objects[2]]
    assert result.image.tobytes() == render_document(doc).tobytes()


def test_unchanged_images_render_nothing(finished):
    renderer, doc = Renderer(), _with_images()
    first = renderer.render(doc, "QL-600")
    finished.clear()
    assert renderer.render(doc, "QL-600").image is first.image
    assert finished == []


def test_threshold_change_does_not_decode_or_scale_again():
    render._scaled_source.cache_clear()
    doc = _with_images()
    renderer = Renderer()
    renderer.render(doc, "QL-600")
    misses = render._scaled_source.cache_info().misses
    doc.objects[2].threshold = 90
    renderer.render(doc, "QL-600")
    assert render._scaled_source.cache_info().misses == misses


def test_random_changes_with_images_stay_byte_identical():
    from PIL import Image
    rng = random.Random(11)
    source = Image.radial_gradient("L").convert("RGB").resize((120, 80))
    renderer = Renderer()
    doc = Document("62", length_mm=None)
    for _ in range(40):
        doc.orientation = rng.choice([doc.orientation] * 4 + ["vertical", "horizontal"])
        action = rng.random()
        if action < 0.3 or not doc.objects:
            if rng.random() < 0.5:
                obj = ImageObject.from_image(source, rng.choice([150, 300, 600]), "verlauf.png")
                obj.x_mm, obj.y_mm = rng.uniform(0, 30), rng.uniform(0, 30)
            else:
                obj = TextObject("Ab", size_pt=10, x_mm=rng.uniform(0, 30), y_mm=5)
            doc.objects.append(obj)
        elif action < 0.8:
            obj = rng.choice(doc.objects)
            if isinstance(obj, ImageObject):
                setattr(obj, *rng.choice([
                    ("threshold", rng.randint(0, 255)), ("mode", rng.choice(["line", "photo"])),
                    ("invert", rng.random() < 0.5), ("rotation", rng.choice([0, 90, 180, 270])),
                    ("keep_ratio", rng.random() < 0.5), ("w_mm", rng.uniform(3, 20)),
                    ("crop", rng.choice([None, (10, 10, 60, 40)]))]))
            else:
                obj.x_mm = rng.uniform(0, 30)
        else:
            del doc.objects[rng.randrange(len(doc.objects))]
        assert renderer.render(doc, "QL-600").image.tobytes() == render_document(doc).tobytes()
