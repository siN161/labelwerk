"""Tastenkürzel-Verzeichnis ohne Qt: alle Aktionen mit Standardkürzel und Bereich.

Kürzel sind Texte im Qt-Format („Ctrl+Shift+Z“, „Del“, „Shift+Left“); „“ = kein Kürzel.
Der Kern prüft nur Form und Doppelbelegung, die GUI wandelt mit ``QKeySequence`` um.
Bereiche: ``global`` (überall), ``canvas`` (Arbeitsfläche hat den Fokus),
``edit`` (Schreibmodus: der Editor im Text-Panel hat den Fokus – Fett/Kursiv/Unterstrichen
wirken auch, solange ein anderes Feld des Panels ihn hat). Arbeitsfläche und Schreibmodus
sind nie gleichzeitig aktiv, ein globales Kürzel kollidiert dagegen mit jedem Bereich.
Feste Kürzel (``fixed``, z. B. Esc beendet den Schreibmodus) lassen sich nicht ändern.
"""
from __future__ import annotations

from dataclasses import dataclass

SCOPES = ("global", "canvas", "edit")


@dataclass(frozen=True)
class Action:
    id: str          # z. B. "edit.copy"
    name: str        # Anzeigename
    default: str     # Standardkürzel, "" = keins
    scope: str       # global | canvas | edit
    fixed: bool = False   # Kürzel fest, in den Einstellungen nicht änderbar


ACTIONS: tuple[Action, ...] = (
    Action("file.print", "Drucken", "Ctrl+P", "global"),
    Action("app.settings", "Einstellungen", "Ctrl+,", "global"),
    Action("view.zoom_in", "Vergrößern (Zoom)", "Ctrl++", "global"),
    Action("view.zoom_out", "Verkleinern (Zoom)", "Ctrl+-", "global"),
    Action("view.zoom_reset", "Echte Größe (100 %)", "Ctrl+0", "global"),
    Action("edit.undo", "Rückgängig", "Ctrl+Z", "global"),
    Action("edit.redo", "Wiederherstellen", "Ctrl+Shift+Z", "global"),
    Action("tool.select", "Werkzeug Auswahl", "Esc", "canvas"),
    Action("tool.text", "Werkzeug Text anlegen", "T", "canvas"),
    Action("edit.cut", "Ausschneiden", "Ctrl+X", "canvas"),
    Action("edit.copy", "Kopieren", "Ctrl+C", "canvas"),
    Action("edit.paste", "Einfügen", "Ctrl+V", "canvas"),
    Action("edit.duplicate", "Duplizieren", "Ctrl+D", "canvas"),
    Action("edit.delete", "Löschen", "Del", "canvas"),
    Action("edit.select_all", "Alles auswählen", "Ctrl+A", "canvas"),
    Action("object.nudge_left", "Nach links (0,1 mm)", "Left", "canvas"),
    Action("object.nudge_right", "Nach rechts (0,1 mm)", "Right", "canvas"),
    Action("object.nudge_up", "Nach oben (0,1 mm)", "Up", "canvas"),
    Action("object.nudge_down", "Nach unten (0,1 mm)", "Down", "canvas"),
    Action("object.nudge_left_coarse", "Nach links (1 mm)", "Shift+Left", "canvas"),
    Action("object.nudge_right_coarse", "Nach rechts (1 mm)", "Shift+Right", "canvas"),
    Action("object.nudge_up_coarse", "Nach oben (1 mm)", "Shift+Up", "canvas"),
    Action("object.nudge_down_coarse", "Nach unten (1 mm)", "Shift+Down", "canvas"),
    Action("object.rotate_left", "90° nach links drehen", "Ctrl+L", "canvas"),
    Action("object.rotate_right", "90° nach rechts drehen", "Ctrl+R", "canvas"),
    Action("object.bring_forward", "Nach vorne", "Ctrl+PgUp", "canvas"),
    Action("object.send_backward", "Nach hinten", "Ctrl+PgDown", "canvas"),
    Action("align.left", "Aneinander links ausrichten", "", "canvas"),
    Action("align.hcenter", "Aneinander waagrecht mittig ausrichten", "", "canvas"),
    Action("align.right", "Aneinander rechts ausrichten", "", "canvas"),
    Action("align.top", "Aneinander oben ausrichten", "", "canvas"),
    Action("align.vcenter", "Aneinander senkrecht mittig ausrichten", "", "canvas"),
    Action("align.bottom", "Aneinander unten ausrichten", "", "canvas"),
    Action("align.paper_left", "Am Papier links ausrichten", "", "canvas"),
    Action("align.paper_hcenter", "Am Papier waagrecht mittig ausrichten", "", "canvas"),
    Action("align.paper_right", "Am Papier rechts ausrichten", "", "canvas"),
    Action("align.paper_top", "Am Papier oben ausrichten", "", "canvas"),
    Action("align.paper_vcenter", "Am Papier senkrecht mittig ausrichten", "", "canvas"),
    Action("align.paper_bottom", "Am Papier unten ausrichten", "", "canvas"),
    Action("size.maximize", "Auf Papier maximieren", "", "canvas"),
    Action("size.same", "Gleiche Größe", "", "canvas"),
    Action("size.width", "Gleiche Breite", "", "canvas"),
    Action("size.height", "Gleiche Höhe", "", "canvas"),
    Action("text.end_edit", "Schreibmodus beenden", "Esc", "edit", fixed=True),
    Action("text.bold", "Fett", "Ctrl+B", "edit"),
    Action("text.italic", "Kursiv", "Ctrl+I", "edit"),
    Action("text.underline", "Unterstrichen", "Ctrl+U", "edit"),
)

