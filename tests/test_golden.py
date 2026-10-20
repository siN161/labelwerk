"""Reference tests per printer model: the raster data of a fixed test label only change
on purpose (then ``python tools/golden.py --update``). Proves what is sent – not what
is printed."""
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
    # without cutter: same with and without cut
    assert STORED["QL-500"]["62"] == STORED["QL-500"]["62-ohne-schnitt"]
    assert STORED["QL-600"]["62"] != STORED["QL-600"]["62-ohne-schnitt"]
