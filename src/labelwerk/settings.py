"""Einstellungen für GUI und CLI in $XDG_CONFIG_HOME/labelwerk/settings.json.

Fehlende oder ungültige Werte fallen auf den Standard zurück – mit Hinweis in
`Settings.warnings`, nie mit Ausnahme. Neue Einstellung = neues Feld + Prüfregel.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .document import MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
from .labels import labels_for_model


@dataclass
class Settings:
    label_id: str = "62"
    orientation: str = "vertical"
    margin_mm: float = 1.0
    font_size_pt: float | None = None      # None = automatisch
    check_media_on_start: bool = True
    start_zoom: int = 200
    warnings: list[str] = field(default_factory=list, compare=False, repr=False)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _rules(model: str) -> dict:
    known = {lab.id for lab in labels_for_model(model)}
    return {
        "label_id": lambda v: isinstance(v, str) and v in known,
        "orientation": lambda v: v in ORIENTATIONS,
        "margin_mm": lambda v: (_is_int(v) or isinstance(v, float)) and 0 <= v <= MAX_MARGIN_MM,
        "font_size_pt": lambda v: v is None or ((_is_int(v) or isinstance(v, float))
                                                and MIN_PT <= v <= MAX_PT),
        "check_media_on_start": lambda v: isinstance(v, bool),
        "start_zoom": lambda v: _is_int(v) and 25 <= v <= 400,
    }


_KEYS = tuple(_rules("QL-600"))


def settings_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "labelwerk" / "settings.json"


def load_settings(path: str | Path | None = None, model: str = "QL-600") -> Settings:
    path = Path(path) if path else settings_path()
    settings = Settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("kein JSON-Objekt")
    except FileNotFoundError:
        return settings
    except (OSError, ValueError) as e:
        settings.warnings.append(f"Einstellungen nicht lesbar ({path}): {e} – Standardwerte aktiv.")
        return settings
    _migrate_font_size(raw, settings)
    for key, valid in _rules(model).items():
        if key not in raw:
            continue
        value = raw[key]
        if valid(value):
            setattr(settings, key, float(value) if key == "margin_mm" else value)
        else:
            settings.warnings.append(f"Einstellung {key!r} ungültig ({value!r}) – "
                                     f"Standardwert {getattr(settings, key)!r} aktiv.")
    return settings


def _migrate_font_size(raw: dict, settings: Settings) -> None:
    """Alte Einstellung ``font_size`` (Druckpunkte bei 300 dpi) einmalig in pt umrechnen."""
    if "font_size" not in raw or "font_size_pt" in raw:
        return
    old = raw.pop("font_size")
    if old is None:
        raw["font_size_pt"] = None
    elif _is_int(old) and old > 0:
        raw["font_size_pt"] = min(max(round(old * 72 / 300), int(MIN_PT)), int(MAX_PT))
        settings.warnings.append(f"Schriftgröße von {old} Druckpunkten auf "
                                 f"{raw['font_size_pt']} pt umgerechnet.")
    else:
        settings.warnings.append(f"Einstellung 'font_size' ungültig ({old!r}) – automatisch.")


def save_settings(settings: Settings, path: str | Path | None = None) -> Path:
    path = Path(path) if path else settings_path()
    data = {key: getattr(settings, key) for key in _KEYS}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as e:
        raise OSError(f"Einstellungen konnten nicht gespeichert werden ({path}): "
                      f"{e.strerror or e}") from e
    return path


def new_document(settings: Settings) -> Document:
    """Neues Etikett mit den Standardwerten aus den Einstellungen."""
    return Document(label_id=settings.label_id, orientation=settings.orientation,
                    margin_mm=settings.margin_mm,
                    objects=[TextObject.plain("", size_pt=settings.font_size_pt)])
