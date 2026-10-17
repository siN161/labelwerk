"""Etikett-Dokument: Etikett und Liste von Objekten (UI-unabhängig, JSON-tauglich)."""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image

from .imaging import limit_size, on_white

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
    x_mm: float | None = None       # linke obere Ecke; beide None = mittig auf dem Etikett,
    y_mm: float | None = None       # nur eine gesetzt: die andere zählt als 0
    w_mm: float | None = None       # Rahmengröße nur bei fit; None = bedruckbarer Bereich
                                    # (Endlosband, automatische Länge: längs = Textlänge)
    h_mm: float | None = None
    rotation: int = 0               # 0 | 90 | 180 | 270

    @property
    def positioned(self) -> bool:
        """Frei platziert, sobald ``x_mm`` oder ``y_mm`` gesetzt ist (sonst mittig wie bisher)."""
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


@dataclass(kw_only=True)
class ImageObject:
    """Bild auf dem Etikett; Schwarz/Weiß erst beim Rendern (``imaging.to_layers``).

    Anlegen meist mit ``ImageObject.from_image``. Der Rahmen ist immer gesetzt – wie bei
    Text mit fester Rahmengröße: ``x_mm``/``y_mm`` linke obere Ecke auf dem Etikett (nach
    dem Drehen), ``w_mm``/``h_mm`` Größe vor dem Drehen.
    """
    png: bytes = field(repr=False)  # Original in Farbe (auf Weiß), verlustfrei als PNG
    source: str = ""                # Dateiname oder „Zwischenablage“
    page: int | None = None         # PDF-Seite
    crop: tuple[int, int, int, int] | None = None   # Ausschnitt (l, t, r, b) in Pixeln; None = ganz
    x_mm: float = 0.0
    y_mm: float = 0.0
    w_mm: float
    h_mm: float
    rotation: int = 0               # 0 | 90 | 180 | 270
    mode: str = "line"              # line (Strich, harte Schwelle) | photo (Foto, gerastert)
    threshold: int = 128            # 0–255; höher = mehr Tinte
    invert: bool = False
    keep_ratio: bool = True         # Seitenverhältnis beibehalten (Ecken/Kanten skalieren gleich)

    def __post_init__(self) -> None:
        if self.crop is not None:                # JSON liefert eine Liste
            self.crop = tuple(int(v) for v in self.crop)

    @property
    def positioned(self) -> bool:
        """Ein Bild hat immer eine Position (anders als Text, der mittig stehen kann)."""
        return True

    def is_empty(self) -> bool:
        return False

    @classmethod
    def from_image(cls, img: Image.Image, dpi: float, source: str, page: int | None = None,
                   crop: tuple[int, int, int, int] | None = None) -> "ImageObject":
        """Bild 1:1 nach ``dpi`` (Größe des Ausschnitts ``crop``, sonst des ganzen Bilds).

        Transparenz wird weiß; sehr große Bilder werden begrenzt (``imaging.limit_size``) –
        der Ausschnitt rechnet mit, die Druckgröße bleibt.
        """
        l, t, r, b = crop if crop is not None else (0, 0, *img.size)
        mm = 25.4 / dpi                          # Druckgröße aus dem Original
        rgb, _ = limit_size(on_white(img), dpi)
        if crop is not None and rgb.size != img.size:
            fx, fy = rgb.width / img.width, rgb.height / img.height
            crop = (round(l * fx), round(t * fy), round(r * fx), round(b * fy))
        buffer = io.BytesIO()
        rgb.save(buffer, "PNG", compress_level=1)   # große Fotos rund 4× schneller
        return cls(png=buffer.getvalue(), source=source, page=page, crop=crop,
                   w_mm=(r - l) * mm, h_mm=(b - t) * mm)

    def image(self) -> Image.Image:
        """Das Original als RGB-Bild."""
        with Image.open(io.BytesIO(self.png)) as img:
            return img.convert("RGB")


@dataclass
class Document:
    label_id: str = "62"
    length_mm: float | None = None    # nur Endlosband; None = automatisch
    orientation: str = "vertical"     # "vertical" (Text quer zum Band) | "horizontal" (längs)
    margin_mm: float = 1.0            # Rand in Bandlaufrichtung (vorne/hinten)
    objects: list[TextObject | ImageObject] = field(default_factory=list)

    def is_empty(self) -> bool:
        """True, wenn kein Objekt sichtbaren Inhalt hat."""
        return all(obj.is_empty() for obj in self.objects)
