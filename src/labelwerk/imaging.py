"""Bilder für den Druck aufbereiten (ohne Qt): auf Weiß legen, Größe begrenzen, in
Druckebenen umwandeln.

Druckebenen (``to_layers``) sind Bilder im Modus „1“ wie gedruckt: schwarz (0) = Tinte,
weiß (255) = Papier. Heute gibt es nur die Ebene ``"black"``. Für den Zweifarbdruck der
QL-8xx kommt später eine Ebene ``"red"`` hinzu – aus dem Farbbild (rote Töne → rot, der
Rest → schwarz); der Druck setzt dann beide Ebenen zusammen (brother_ql ``red=True``).
Deshalb bleibt das Original in Farbe, bis ``to_layers`` es umwandelt.
"""
from __future__ import annotations

from PIL import Image, ImageChops

MODES = ("line", "photo")      # Strich (harte Schwelle) | Foto (Rasterpunkte)
MAX_DPI = 600                  # feiner druckt der QL nicht (300 dpi) – mehr kostet nur Speicher
MAX_PIXELS = 6000              # längste Seite in Pixeln (Speicher; bei 300 dpi gut 50 cm)


_GRAY_16 = ("I", "I;16", "I;16B", "I;16L", "I;16N")   # Graustufen mit 16 Bit (PNG, TIFF)


def to_8bit(img: Image.Image) -> Image.Image:
    """Graustufen mit 16 Bit auf 8 Bit skalieren (0–65535 → 0–255); Pillow würde beim
    Umwandeln abschneiden – das Bild käme fast weiß an. Andere Bilder unverändert."""
    if img.mode in _GRAY_16:
        return img.convert("I").point(lambda v: v / 257).convert("L")
    return img


def on_white(img: Image.Image) -> Image.Image:
    """Bild als RGB; Transparenz (Alphakanal, transparente Palettenfarbe) wird weiß."""
    img = to_8bit(img)
    if img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        return Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba).convert("RGB")
    if img.mode == "F":                       # Fließkomma-Graustufen
        img = img.convert("L")
    return img.convert("RGB")


def limit_size(img: Image.Image, dpi: float,
               stretch: float = 1.0) -> tuple[Image.Image, float]:
    """Sehr große Bilder verkleinern: höchstens ``MAX_DPI`` bezogen auf die Druckgröße und
    höchstens ``MAX_PIXELS`` auf der längsten Seite. Die Druckgröße bleibt (die Auflösung
    sinkt mit); ein Bild in Grenzen kommt unverändert zurück. ``stretch``: Faktor für die
    Höhe (ungleiche Auflösung) – gerechnet wird mit der gestreckten Größe, in einem
    Schritt vom Original aus (kein Hochskalieren vorab); auch bei ``factor`` 1 wird dann
    gestreckt."""
    height = max(1, round(img.height * stretch))
    factor = min(1.0, MAX_DPI / dpi, MAX_PIXELS / max(img.width, height))
    if factor >= 1.0 and height == img.height:
        return img, dpi
    size = (max(1, round(img.width * factor)), max(1, round(height * factor)))
    return img.resize(size, Image.Resampling.LANCZOS, reducing_gap=3.0), dpi * factor


def check(mode: str, threshold: int) -> None:
    """Umwandlung und Schwelle prüfen; ``ValueError`` mit verständlicher Meldung."""
    if mode not in MODES:
        raise ValueError(f"Unbekannte Umwandlung {mode!r} – erlaubt: Strich, Foto (line, photo)")
    if isinstance(threshold, bool) or not isinstance(threshold, int) or not 0 <= threshold <= 255:
        raise ValueError(f"Schwelle muss eine ganze Zahl von 0 bis 255 sein, nicht {threshold!r}.")


def photo_curve(threshold: int) -> list[int]:
    """Helligkeitskurve für ``"photo"`` (Tabelle 0–255): ``v' = 255 · (v / 255) ** g`` mit
    ``g = 2 ** ((threshold − 128) / 64)`` – höhere Schwelle → dunkler, 128 = unverändert;
    0 und 255 bleiben fest (Papier bleibt weiß, Schwarz bleibt voll)."""
    gamma = 2 ** ((threshold - 128) / 64)
    return [round(255 * (v / 255) ** gamma) for v in range(256)]


def to_layers(img: Image.Image, mode: str, threshold: int,
              invert: bool) -> dict[str, Image.Image]:
    """Bild in Druckebenen umwandeln (siehe Modulbeschreibung), gleiche Größe wie ``img``.

    ``"line"``: Graustufe, dunkler als ``threshold`` wird Tinte (harte Schwelle – Codes,
    Schrift, Logos). ``"photo"``: Gammakurve (``photo_curve``: 128 = unverändert, Weiß und
    Schwarz bleiben), dann Floyd-Steinberg-Rasterung (Fotos, Verläufe) – weißes Papier
    bekommt nie Punkte. Beide Male gilt: höhere Schwelle → mehr Tinte. ``invert`` tauscht
    zuletzt Tinte und Papier.
    """
    check(mode, threshold)
    gray = img.convert("L")
    if mode == "line":
        black = gray.point([0 if v < threshold else 255 for v in range(256)])
        black = black.convert("1", dither=Image.Dither.NONE)
    else:
        if threshold != 128:
            gray = gray.point(photo_curve(threshold))
        black = gray.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    if invert:
        black = ImageChops.invert(black)
    return {"black": black}
