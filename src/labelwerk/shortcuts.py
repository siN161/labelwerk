"""Tastenkürzel-Verzeichnis ohne Qt: alle Aktionen mit Standardkürzel und Bereich.

Kürzel sind Texte im Qt-Format („Ctrl+Shift+Z“, „Del“, „Shift+Left“); „“ = kein Kürzel.
Der Kern prüft nur Form und Doppelbelegung, die GUI wandelt mit ``QKeySequence`` um.
Bereiche: ``global`` (überall), ``canvas`` (Arbeitsfläche hat den Fokus),
``edit`` (Schreibmodus: der Editor im Text-Panel hat den Fokus – Fett/Kursiv/Unterstrichen
wirken auch, solange ein anderes Feld des Panels ihn hat). Arbeitsfläche und Schreibmodus
sind nie gleichzeitig aktiv, ein globales Kürzel kollidiert dagegen mit jedem Bereich.
Feste Kürzel (``fixed``, z. B. Esc beendet den Schreibmodus, Enter startet ihn für das
gewählte Textobjekt) lassen sich nicht ändern; Enter ist sonst nicht belegbar, F2 ist die
änderbare Alternative.
"""
from __future__ import annotations

from dataclasses import dataclass

from .i18n import N_, _

SCOPES = ("global", "canvas", "edit")


@dataclass(frozen=True)
class Action:
    id: str          # z. B. "edit.copy"
    name: str        # Anzeigename (englisch, mit N_ markiert – angezeigt wird _(name))
    default: str     # Standardkürzel, "" = keins
    scope: str       # global | canvas | edit
    fixed: bool = False   # Kürzel fest, in den Einstellungen nicht änderbar


