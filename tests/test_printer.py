from labelwerk.render import render_text
from labelwerk.printer import build_instructions


def test_build_instructions_produces_brother_raster_data():
    data = build_instructions(render_text("Test", "62"), "62", model="QL-600")
    assert isinstance(data, bytes)
    assert b"\x1b@" in data          # ESC @ = Initialisieren
    assert data.endswith(b"\x1a")    # Drucken mit Vorschub
