"""Settings for GUI and CLI in $XDG_CONFIG_HOME/labelwerk/settings.json.

Missing or invalid values fall back to the default – with a hint in
`Settings.warnings`, never with an exception. New setting = new field + validation rule.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import shortcuts as _shortcuts
from .clipart import RECENT_LIMIT
from .document import MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
from .fonts import DEFAULT_FAMILY
from . import i18n
from .i18n import N_, _
from .imaging import MODES
from .labels import labels_for_model, sized_label
from . import zpl
from .printers import SUPPORTED_MODELS, NetworkEntry, effective_model, is_model
from .storage import RECENT_FILES

THEMES = ("blackwerk", "classic")
OLD_THEMES = {"rawblock": "blackwerk"}      # renamed designs: old saved name → new one
RESTART_KEYS = ("language", "start_zoom", "start_tool", "system_file_dialog")   # only after a restart (hint)
# tab at startup: "last" = last used, otherwise a tool key (gui/tools.py TOOLS)
START_TOOLS = ("last", "file", "paper", "text", "image", "barcode", "layout", "series", "parcel")
# tabs that can be hidden (FILE and PAPER always stay – the label is chosen there)
HIDEABLE_TOOLS = tuple(key for key in START_TOOLS[1:] if key not in ("file", "paper"))
SYMBOL_LISTS = ("symbols_recent", "symbols_favorites")
# invalid → default without a hint: only remembered (last_tool) or only show/hide (hidden_tools)
QUIET_KEYS = ("last_tool", "hidden_tools")


@dataclass
class Settings:
    label_id: str = "62"
    orientation: str = "vertical"
    margin_mm: float = 1.0
    font_size_pt: float | None = None      # None = automatic
    font_family: str = DEFAULT_FAMILY
    fonts_all: bool = False                # font choice: all families instead of the short list
    check_media_on_start: bool = True
    start_zoom: int = 200
    start_tool: str = "paper"              # tab at startup (START_TOOLS; "last" = last used)
    last_tool: str = ""                    # last used tab (saved silently)
    hidden_tools: list[str] = field(default_factory=list)   # hidden tabs (HIDEABLE_TOOLS)
    theme: str = "blackwerk"               # "blackwerk" or "classic" (Qt system style)
    system_file_dialog: bool = False       # desktop file dialog (portal) instead of our own with preview
    image_crop: bool = True                # crop images to their content when inserting
    image_rotate: bool = False             # rotate images if they only fit 1:1 when rotated
    image_mode: str = "line"               # new images: line art ("line") or photo ("photo")
    image_threshold: int = 128             # new images: threshold 0–255
    symbols_recent: list[str] = field(default_factory=list)      # symbol ids, newest first
    symbols_favorites: list[str] = field(default_factory=list)   # symbol ids
    recent_files: list[str] = field(default_factory=list)   # recently opened (paths), newest first
    start_favorite: str | None = None      # favourite labelwerk starts with; None = empty
    printer: str = ""                      # selected printer (URI); "" = automatic
    printer_model: str = ""                # fallback if the model is not detected; "" = none
    last_model: str = ""                   # model detected last (applies without a printer)
    network_printers: list[dict] = field(default_factory=list)   # {name, host, model}
    printer_options: dict[str, dict[str, str]] = field(default_factory=dict)  # model → print options
    zebra_dpi: int = 0                  # resolution of USB Zebras, 0 = detected
    cups_all: bool = False              # printer menu: also show CUPS office printers (A4/Letter)
    language: str = ""                  # "" = language of the system, otherwise "de", "en" …
    shortcuts: dict[str, str] = field(default_factory=dict)   # changed shortcuts only, "" = none
    warnings: list[str] = field(default_factory=list, compare=False, repr=False)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _rules(model: str | None = None) -> dict:
    """Validation rules; the label must be a known one – whether it fits the printer is checked by the GUI and
    CLI only with the detected model (whoever alternates between two printers keeps their label)."""
    known = {lab.id for m in SUPPORTED_MODELS for lab in labels_for_model(m)}
    return {
        "label_id": lambda v: isinstance(v, str) and (v in known or sized_label(v) is not None),
        "orientation": lambda v: v in ORIENTATIONS,
        "margin_mm": lambda v: (_is_int(v) or isinstance(v, float)) and 0 <= v <= MAX_MARGIN_MM,
        "font_size_pt": lambda v: v is None or ((_is_int(v) or isinstance(v, float))
                                                and MIN_PT <= v <= MAX_PT),
        "font_family": lambda v: isinstance(v, str) and bool(v.strip()),
        "fonts_all": lambda v: isinstance(v, bool),
        "check_media_on_start": lambda v: isinstance(v, bool),
        "start_zoom": lambda v: _is_int(v) and 25 <= v <= 400,
        "theme": lambda v: v in THEMES,
        "system_file_dialog": lambda v: isinstance(v, bool),
        "image_crop": lambda v: isinstance(v, bool),
        "image_rotate": lambda v: isinstance(v, bool),
        "image_mode": lambda v: v in MODES,
        "image_threshold": lambda v: _is_int(v) and 0 <= v <= 255,
        "start_tool": lambda v: v in START_TOOLS,
        "last_tool": lambda v: v == "" or (v in START_TOOLS and v != "last"),
        "hidden_tools": lambda v: isinstance(v, list),
        "symbols_recent": lambda v: isinstance(v, list),
        "symbols_favorites": lambda v: isinstance(v, list),
        "recent_files": lambda v: isinstance(v, list),
        "start_favorite": lambda v: v is None or (isinstance(v, str) and bool(v.strip())),
        "printer": lambda v: isinstance(v, str) and (
            v == "" or v.startswith(("file://", "tcp://", "usb://", "cups:", "zpl+file://",
                                     "zpl+tcp://"))),
        "printer_model": lambda v: v == "" or v in SUPPORTED_MODELS,
        "last_model": lambda v: v == "" or is_model(v),
        "language": lambda v: v == "" or v in i18n.available(),
        "zebra_dpi": lambda v: v in (0, *zpl.RESOLUTIONS) and not isinstance(v, bool),
        "printer_options": lambda v: isinstance(v, dict),
        "cups_all": lambda v: isinstance(v, bool),
        "network_printers": lambda v: isinstance(v, list),
    }


_KEYS = (*_rules(), "shortcuts")
_DISCARDED = N_("Setting {key!r}: invalid entries discarded.")


def _option_word(value, empty: bool = False) -> bool:
    """Key or value of a print option: one word (``lp -o`` splits at spaces);
    ``empty``: empty allowed (Zebra mode "as set on the printer")."""
    return isinstance(value, str) and value.isprintable() and (bool(value) or empty) \
        and not any(c.isspace() or c in "='\"" for c in value)


def _printer_options(value: dict, warnings: list[str]) -> dict[str, dict[str, str]]:
    """Print options per model: invalid entries dropped one by one (with a hint)."""
    valid = {k: {a: b for a, b in o.items() if _option_word(a) and _option_word(b, empty=True)}
             for k, o in value.items() if isinstance(k, str) and isinstance(o, dict)}
    if len(valid) != len(value) or any(len(valid[k]) != len(value[k]) for k in valid):
        warnings.append(_(_DISCARDED).format(key="printer_options"))
    return {k: o for k, o in valid.items() if o}


def start_tool_for(start_tool: str, hidden_tools: list[str]) -> str:
    """Tab labelwerk really starts with: a hidden start tab becomes PAPER
    (like ``MainWindow._start_tool``)."""
    return "paper" if start_tool in hidden_tools else start_tool


def started_values(settings: Settings) -> dict:
    """What applied at startup (for ``restart_pending``): the chosen language and the restart
    settings (start tab as effective, hidden = PAPER)."""
    return {**{key: getattr(settings, key) for key in RESTART_KEYS}, "language": i18n.language(),
            "start_tool": start_tool_for(settings.start_tool, settings.hidden_tools)}


def restart_pending(values: dict, started: dict) -> bool:
    """Does a setting only differ after a restart? ``values``: chosen values
    of the restart settings (``RESTART_KEYS``); language compared as effective ("" = system language),
    the others with the value at startup."""
    language = values["language"]
    effective = language if language in i18n.available() else i18n.system_language()
    return effective != started["language"] or any(
        values[key] != started[key] for key in RESTART_KEYS if key != "language")


def _configured(path: str | Path | None, key: str, valid) -> object | None:
    """Value ``key`` directly from the file (read before anything else); unreadable/invalid → None."""
    try:
        raw = json.loads(Path(path or settings_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = raw.get(key) if isinstance(raw, dict) else None
    return value if valid(value) else None


def configured_language(path: str | Path | None = None) -> str:
    """Configured language ("" = system) – read before anything else (the messages while loading the
    settings already come in this language); unreadable or invalid → ""."""
    return _configured(path, "language",
                       lambda v: isinstance(v, str) and v in i18n.available()) or ""


def configured_file_dialog(path: str | Path | None = None) -> bool:
    """System file dialog configured? – read before the interface starts (the
    Qt platform theme applies from the moment the application is created)."""
    return _configured(path, "system_file_dialog", lambda v: isinstance(v, bool)) is True


def settings_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "labelwerk" / "settings.json"


def load_settings(path: str | Path | None = None, model: str | None = None) -> Settings:
    """``model``: model for checking the label; None = from the settings (fallback model,
    last detected)."""
    path = Path(path) if path else settings_path()
    settings = Settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(_("not a JSON object"))
    except FileNotFoundError:
        return settings
    except (OSError, ValueError) as e:
        settings.warnings.append(_("Settings not readable ({path}): {error} – using defaults.")
                                 .format(path=path, error=e))
        return settings
    _migrate_font_size(raw, settings)
    if raw.get("theme") in OLD_THEMES:                    # renamed design: silently the new name
        raw["theme"] = OLD_THEMES[raw["theme"]]
    if model is None:
        model = _model_of(raw)
    for key, valid in _rules(model).items():
        if key not in raw:
            continue
        value = raw[key]
        if key == "font_family" and isinstance(value, str):
            value = value.strip()
        if valid(value):
            if key == "margin_mm":
                value = float(value)
            elif key in SYMBOL_LISTS:
                value = _symbol_ids(key, value, settings.warnings)
            elif key == "recent_files":
                value = _text_list(key, value, settings.warnings)[:RECENT_FILES]
            elif key == "hidden_tools":            # silent: FILE/PAPER and unknown ones are dropped
                value = list(dict.fromkeys(v for v in value if v in HIDEABLE_TOOLS))
            elif key == "network_printers":
                value = _network(value, settings.warnings)
            elif key == "printer_options":
                value = _printer_options(value, settings.warnings)
            setattr(settings, key, value)
        elif key not in QUIET_KEYS:
            settings.warnings.append(_("Setting {key!r} invalid ({value!r}) – using default "
                                       "{default!r}.").format(key=key, value=value,
                                                              default=getattr(settings, key)))
    if "shortcuts" in raw:                 # each shortcut is checked on its own: valid ones are kept
        settings.shortcuts, warnings = _shortcuts.validate(raw["shortcuts"])
        settings.warnings.extend(warnings)
    return settings


def _model_of(raw: dict) -> str:
    """Model for checking the label: from the settings (fallback model, last detected)."""
    return effective_model(None, *(raw.get(k) if raw.get(k) in SUPPORTED_MODELS else ""
                                   for k in ("printer_model", "last_model")))


def _text_list(key: str, value: list, warnings: list[str]) -> list[str]:
    """List of texts: invalid entries dropped one by one (with a hint), duplicates removed."""
    valid = [i for i in value if isinstance(i, str) and i]
    if len(valid) != len(value):
        warnings.append(_(_DISCARDED).format(key=key))
    return list(dict.fromkeys(valid))


def _network(value: list, warnings: list[str]) -> list[dict]:
    """Network printers: entries with host (no spaces, no scheme) and known model
    (Brother QL or Zebra "zpl:203");
    invalid ones dropped one by one (with a hint)."""
    valid = [{"name": e.get("name") or "", "host": e["host"].strip(), "model": e["model"]}
             for e in value if isinstance(e, dict) and isinstance(e.get("host"), str)
             and valid_host(e["host"]) and (e.get("model") in SUPPORTED_MODELS
                                             or zpl.is_model(e.get("model")))
             and isinstance(e.get("name", ""), str)]
    if len(valid) != len(value):
        warnings.append(_(_DISCARDED).format(key="network_printers"))
    return valid


def valid_host(host: str) -> bool:
    """IPv4 address or hostname (without scheme, path, port, spaces and control characters; IPv6 does
    not work – ":" separates the port)."""
    host = host.strip()
    return (bool(host) and host.isprintable() and not any(c in host for c in " /:")
            and len(host) <= 253)


def network_entries(settings: Settings) -> list[NetworkEntry]:
    """Network printers of the settings for ``printers.network_printers``."""
    return [NetworkEntry(e["name"], e["host"], e["model"]) for e in settings.network_printers]


def _symbol_ids(key: str, value: list, warnings: list[str]) -> list[str]:
    """Symbol ids: invalid entries dropped one by one (with a hint), duplicates removed,
    recently used limited to ``RECENT_LIMIT``."""
    ids = _text_list(key, value, warnings)
    return ids[:RECENT_LIMIT] if key == "symbols_recent" else ids


def _migrate_font_size(raw: dict, settings: Settings) -> None:
    """Convert the old setting ``font_size`` (dots at 300 dpi) to pt once."""
    if "font_size" not in raw or "font_size_pt" in raw:
        return
    old = raw.pop("font_size")
    if old is None:
        raw["font_size_pt"] = None
    elif _is_int(old) and old > 0:
        raw["font_size_pt"] = min(max(round(old * 72 / 300), int(MIN_PT)), int(MAX_PT))
        settings.warnings.append(_("Font size converted from {old} dots to {new} pt.").format(
            old=old, new=raw["font_size_pt"]))
    else:
        settings.warnings.append(_("Setting 'font_size' invalid ({value!r}) – automatic.").format(
            value=old))


def save_settings(settings: Settings, path: str | Path | None = None) -> Path:
    return _write({key: getattr(settings, key) for key in _KEYS}, path)


def update_settings(path: str | Path | None = None, base: Settings | None = None, **fields) -> Path:
    """Write only ``fields`` to the file (silent saving: recently used, favourites,
    selected printer …): the file is read again, everything else stays as it is there –
    also what a second instance has saved in the meantime or a newer version knows.
    If the file is missing or unreadable, ``base`` (state in memory) or the default applies.
    What was only reported while loading is cleaned up (otherwise the message would come at every
    start): the old font size converted, invalid values replaced by the value from ``base``
    (or the validated one of the file)."""
    unknown = [key for key in fields if key not in _KEYS]
    if unknown:
        raise KeyError(unknown[0])
    target = Path(path) if path else settings_path()
    source = base if base is not None else Settings()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")          # internal, never shown
    except (OSError, ValueError):
        data = {key: getattr(source, key) for key in _KEYS}
    else:
        _clean(data, target, base)
    data.update(fields)
    return _write(data, target)


def _clean(data: dict, path: Path, base: Settings | None) -> None:
    """Clean up the read settings the way ``load_settings`` understands them: old font size
    converted; invalid values replaced by the value from ``base`` (state in memory), only partially
    invalid ones (single entries of a list) by the cleaned value of the file – the
    rest may have been saved more recently by a second instance. Unknown keys stay."""
    checked = load_settings(path)
    if "font_size" in data and "font_size_pt" not in data:
        data.pop("font_size")
        data["font_size_pt"] = checked.font_size_pt
    rules = _rules(_model_of(data))
    for key in _KEYS:
        if key not in data or data[key] == getattr(checked, key):
            continue
        valid = key in rules and rules[key](data[key])
        data[key] = getattr(checked if valid or base is None else base, key)


def _write(data: dict, path: str | Path | None) -> Path:
    path = Path(path) if path else settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # write next to it first, then replace: a crash in the middle of writing leaves the old
        # file intact (the GUI silently saves recently used/favourites on every insert)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    except OSError as e:
        raise OSError(_("Settings could not be saved ({path}): {reason}").format(
            path=path, reason=e.strerror or e)) from e
    return path


def new_document(settings: Settings) -> Document:
    """New label with the default values from the settings."""
    family = None if settings.font_family == DEFAULT_FAMILY else settings.font_family
    return Document(label_id=settings.label_id, orientation=settings.orientation,
                    margin_mm=settings.margin_mm,
                    objects=[TextObject.plain("", size_pt=settings.font_size_pt, family=family)])