_BY_ID = {a.id: a for a in ACTIONS}
_MODIFIERS = ("Ctrl", "Alt", "Shift", "Meta")          # Reihenfolge wie Qt
# bedienen Textfeld, Tabelle und Dialoge: als Kürzel nicht belegbar (außer als eigener Standard)
_RESERVED = {"Esc", "Return", "Enter", "Tab", "Backtab", "Shift+Tab"}
_KEY_ALIASES = {"del": "Del", "delete": "Del", "esc": "Esc", "escape": "Esc",
                "ins": "Ins", "insert": "Ins", "pgup": "PgUp", "pageup": "PgUp",
                "pgdown": "PgDown", "pagedown": "PgDown"}


def action(action_id: str) -> Action:
    """Aktion zur ID (``KeyError`` bei unbekannter ID)."""
    return _BY_ID[action_id]


# --- Form ---------------------------------------------------------------------------
def _split(seq: str) -> tuple[list[str], str]:
    """Kürzel in Umschalttasten und Taste zerlegen („Ctrl++“ = Strg und Plus).

    „++“ ergibt eine leere Umschalttaste und ist damit ungültig."""
    if seq == "+":
        return [], "+"
    if seq.endswith("++"):
        return seq[:-2].split("+"), "+"
    *mods, key = seq.split("+")
    return mods, key


def _parse(seq: str) -> tuple[frozenset[str], str] | None:
    """Umschalttasten (normiert) und Taste, oder None bei ungültiger Form."""
    mods, key = _split(seq)
    known = {m.casefold(): m for m in _MODIFIERS}
    normed = [known.get(m.casefold()) for m in mods]
    if None in normed or len(set(normed)) != len(normed):
        return None                              # unbekannte oder doppelte Umschalttaste
    if not key or key != key.strip() or key.casefold() in known:
        return None                              # Taste fehlt oder ist nur eine Umschalttaste
    return frozenset(normed), key


def is_well_formed(seq: str) -> bool:
    """True für ein Kürzel in Qt-Form oder „“ (kein Kürzel); kein Text = nicht wohlgeformt."""
    return isinstance(seq, str) and (seq == "" or _parse(seq) is not None)


def normalize(seq: str) -> str:
    """Einheitliche Schreibweise (Groß/klein, Reihenfolge, Tastennamen) zum Vergleichen.

    ``ValueError`` bei ungültiger Form."""
    if seq == "":
        return ""
    parsed = _parse(seq) if isinstance(seq, str) else None
    if parsed is None:
        raise ValueError(f"Ungültiges Tastenkürzel {seq!r}")
    mods, key = parsed
    key = _KEY_ALIASES.get(key.casefold(), key.upper() if len(key) == 1 else key.capitalize())
    return "+".join([m for m in _MODIFIERS if m in mods] + [key])


