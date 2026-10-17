"""Etikettentypen für Brother-QL-Drucker (Daten aus brother_ql)."""
from __future__ import annotations

from dataclasses import dataclass

from brother_ql.labels import Color, FormFactor, LabelsManager
from brother_ql.models import ModelsManager

# Maximale Bandbreite in mm je Modell (QL-5xx/6xx/7xx/8xx: 62 mm)
MAX_TAPE_MM = {"QL-600": 62}
TWO_COLOR_MODELS = {"QL-800", "QL-810W", "QL-820NWB"}

DPI = 300  # Druckauflösung der QL-Drucker


@dataclass(frozen=True)
class Label:
    id: str
    width: int              # druckbare Punkte quer zum Band (300 dpi)
    height: int | None      # None = Endlosband
    tape_mm: int
    description: str


def _convert(raw) -> Label:
    w, h = raw.dots_printable
    endless = raw.form_factor in (FormFactor.ENDLESS, FormFactor.PTOUCH_ENDLESS)
    if endless:
        desc = f"{raw.tape_size[0]} mm endlos"
    elif raw.form_factor == FormFactor.ROUND_DIE_CUT:
        desc = f"Ø {raw.tape_size[0]} mm rund"
    else:
        desc = f"{raw.tape_size[0]} x {raw.tape_size[1]} mm gestanzt"
    return Label(raw.identifier, w, None if endless else h, raw.tape_size[0], desc)


def _all_raw():
    return list(LabelsManager().iter_elements())


def get_label(label_id: str) -> Label:
    for raw in _all_raw():
        if raw.identifier == label_id:
            return _convert(raw)
    raise ValueError(f"Unbekanntes Etikett: {label_id!r}")


def labels_for_model(model: str) -> list[Label]:
    max_mm = MAX_TAPE_MM.get(model)
    result = []
    for raw in _all_raw():
        if raw.restricted_to_models and model not in raw.restricted_to_models:
            continue
        if max_mm is not None and raw.tape_size[0] > max_mm:
            continue
        if model.startswith("QL") and raw.form_factor == FormFactor.PTOUCH_ENDLESS:
            continue
        if raw.color == Color.BLACK_RED_WHITE and model not in TWO_COLOR_MODELS:
            continue
        result.append(_convert(raw))
    return result


def format_mm(dots: int) -> str:
    """Punkte (300 dpi) als mm-Angabe mit Dezimalkomma, z. B. "58,9"."""
    return f"{dots * 25.4 / DPI:.1f}".replace(".", ",")


def length_limits(model: str) -> tuple[int, int]:
    """Erlaubte Etikettlänge (Endlosband) in Punkten, z. B. (150, 11811) für den QL-600."""
    for m in ModelsManager().iter_elements():
        if m.identifier == model:
            return m.min_max_length_dots
    raise ValueError(f"Unbekanntes Druckermodell: {model!r}")
