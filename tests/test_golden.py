"""Referenztests je Druckermodell: Die Rasterdaten eines festen Testetiketts ändern sich nur
gewollt (dann ``python tools/golden.py --update``). Beweist, was gesendet wird – nicht, was
gedruckt wird."""
import importlib.util
import json
from pathlib import Path

import pytest

from labelwerk.printers import SUPPORTED_MODELS

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("golden", ROOT / "tools" / "golden.py")
golden = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(golden)
STORED = json.loads((ROOT / "tests" / "golden" / "raster.json").read_text())


def test_every_supported_model_has_references():
    assert sorted(STORED) == sorted(golden.MODELS)
    assert set(SUPPORTED_MODELS) < set(golden.MODELS) and "zpl:203" in STORED


@pytest.mark.parametrize("model", golden.MODELS)
def test_raster_data_is_unchanged(model):
    current = {name: golden.hashlib.sha256(data).hexdigest()
               for name, data in golden.cases(model).items()}
    assert current == STORED[model]


def test_cases_cover_cut_width_and_red():
    assert "62-ohne-schnitt" in STORED["QL-600"] and "102" not in STORED["QL-600"]
    assert "102" in STORED["QL-1100"] and "62red" in STORED["QL-820NWB"]
    # ohne Abschneider: mit und ohne Schnitt gleich
    assert STORED["QL-500"]["62"] == STORED["QL-500"]["62-ohne-schnitt"]
    assert STORED["QL-600"]["62"] != STORED["QL-600"]["62-ohne-schnitt"]
