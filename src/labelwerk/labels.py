"""Etikettentypen: Brother-QL (Daten aus brother_ql, 300 dpi) und Etiketten anderer Drucker als
IDs mit Größe und Auflösung („54x25mm@300“ – ohne angeschlossenen Drucker lesbar)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from brother_ql.labels import Color, FormFactor, LabelsManager

from .printers import capabilities

DPI = 300  # Druckauflösung der QL-Drucker
DPI_RANGE = (100, 600)       # Auflösungen anderer Drucker
SIZE_MM = (5.0, 300.0)       # Kanten fester Etiketten anderer Drucker
_SIZED = re.compile(r"(\d{1,3}(?:\.\d)?)x(\d{1,3}(?:\.\d)?)mm@(\d{2,3})")


@dataclass(frozen=True)
class Label:
    id: str
    width: int              # druckbare Punkte quer zum Band (bei ``dpi``)
    height: int | None      # None = Endlosband
    tape_mm: int
    description: str
    shape: str              # "endless", "die_cut" oder "round"
    size_mm: tuple[int, int]  # Nenngröße laut Etikett, z. B. (62, 29); Endlos: (62, 0)
    total_width: int        # physische Breite in Punkten (bedruckbarer Bereich liegt mittig)
    total_height: int | None  # physische Höhe in Punkten; None = Endlosband
    two_color: bool = False   # Rot/Schwarz (DK-22251, „62red“)
    dpi: int = DPI            # Druckauflösung (Brother 300; andere aus der ID)


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


def sized_id(w_mm: float, h_mm: float, dpi: int) -> str:
    """ID eines festen Etiketts anderer Drucker: „54x25mm@300“ (mm auf 0,1)."""
    return f"{_mm(w_mm)}x{_mm(h_mm)}mm@{round(dpi)}"


def _mm(value: float) -> str:
    return f"{round(value, 1):g}"


def mm_text(value: float) -> str:
    """Maß in mm zum Anzeigen: „62“, „101,6“."""
    return _mm(value).replace(".", ",")


def sized_label(label_id: str) -> Label | None:
    """Etikett zu einer ID „BxHmm@dpi“ (fest, ganz bedruckbar), sonst None."""
    m = _SIZED.fullmatch(label_id) if isinstance(label_id, str) else None
    if m is None:
        return None
    w, h, dpi = float(m[1]), float(m[2]), int(m[3])
    if not (SIZE_MM[0] <= w <= SIZE_MM[1] and SIZE_MM[0] <= h <= SIZE_MM[1]
            and DPI_RANGE[0] <= dpi <= DPI_RANGE[1]) or label_id != sized_id(w, h, dpi):
        return None                          # auch „057x32mm@203“: nur eine Schreibweise je Etikett
    width, height = round(w * dpi / 25.4), round(h * dpi / 25.4)
    text = f"{mm_text(w)} × {mm_text(h)} mm · {dpi} dpi"
    return Label(label_id, width, height, round(w), text, "die_cut", (w, h), width, height,
                 False, dpi)


def get_label(label_id: str) -> Label:
    if (sized := sized_label(label_id)) is not None:
        return sized
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


def format_mm(dots: int, dpi: int = DPI) -> str:
    """Druckpunkte als mm-Angabe mit Dezimalkomma, z. B. "58,9"."""
    return f"{dots * 25.4 / dpi:.1f}".replace(".", ",")


def length_limits(model: str) -> tuple[int, int]:
    """Erlaubte Etikettlänge (Endlosband) in Punkten, z. B. (150, 11811) für den QL-600 – bei
    300 dpi: Endlosband gibt es nur bei Brother (andere Drucker haben feste Etiketten)."""
    return capabilities(model).length_limits
