"""Etikett-Dokument: Etikett und Liste von Objekten (UI-unabhängig, JSON-tauglich)."""
from __future__ import annotations

from dataclasses import dataclass, field

ORIENTATIONS = ("vertical", "horizontal")
ALIGNMENTS = ("left", "center", "right", "justify")
ROTATIONS = (0, 90, 180, 270)      # Grad im Uhrzeigersinn
MAX_MARGIN_MM = 20.0
MIN_PT, MAX_PT = 4.0, 100.0


@dataclass
class Span:
    """Gleich formatiertes Textstück."""
    text: str
    family: str | None = None       # None = Standardschrift (DejaVu Sans)
    size_pt: float | None = None    # None = Grundgröße des Textobjekts
    bold: bool = True               # heutiges Aussehen bleibt Standard
    italic: bool = False
    underline: bool = False


@dataclass
class Paragraph:
    """Eine Zeile (Absatz) aus Textstücken."""
    spans: list[Span] = field(default_factory=list)
    align: str = "center"           # left | center | right | justify

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)


@dataclass
class TextObject:
    """Formatierter Text. ``TextObject("Zeile 1\\nZeile 2")`` legt reinen Text an."""
    paragraphs: list[Paragraph] | str = field(default_factory=list)
    size_pt: float | None = None    # Grundgröße; None = automatisch
    font_path: str | None = None    # feste TTF-Datei für Stücke ohne Familie (CLI --font)
    fit: bool = False               # „Feste Rahmengröße“: Grundgröße + Verhältnisse, gemeinsam skaliert
    # Rahmen in mm in Leserichtung, Ursprung = linke obere Ecke des Etiketts
    x_mm: float | None = None       # linke obere Ecke; None = mittig auf dem Etikett
    y_mm: float | None = None
    w_mm: float | None = None       # Rahmengröße nur bei fit; None = bedruckbarer Bereich
    h_mm: float | None = None
    rotation: int = 0               # 0 | 90 | 180 | 270

    @property
    def positioned(self) -> bool:
        """Frei platziert (sonst mittig auf dem Etikett wie bisher)."""
        return self.x_mm is not None or self.y_mm is not None

    @property
    def auto(self) -> bool:
        """Größe wird automatisch angepasst (keine feste Grundgröße oder feste Rahmengröße)."""
        return self.size_pt is None or self.fit

    def __post_init__(self) -> None:
        if isinstance(self.paragraphs, str):
            self.paragraphs = [Paragraph([Span(line)]) for line in self.paragraphs.split("\n")]

    @classmethod
    def plain(cls, text: str, size_pt: float | None = None, align: str = "center",
              family: str | None = None, bold: bool = True, italic: bool = False,
              underline: bool = False, font_path: str | None = None) -> "TextObject":
        """Reiner Text mit einheitlicher Formatierung für alle Zeilen."""
        paragraphs = [Paragraph([Span(line, family, None, bold, italic, underline)], align)
                      for line in text.split("\n")]
        return cls(paragraphs, size_pt=size_pt, font_path=font_path)

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.paragraphs)

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
