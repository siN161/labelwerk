"""Etikett-Dokument: Etikett und Liste von Objekten (UI-unabhängig)."""
from __future__ import annotations

from dataclasses import dataclass, field

ORIENTATIONS = ("vertical", "horizontal")
MAX_MARGIN_MM = 20.0


@dataclass
class TextObject:
    text: str = ""
    font_size: int | None = None      # None = automatisch
    font_path: str | None = None

    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass
class Document:
    label_id: str = "62"
    length_mm: float | None = None    # nur Endlosband; None = automatisch
    orientation: str = "vertical"     # "vertical" (Text quer zum Band) | "horizontal" (längs)
    margin_mm: float = 1.0            # Rand in Bandlaufrichtung (vorne/hinten)
    objects: list[TextObject] = field(default_factory=list)

    def is_empty(self) -> bool:
        """True, wenn kein Objekt sichtbaren Inhalt hat."""
        return all(obj.is_empty() for obj in self.objects)
