"""Etikettentypen für Brother-QL-Drucker (Daten aus brother_ql)."""
from __future__ import annotations

from dataclasses import dataclass

from brother_ql.labels import Color, FormFactor, LabelsManager

from .printers import capabilities

DPI = 300  # Druckauflösung der QL-Drucker


@dataclass(frozen=True)
class Label:
    id: str
    width: int              # druckbare Punkte quer zum Band (300 dpi)
    height: int | None      # None = Endlosband
    tape_mm: int
    description: str
    shape: str              # "endless", "die_cut" oder "round"
    size_mm: tuple[int, int]  # Nenngröße laut Etikett, z. B. (62, 29); Endlos: (62, 0)
    total_width: int        # physische Breite in Punkten (bedruckbarer Bereich liegt mittig)
    total_height: int | None  # physische Höhe in Punkten; None = Endlosband
    two_color: bool = False   # Rot/Schwarz (DK-22251, „62red“)


def _convert(raw) -> Label:
    w, h = raw.dots_printable
    endless = raw.form_factor in (FormFactor.ENDLESS, FormFactor.PTOUCH_ENDLESS)
    if endless:
        desc, shape = f"{raw.tape_size[0]} mm endlos", "endless"
    elif raw.form_factor == FormFactor.ROUND_DIE_CUT:
        desc, shape = f"Ø {raw.tape_size[0]} mm rund", "round"
    else:
        desc, shape = f"{raw.tape_size[0]} x {raw.tape_size[1]} mm gestanzt", "die_cut"
    total_w, total_h = raw.dots_total
    return Label(raw.identifier, w, None if endless else h, raw.tape_size[0], desc,
                 shape, tuple(raw.tape_size), total_w, None if endless else total_h,
                 raw.color == Color.BLACK_RED_WHITE)


def _all_raw():
    return list(LabelsManager().iter_elements())


def get_label(label_id: str) -> Label:
    for raw in _all_raw():
        if raw.identifier == label_id:
            return _convert(raw)
    raise ValueError(f"Unbekanntes Etikett: {label_id!r}")


def labels_for_model(model: str) -> list[Label]:
    """Etiketten, die ``model`` drucken kann (``printers.capabilities``): bis zu seiner Breite,
    ohne P-touch-Bänder, Rot/Schwarz nur bei Zweifarb-Modellen; unbekanntes Modell → ValueError."""
    caps = capabilities(model)
    result = []
    for raw in _all_raw():
        if raw.restricted_to_models and model not in raw.restricted_to_models:
            continue
        if raw.tape_size[0] > caps.max_tape_mm or raw.form_factor == FormFactor.PTOUCH_ENDLESS:
            continue
        if raw.color == Color.BLACK_RED_WHITE and not caps.two_color:
            continue
        result.append(_convert(raw))
    return result


def format_mm(dots: int) -> str:
    """Punkte (300 dpi) als mm-Angabe mit Dezimalkomma, z. B. "58,9"."""
    return f"{dots * 25.4 / DPI:.1f}".replace(".", ",")


def length_limits(model: str) -> tuple[int, int]:
    """Erlaubte Etikettlänge (Endlosband) in Punkten, z. B. (150, 11811) für den QL-600."""
    return capabilities(model).length_limits