ACTIONS: tuple[Action, ...] = (
    Action("file.new", N_("New label"), "Ctrl+N", "global"),
    Action("file.open", N_("Open …"), "Ctrl+O", "global"),
    Action("file.save", N_("Save"), "Ctrl+S", "global"),
    Action("file.save_as", N_("Save as …"), "Ctrl+Shift+S", "global"),
    Action("file.print", N_("Print"), "Ctrl+P", "global"),
    Action("app.settings", N_("Settings"), "Ctrl+,", "global"),
    Action("view.zoom_in", N_("Zoom in"), "Ctrl++", "global"),
    Action("view.zoom_out", N_("Zoom out"), "Ctrl+-", "global"),
    Action("view.zoom_reset", N_("Actual size (100%)"), "Ctrl+0", "global"),
    Action("edit.undo", N_("Undo"), "Ctrl+Z", "global"),
    Action("edit.redo", N_("Redo"), "Ctrl+Shift+Z", "global"),
    Action("tool.select", N_("Select tool"), "Esc", "canvas"),
    Action("tool.text", N_("Add text tool"), "T", "canvas"),
    Action("image.insert", N_("Insert image …"), "Ctrl+Shift+I", "canvas"),
    Action("image.screenshot", N_("Insert screenshot"), "", "canvas"),
    Action("image.symbol", N_("Insert symbol …"), "", "canvas"),
    Action("barcode.insert", N_("Insert barcode"), "", "canvas"),
    Action("edit.cut", N_("Cut"), "Ctrl+X", "canvas"),
    Action("edit.copy", N_("Copy"), "Ctrl+C", "canvas"),
    Action("edit.paste", N_("Paste"), "Ctrl+V", "canvas"),
    Action("edit.duplicate", N_("Duplicate"), "Ctrl+D", "canvas"),
    Action("edit.delete", N_("Delete"), "Del", "canvas"),
    Action("edit.select_all", N_("Select all"), "Ctrl+A", "canvas"),
    Action("object.nudge_left", N_("Move left (0.1 mm)"), "Left", "canvas"),
    Action("object.nudge_right", N_("Move right (0.1 mm)"), "Right", "canvas"),
    Action("object.nudge_up", N_("Move up (0.1 mm)"), "Up", "canvas"),
    Action("object.nudge_down", N_("Move down (0.1 mm)"), "Down", "canvas"),
    Action("object.nudge_left_coarse", N_("Move left (1 mm)"), "Shift+Left", "canvas"),
    Action("object.nudge_right_coarse", N_("Move right (1 mm)"), "Shift+Right", "canvas"),
    Action("object.nudge_up_coarse", N_("Move up (1 mm)"), "Shift+Up", "canvas"),
    Action("object.nudge_down_coarse", N_("Move down (1 mm)"), "Shift+Down", "canvas"),
    Action("object.rotate_left", N_("Rotate 90° left"), "Ctrl+L", "canvas"),
    Action("object.rotate_right", N_("Rotate 90° right"), "Ctrl+R", "canvas"),
    Action("object.bring_forward", N_("Bring forward"), "Ctrl+PgUp", "canvas"),
    Action("object.send_backward", N_("Send backward"), "Ctrl+PgDown", "canvas"),
    Action("align.left", N_("Align left edges"), "", "canvas"),
    Action("align.hcenter", N_("Align horizontal centers"), "", "canvas"),
    Action("align.right", N_("Align right edges"), "", "canvas"),
    Action("align.top", N_("Align top edges"), "", "canvas"),
    Action("align.vcenter", N_("Align vertical centers"), "", "canvas"),
    Action("align.bottom", N_("Align bottom edges"), "", "canvas"),
    Action("align.paper_left", N_("Align left on paper"), "", "canvas"),
    Action("align.paper_hcenter", N_("Center horizontally on paper"), "", "canvas"),
    Action("align.paper_right", N_("Align right on paper"), "", "canvas"),
    Action("align.paper_top", N_("Align top on paper"), "", "canvas"),
    Action("align.paper_vcenter", N_("Center vertically on paper"), "", "canvas"),
    Action("align.paper_bottom", N_("Align bottom on paper"), "", "canvas"),
    Action("size.maximize", N_("Maximize on paper"), "", "canvas"),
    Action("size.same", N_("Same size"), "", "canvas"),
    Action("size.width", N_("Same width"), "", "canvas"),
    Action("size.height", N_("Same height"), "", "canvas"),
    Action("text.start_edit", N_("Start text editing (selected text)"), "F2", "canvas"),
    Action("text.start_edit_enter", N_("Start text editing (Enter)"), "Return", "canvas",
           fixed=True),
    Action("text.end_edit", N_("End text editing"), "Esc", "edit", fixed=True),
    Action("text.bold", N_("Bold"), "Ctrl+B", "edit"),
    Action("text.italic", N_("Italic"), "Ctrl+I", "edit"),
    Action("text.underline", N_("Underline"), "Ctrl+U", "edit"),
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
        raise ValueError(_("Invalid shortcut {seq!r}").format(seq=seq))
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
        warnings.append(_("Shortcut assigned twice: {keys} ({first}, {second}) – “{second}” "
                          "has no shortcut now.").format(keys=seq, first=_(_BY_ID[other].name),
                                                         second=_(entry.name)))
    return clean, warnings


def _clash(scope_a: str, scope_b: str) -> bool:
    return scope_a == scope_b or "global" in (scope_a, scope_b)


def validate(overrides) -> tuple[dict[str, str], list[str]]:
    """Geänderte Kürzel aus den Einstellungen prüfen: ``(gültige, Warnungen)``.

    Unbekannte Aktionen und ungültige Kürzel werden mit Warnung verworfen (Standard gilt);
    „“ ist erlaubt und heißt „kein Kürzel“."""
    if not isinstance(overrides, dict):
        return {}, [_("Setting 'shortcuts' invalid ({value!r}) – default shortcuts active.")
                    .format(value=overrides)]
    clean: dict[str, str] = {}
    warnings: list[str] = []
    for action_id, seq in overrides.items():
        if action_id not in _BY_ID:
            warnings.append(_("Shortcut for unknown action {action!r} ignored.")
                            .format(action=action_id))
        elif not isinstance(seq, str) or not is_well_formed(seq):
            warnings.append(_("Shortcut for {action!r} invalid ({keys!r}) – default {default!r} "
                              "active.").format(action=action_id, keys=seq,
                                                default=_BY_ID[action_id].default))
        elif (normalize(seq) in _RESERVED
              and normalize(seq) != normalize(_BY_ID[action_id].default)):
            warnings.append(_("Shortcut for {action!r} invalid ({keys}) – Esc, Enter and Tab "
                              "cannot be assigned; default {default!r} active.")
                            .format(action=action_id, keys=seq,
                                    default=_BY_ID[action_id].default))
        elif _BY_ID[action_id].fixed and normalize(seq) != normalize(_BY_ID[action_id].default):
            warnings.append(_("Shortcut for {action!r} is fixed ({default}) – setting "
                              "ignored.").format(action=action_id,
                                                 default=_BY_ID[action_id].default))
        else:
            clean[action_id] = seq
    return clean, warnings