# --- Verzeichnis anwenden -------------------------------------------------------------
def effective(overrides: dict[str, str]) -> dict[str, str]:
    """Wirksame Kürzel aller Aktionen: Standard, überschrieben durch ``overrides`` (feste
    Kürzel bleiben)."""
    mapping = {a.id: a.default for a in ACTIONS}
    mapping.update({k: v for k, v in overrides.items() if k in _BY_ID and not _BY_ID[k].fixed})
    return mapping


def conflicts(mapping: dict[str, str]) -> list[tuple[str, list[str]]]:
    """Doppelt belegte Kürzel: ``[(Kürzel, [Aktions-IDs])]``, nach Kürzel sortiert.

    Kollision = gleiches Kürzel im selben Bereich oder ein globales gegen jeden Bereich.
    Leere, ungültige Kürzel und unbekannte IDs werden übergangen.
    """
    groups: dict[str, list[str]] = {}
    for action_id, seq in mapping.items():
        if action_id in _BY_ID and seq and is_well_formed(seq):
            groups.setdefault(normalize(seq), []).append(action_id)
    result = []
    for seq, ids in sorted(groups.items()):
        clashing = {a for a in ids for b in ids
                    if a != b and _clash(_BY_ID[a].scope, _BY_ID[b].scope)}
        if clashing:
            result.append((seq, sorted(clashing)))
    return result


def without_conflicts(mapping: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Doppelbelegungen auflösen (z. B. von Hand bearbeitete settings.json): Feste Kürzel
    bleiben immer; sonst behält die Aktion, die im Verzeichnis zuerst steht, das Kürzel,
    spätere bekommen keins. ``(Kürzel, Warnungen)``.
    """
    clean = dict(mapping)
    kept: list[tuple[str, str]] = []                    # (normalisiertes Kürzel, Aktions-ID)
    warnings: list[str] = []
    for entry in sorted(ACTIONS, key=lambda a: not a.fixed):   # feste zuerst, sonst stabil
        seq = clean.get(entry.id, "")
        if not seq or not is_well_formed(seq):
            continue
        key = normalize(seq)
        other = next((i for k, i in kept if k == key and _clash(_BY_ID[i].scope, entry.scope)),
                     None)
        if other is None:
            kept.append((key, entry.id))
            continue
        clean[entry.id] = ""
        warnings.append(f"Tastenkürzel doppelt belegt: {seq} ({_BY_ID[other].name}, "
                        f"{entry.name}) – „{entry.name}“ ohne Kürzel.")
    return clean, warnings


def _clash(scope_a: str, scope_b: str) -> bool:
    return scope_a == scope_b or "global" in (scope_a, scope_b)


def validate(overrides) -> tuple[dict[str, str], list[str]]:
    """Geänderte Kürzel aus den Einstellungen prüfen: ``(gültige, Warnungen)``.

    Unbekannte Aktionen und ungültige Kürzel werden mit Warnung verworfen (Standard gilt);
    „“ ist erlaubt und heißt „kein Kürzel“."""
    if not isinstance(overrides, dict):
        return {}, [f"Einstellung 'shortcuts' ungültig ({overrides!r}) – Standardkürzel aktiv."]
    clean: dict[str, str] = {}
    warnings: list[str] = []
    for action_id, seq in overrides.items():
        if action_id not in _BY_ID:
            warnings.append(f"Tastenkürzel für unbekannte Aktion {action_id!r} ignoriert.")
        elif not isinstance(seq, str) or not is_well_formed(seq):
            warnings.append(f"Tastenkürzel für {action_id!r} ungültig ({seq!r}) – "
                            f"Standard {_BY_ID[action_id].default!r} aktiv.")
        elif (normalize(seq) in _RESERVED
              and normalize(seq) != normalize(_BY_ID[action_id].default)):
            warnings.append(f"Tastenkürzel für {action_id!r} ungültig ({seq}) – Esc, Enter und "
                            f"Tab sind nicht belegbar; Standard "
                            f"{_BY_ID[action_id].default!r} aktiv.")
        elif _BY_ID[action_id].fixed and normalize(seq) != normalize(_BY_ID[action_id].default):
            warnings.append(f"Tastenkürzel für {action_id!r} ist fest "
                            f"({_BY_ID[action_id].default}) – Einstellung ignoriert.")
        else:
            clean[action_id] = seq
    return clean, warnings
