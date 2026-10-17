"""Inkrementeller Renderer (``render.Renderer``): nur Geändertes neu, Druckbild = render_document."""
import copy
import random

import pytest

from labelwerk import render
from labelwerk.document import Document, Paragraph, Span, TextObject
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
