# Text-Formatierung (Etappe 3a/3b) – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zeichenweise Formatierung wie im P-touch Editor: Schriftart, Größe in pt, fett/kursiv/unterstrichen, Textposition je Absatz, „Feste Rahmengröße“ – im Kern (Qt-frei), in der CLI und als Rich-Text-Editor in der GUI.

**Architecture:** Neues Textmodell `Span`/`Paragraph`/`TextObject` im Kern; `render.py` setzt die Stücke selbst (Verallgemeinerung von Pillows `multiline_text`, daher pixelgleich für reinen Text); `fonts.py` findet Schriften über fontconfig. Die GUI übersetzt `QTextDocument` ↔ Modell und führt ein eigenes Grundformat.

**Tech Stack:** Python ≥ 3.10, Pillow 13, fontconfig (`fc-list`/`fc-match`), PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-17-text-formatierung-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge, nach jedem Task volle Suite grün (210 → 216 → 235 → 243 → 258), jeweils dreimal ohne Wackler; Pixelgleichheit gegen den alten Algorithmus in 9 Fällen geprüft; GUI per Offscreen-Screenshot geprüft. Code wörtlich übernehmen.

## Global Constraints

- Kern bleibt **Qt-frei** (`document.py`, `render.py`, `fonts.py`, `settings.py`); keine Drucklogik in der GUI.
- **Vorschau = Druck**; reiner Text mit Standardwerten (DejaVu Sans Bold, zentriert, automatisch) ist **pixelgleich** zu vorher.
- Schriftgrößen für Nutzer in **pt** (4–100); `PT = 300/72` Druckpunkte pro pt.
- Formatierung ohne Markierung wirkt auf den ganzen Text (wie ein ausgewählter Textrahmen in P-touch).
- Benutzer-Meldungen und Kommentare auf Deutsch; keine Tracebacks für Nutzer.
- Tests ohne Hardware und ohne echte Nutzer-Einstellungen (Fixtures in `tests/conftest.py`, `tests/gui/conftest.py`).
- Tests: `.venv/bin/python -m pytest -q` im Repo-Wurzelverzeichnis.
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Code geschrieben hat).

---
### Task 1: Kern – Schriften (`fonts.py`)

**Files:**
- Create: `src/labelwerk/fonts.py`
- Create: `tests/test_fonts.py`

**Interfaces / Produces:** `fonts.DEFAULT_FAMILY = "DejaVu Sans"`, `FontMatch(path, family, bold, italic)`, `families() -> list[str]` (gecacht), `resolve(family, bold, italic) -> FontMatch` (fc-match, gecacht; `bold`/`italic` = Datei ist wirklich diese Variante), `load(path, size) -> ImageFont` (gecacht). Ohne fontconfig: DejaVu-Fallback.

- [ ] **Step 1: Tests schreiben bzw. anpassen**

`tests/test_fonts.py` – **anlegen** (vollständiger Inhalt):

```python
import shutil

import pytest

from labelwerk import fonts

needs_fontconfig = pytest.mark.skipif(shutil.which("fc-match") is None, reason="kein fontconfig")


def test_families_contains_default():
    assert fonts.DEFAULT_FAMILY in fonts.families()


@needs_fontconfig
def test_resolve_default_bold_is_dejavu_bold():
    match = fonts.resolve(None, True, False)
    assert match.path.endswith("DejaVuSans-Bold.ttf")
    assert match.family == "DejaVu Sans" and match.bold and not match.italic


@needs_fontconfig
def test_resolve_regular_differs_from_bold():
    assert fonts.resolve("DejaVu Sans", False, False).path != fonts.resolve("DejaVu Sans", True, False).path


@needs_fontconfig
def test_unknown_family_is_substituted():
    match = fonts.resolve("GibtsGarNicht 4711", False, False)
    assert match.family != "GibtsGarNicht 4711"
    assert match.path


def test_without_fontconfig_falls_back_to_dejavu(monkeypatch):
    monkeypatch.setattr(fonts, "_run", lambda *a: None)
    fonts.resolve.cache_clear()
    fonts.families.cache_clear()
    try:
        assert fonts.families() == ["DejaVu Sans"]
        assert fonts.resolve(None, True, False).path.endswith("DejaVuSans-Bold.ttf")
    finally:
        fonts.resolve.cache_clear()
        fonts.families.cache_clear()


def test_load_is_cached():
    path = fonts.resolve(None, True, False).path
    assert fonts.load(path, 40) is fonts.load(path, 40)
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: `ModuleNotFoundError: No module named 'labelwerk.fonts'`

- [ ] **Step 3: Implementierung**

`src/labelwerk/fonts.py` – **anlegen** (vollständiger Inhalt):

```python
"""Schriften finden (fontconfig) und laden – UI-unabhängig.

Ohne fontconfig (fc-list/fc-match) wird auf DejaVu Sans zurückgefallen.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

DEFAULT_FAMILY = "DejaVu Sans"
_DEJAVU_DIRS = ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/TTF",
                "/usr/share/fonts/dejavu-sans-fonts")


@dataclass(frozen=True)
class FontMatch:
    path: str
    family: str          # tatsächlich gefundene Familie
    bold: bool           # Datei ist wirklich fett
    italic: bool         # Datei ist wirklich kursiv/schräg


def _run(*args: str) -> str | None:
    if shutil.which(args[0]) is None:
        return None
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10,
                              check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None


@lru_cache(maxsize=1)
def families() -> list[str]:
    """Installierte Schriftfamilien, sortiert."""
    out = _run("fc-list", ":", "family")
    if not out:
        return [DEFAULT_FAMILY]
    names = {line.split(",")[0].strip() for line in out.splitlines() if line.strip()}
    return sorted(names, key=str.casefold)


@lru_cache(maxsize=256)
def resolve(family: str | None, bold: bool, italic: bool) -> FontMatch:
    """Datei zu Familie + fett/kursiv; fontconfig ersetzt Fehlendes durch Ähnliches."""
    family = family or DEFAULT_FAMILY
    pattern = family + (":bold" if bold else ":weight=regular") + (":italic" if italic else ":roman")
    out = _run("fc-match", "-f", "%{file}|%{family}|%{style}", pattern)
    if out and out.count("|") >= 2:
        path, found, style = out.split("|", 2)
        found = found.split(",")[0]
        style = style.casefold()
        return FontMatch(path, found, bold=any(w in style for w in ("bold", "black", "heavy")),
                         italic=any(w in style for w in ("italic", "oblique")))
    return _dejavu_fallback(bold)


def _dejavu_fallback(bold: bool) -> FontMatch:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for folder in _DEJAVU_DIRS:
        path = Path(folder) / name
        if path.exists():
            return FontMatch(str(path), DEFAULT_FAMILY, bold=bold, italic=False)
    return FontMatch("", DEFAULT_FAMILY, bold=False, italic=False)   # PIL-Standardschrift


@lru_cache(maxsize=512)
def load(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Schrift in Druckpunkten laden (gecacht)."""
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)
```

- [ ] **Step 4: Grün prüfen** – Run: `.venv/bin/python -m pytest -q` (dreimal) – Expected: `216 passed`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/fonts.py tests/test_fonts.py
git commit -m "Schriften: fontconfig-Anbindung mit DejaVu-Fallback

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Kern – Textmodell, Zeilensatz, pt durchgängig

**Files:**
- Modify: `src/labelwerk/cli.py`
- Modify: `src/labelwerk/document.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/render.py`
- Modify: `src/labelwerk/settings.py`
- Modify: `tests/gui/test_gui_papier.py`
- Modify: `tests/gui/test_gui_settings.py`
- Modify: `tests/gui/test_gui_window.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_document.py`
- Modify: `tests/test_render.py`
- Create: `tests/test_rich_text.py`
- Modify: `tests/test_settings.py`

**Interfaces / Produces:** `document.Span(text, family=None, size_pt=None, bold=True, italic=False, underline=False)`, `Paragraph(spans, align="center")` (`.text`), `TextObject(paragraphs | str, size_pt=None, font_path=None)` mit `.plain(...)`, `.text`, `.is_empty()`; `ALIGNMENTS`, `MIN_PT=4.0`, `MAX_PT=100.0`. `render.render_document` setzt Spans auf gemeinsamer Grundlinie (pixelgleich zu vorher für reinen Text), `render_text(text, label_id, size_pt=None, font_path=None)`, `font_warnings(doc) -> list[str]`, `TextTooLarge(size_pt, max_pt, label_id)` mit `.size_pt`/`.max_pt`, `PT = 300/72`, `REF_PT = 12`. Einstellung `font_size` → `font_size_pt` (alte Werte werden umgerechnet). CLI `-s` in pt (`auto` oder 4–100), Text-Panel und Einstellungsdialog in pt.

- [ ] **Step 1: Tests schreiben bzw. anpassen**

`tests/gui/test_gui_papier.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import MM, Canvas
from labelwerk.gui.main_window import MainWindow
from labelwerk.labels import get_label
from labelwerk.render import render_document
from labelwerk.settings import Settings


@pytest.fixture
def window(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.panel("text").edit.setPlainText("Max Mustermann")
    win.render_now()
    return win


def test_orientation_switch_changes_document_and_preview(window):
    paper = window.panel("paper")
    assert paper.vertical.isChecked()
    paper.horizontal.setChecked(True)
    window.render_now()
    assert window.doc.orientation == "horizontal"
    assert window.image.tobytes() == render_document(window.doc).tobytes()


def test_margin_changes_document_and_length(window):
    paper = window.panel("paper")
    paper.horizontal.setChecked(True)
    window.render_now()
    before = window.image.height
    paper.margin.setValue(5.0)
    window.render_now()
    assert window.doc.margin_mm == 5.0
    assert window.image.height == before + 2 * (59 - 12)


def test_horizontal_view_shows_handle_right_of_label(window):
    window.panel("paper").horizontal.setChecked(True)
    window.render_now()
    canvas = window.canvas
    label_box = canvas.label_view_rect()
    handle = canvas.mapFromScene(canvas.handle.sceneBoundingRect().center())
    assert handle.x() > label_box.right()
    assert label_box.width() > label_box.height()          # Adresse liegt quer im Bild


def test_horizontal_caption_reads_length_first(qtbot):
    view = Canvas()
    qtbot.addWidget(view)
    doc = Document("62", length_mm=50, orientation="horizontal", objects=[TextObject("A")])
    view.set_document(get_label("62"), render_document(doc), "horizontal")
    assert view._caption == "50,0 × 62 mm"


def _mouse(view, kind, scene_point, buttons):
    pos = QPointF(view.mapFromScene(scene_point))
    event = QMouseEvent(kind, pos, QPointF(view.viewport().mapToGlobal(pos.toPoint())),
                        Qt.MouseButton.LeftButton if kind != QMouseEvent.Type.MouseMove
                        else Qt.MouseButton.NoButton,
                        buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), event)


def test_dragging_in_horizontal_view_sets_length(window):
    window.panel("paper").horizontal.setChecked(True)
    window.render_now()
    canvas = window.canvas
    start = canvas.handle.sceneBoundingRect().center()
    end = QPointF(start.x(), start.y() + 80.1 * MM - canvas.label_height())
    _mouse(canvas, QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseMove, end, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
    assert window.doc.length_mm == 80.0


def test_window_starts_with_settings(qtbot):
    settings = Settings(label_id="62x29", orientation="horizontal", margin_mm=3, font_size_pt=19,
                        start_zoom=150)
    win = MainWindow(settings=settings)
    qtbot.addWidget(win)
    assert (win.doc.label_id, win.doc.orientation, win.doc.margin_mm) == ("62x29", "horizontal", 3)
    assert win.panel("paper").horizontal.isChecked()
    assert win.panel("paper").margin.value() == 3.0
    assert not win.panel("text").auto.isChecked() and win.panel("text").size.value() == 19
    assert win.canvas.zoom == 150


def test_settings_warnings_appear_in_status_bar(qtbot):
    win = MainWindow(settings=Settings(warnings=["Einstellung 'start_zoom' ungültig"]))
    qtbot.addWidget(win)
    assert "start_zoom" in win.result.text()
```

`tests/gui/test_gui_settings.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
import json
import os
from pathlib import Path

from PySide6.QtWidgets import QDialog

from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.settings_dialog import SettingsDialog
from labelwerk.settings import Settings, load_settings


def test_dialog_shows_current_settings(qtbot):
    dialog = SettingsDialog(Settings(label_id="62x29", orientation="horizontal", margin_mm=3,
                                     font_size_pt=19, check_media_on_start=False, start_zoom=150))
    qtbot.addWidget(dialog)
    assert dialog.values() == Settings(label_id="62x29", orientation="horizontal", margin_mm=3.0,
                                       font_size_pt=19, check_media_on_start=False, start_zoom=150)


def test_dialog_saves_to_file(qtbot, tmp_path):
    path = tmp_path / "settings.json"
    dialog = SettingsDialog(Settings(), path=path)
    qtbot.addWidget(dialog)
    dialog.orientation.setCurrentIndex(dialog.orientation.findData("horizontal"))
    dialog.font_auto.setChecked(False)
    dialog.font_size.setValue(19)
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    saved = load_settings(path)
    assert (saved.orientation, saved.font_size_pt) == ("horizontal", 19)
    assert dialog.saved == saved


def test_dialog_save_error_keeps_dialog_open(qtbot, tmp_path):
    blocker = tmp_path / "datei"
    blocker.write_text("x")
    dialog = SettingsDialog(Settings(), path=blocker / "settings.json")
    qtbot.addWidget(dialog)
    dialog.accept()
    assert dialog.saved is None
    assert not dialog.error.isHidden() and "nicht gespeichert" in dialog.error.text()


def test_window_opens_dialog_and_takes_new_settings(qtbot, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)

    def fake_exec(dialog):
        dialog.check_media.setChecked(False)
        dialog.accept()                       # speichert in XDG_CONFIG_HOME (Test-Ordner)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(SettingsDialog, "exec", fake_exec)
    win.settings_action.trigger()
    assert win.settings.check_media_on_start is False
    path = Path(os.environ["XDG_CONFIG_HOME"]) / "labelwerk" / "settings.json"
    assert json.loads(path.read_text())["check_media_on_start"] is False
    assert "gespeichert" in win.result.text()


def test_qt_dialog_buttons_are_german(qapp):
    import pytest
    from PySide6.QtWidgets import QDialogButtonBox
    from labelwerk.gui.app import install_translations
    translator = install_translations(qapp)
    if translator is None:
        pytest.skip("qtbase_de.qm nicht installiert")
    try:
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        assert sorted(b.text() for b in box.buttons()) == ["Abbrechen", "Speichern"]
    finally:
        qapp.removeTranslator(translator)
```

`tests/gui/test_gui_window.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from labelwerk.gui.app import load_theme
from labelwerk.gui.canvas import MM
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.tools import TOOLS


@pytest.fixture
def window(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    return win


def test_theme_is_packaged():
    assert "QToolBar" in load_theme()


def test_registry_creates_button_and_panel_per_tool(window):
    assert list(window.tool_actions) == [tool.key for tool in TOOLS]
    assert window.panels.count() == len(TOOLS)
    window.tool_actions["text"].trigger()
    assert window.panels.currentWidget() is window.panel("text")


def test_typing_updates_preview(window, qtbot):
    before = window.image.tobytes()
    window.panel("text").edit.setPlainText("Hallo")
    qtbot.waitUntil(lambda: window.image.tobytes() != before, timeout=1000)


def test_too_large_font_shows_hint_in_text_panel(window):
    panel = window.panel("text")
    panel.edit.setPlainText("Sehr langer Text")
    panel.auto.setChecked(False)
    panel.size.setValue(72)
    window.render_now()
    assert not panel.error.isHidden()
    assert "höchstens" in panel.error.text()


def test_changing_label_changes_preview_size(window):
    paper = window.panel("paper")
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    window.render_now()
    assert window.image.size == (696, 271)


def test_paper_panel_shows_length_only_for_endless(window):
    paper = window.panel("paper")
    assert not paper.length_box.isHidden() and paper.fixed_size.isHidden()
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    assert paper.length_box.isHidden()
    assert paper.fixed_size.text() == "62 × 29 mm · gestanzt"


def test_fixed_length_sets_preview_height(window):
    paper = window.panel("paper")
    paper.length_auto.setChecked(False)
    paper.length.setValue(50.0)
    window.render_now()
    assert window.image.height == round(50 * MM)


def _mouse(view, kind, scene_point, buttons):
    pos = QPointF(view.mapFromScene(scene_point))
    event = QMouseEvent(kind, pos, QPointF(view.viewport().mapToGlobal(pos.toPoint())),
                        Qt.MouseButton.LeftButton if kind != QMouseEvent.Type.MouseMove
                        else Qt.MouseButton.NoButton,
                        buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), event)


def _drag_handle(window, to_y):
    """Untere Schnittkante am Anfasser auf Szene-y to_y ziehen (Greifversatz bleibt erhalten)."""
    canvas = window.canvas
    start = canvas.handle.sceneBoundingRect().center()
    end = QPointF(start.x(), start.y() + to_y - canvas.label_height())
    _mouse(canvas, QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseMove, end, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)


def test_dragging_handle_sets_fixed_length(window):
    _drag_handle(window, 40.1 * MM)   # ±1 Pixel Rundung bleibt im 0,5-mm-Raster
    assert window.doc.length_mm == 40.0                   # Raster 0,5 mm
    paper = window.panel("paper")
    assert not paper.length_auto.isChecked()
    assert paper.length.value() == 40.0


def test_dragging_below_minimum_stops_at_12_7_mm(window):
    _drag_handle(window, 2 * MM)
    assert window.doc.length_mm == pytest.approx(12.7, abs=0.01)


def test_double_click_on_handle_resets_to_automatic(window):
    _drag_handle(window, 40 * MM)
    window.render_now()
    center = window.canvas.handle.sceneBoundingRect().center()
    _mouse(window.canvas, QMouseEvent.Type.MouseButtonDblClick, center, Qt.MouseButton.LeftButton)
    assert window.doc.length_mm is None
    assert window.panel("paper").length_auto.isChecked()


def test_print_success_shows_status_and_reenables_button(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")
    sent = {}

    def fake_print(image, label_id, **kw):
        sent["size"] = image.size
        return {"outcome": "printed", "did_print": True}

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image", fake_print)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert window.result.text() == "Gedruckt ✓"
    assert sent["size"][0] == 696


def test_print_error_is_shown(window, qtbot, monkeypatch):
    from labelwerk.printer import PrintError

    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")

    def fail(*a, **kw):
        raise PrintError("Eingelegte Rolle passt nicht zum Etikett '62'")

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image", fail)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "Rolle passt nicht" in window.result.text()


def test_no_printer_message(window, qtbot):
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "nicht gefunden" in window.result.text()


def test_empty_label_asks_and_cancel_does_not_print(window, monkeypatch):
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **kw: asked.append(a) or QMessageBox.StandardButton.Cancel)
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: pytest.fail("darf nicht drucken"))
    window.print_label()
    assert asked
    assert window.print_action.isEnabled()
    assert window.result.text() == ""


def test_detection_error_does_not_hang_button(window, qtbot, monkeypatch):
    def broken():
        raise OSError("kaputt")

    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp", broken)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "kaputt" in window.result.text()


def test_new_print_resets_result_state(window, qtbot, monkeypatch):
    from labelwerk.printer import PrintError

    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")

    def fail(*a, **kw):
        raise PrintError("kaputt")

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image", fail)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert window.result.property("state") == "error"

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: {"outcome": "printed", "did_print": True})
    window.print_label()
    assert window.result.property("state") == ""
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert window.result.property("state") == "ok"


def _press_move(window, dy_mm, kind=QMouseEvent.Type.MouseMove, start=None):
    canvas = window.canvas
    point = QPointF(start.x(), start.y() + dy_mm * MM)
    _mouse(canvas, kind, point, Qt.MouseButton.LeftButton)


def test_drag_without_motion_does_not_drift_and_renders_only_on_release(window, qtbot):
    canvas = window.canvas
    start = canvas.handle.sceneBoundingRect().center()
    height_before = canvas.label_height()
    _mouse(canvas, QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton)
    _press_move(window, 10, start=start)
    first = window.doc.length_mm
    qtbot.wait(300)   # früher: Render mitten im Ziehen verschob das Etikett unter dem Cursor
    assert canvas.label_height() == height_before
    _press_move(window, 10, start=start)
    assert window.doc.length_mm == first
    end = QPointF(start.x(), start.y() + 10 * MM)
    _mouse(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
    assert not canvas.is_dragging()
    assert window.image.height == round(first * MM)
    assert canvas.label_height() == pytest.approx(round(first * MM))


def test_render_error_blocks_print_and_shows_in_status(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: pytest.fail("darf nicht drucken"))
    panel = window.panel("text")
    panel.edit.setPlainText("Sehr langer Text")
    panel.auto.setChecked(False)
    panel.size.setValue(72)
    window.print_label()
    assert "höchstens" in window.result.text()
    assert window.result.property("state") == "error"
    assert window.print_action.isEnabled()
    panel.auto.setChecked(True)
    window.render_now()
    assert panel.error.isHidden()
    assert window.result.text() == ""


def test_render_success_keeps_print_result(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: {"outcome": "printed", "did_print": True})
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    window.render_now()
    assert window.result.text() == "Gedruckt ✓"


def test_printer_detection_error_at_startup(qtbot, monkeypatch):
    def broken():
        raise OSError("kaputt")

    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", broken)
    win = MainWindow()
    qtbot.addWidget(win)
    assert "unbekannt" in win.printer_status.text()


def test_busy_printer_message(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.brother_busy", lambda: True)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "belegt" in window.result.text()


def test_app_identity_sets_icon_and_desktop_name(qapp):
    from labelwerk.gui.app import apply_identity
    apply_identity(qapp)
    assert qapp.desktopFileName() == "labelwerk"
    assert not qapp.windowIcon().isNull()


def test_window_title_and_app_name_use_app_name(window, qapp):
    from labelwerk.desktop import APP_NAME
    from labelwerk.gui.app import apply_identity
    apply_identity(qapp)
    assert window.windowTitle() == APP_NAME
    assert qapp.applicationName() == APP_NAME


def test_theme_arrows_resolve_to_existing_files():
    import re
    from pathlib import Path
    theme = load_theme()
    assert "@THEME@" not in theme
    urls = [u.strip('"') for u in re.findall(r"url\(([^)]+)\)", theme)]
    assert urls and all(Path(u).exists() for u in urls)


def test_number_fields_keep_text_clear_of_frame(window):
    from PySide6.QtWidgets import QAbstractSpinBox
    from labelwerk.gui.settings_dialog import SettingsDialog
    from labelwerk.settings import Settings
    dialog = SettingsDialog(Settings())
    spins = window.findChildren(QAbstractSpinBox) + dialog.findChildren(QAbstractSpinBox)
    assert len(spins) >= 6
    assert all(s.lineEdit().textMargins().left() >= 8 for s in spins)


def test_theme_urls_are_quoted():
    import re
    assert all(u.startswith('"') for u in re.findall(r"url\(([^)]+)\)", load_theme()))


def test_toolbar_buttons_have_equal_space_above_and_below(qtbot, qapp):
    """Abstand Knopf ↔ Leistenrand oben gleich unten (gemessen an dunklen Pixelzeilen)."""
    from PySide6.QtWidgets import QToolBar
    from labelwerk.settings import Settings
    qapp.setStyleSheet(load_theme())
    try:
        win = MainWindow(settings=Settings(check_media_on_start=False))
        qtbot.addWidget(win)
        win.show()
        toolbar = win.findChild(QToolBar)
        img = toolbar.grab().toImage()
        x = toolbar.widgetForAction(win.tool_actions["text"]).geometry().center().x()
        dark = [y for y in range(img.height()) if img.pixelColor(x, y).lightness() < 80]
        bands, current = [], [dark[0]]
        for y in dark[1:]:
            if y == current[-1] + 1:
                current.append(y)
            else:
                bands.append(current)
                current = [y]
        bands.append(current)
        top_gap = bands[0][0]
        bottom_gap = bands[-1][0] - bands[-2][-1] - 1
        assert top_gap == bottom_gap
    finally:
        qapp.setStyleSheet("")
```

`tests/test_cli.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
import pytest
from PIL import Image

from labelwerk.cli import main


def test_preview_writes_png_without_printer(tmp_path):
    out = tmp_path / "vorschau.png"
    rc = main(["print", "Hallo", "-l", "62", "--preview", str(out)])
    assert rc == 0
    assert out.exists()


def test_missing_printer_gives_friendly_error(monkeypatch, capsys):
    def not_found(**kwargs):
        raise FileNotFoundError(kwargs["printer_identifier"])
    monkeypatch.setattr("labelwerk.printer.send", not_found)
    rc = main(["print", "Hallo", "-l", "62", "-p", "file:///nonexistent/lp9"])
    assert rc == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_auto_printer_without_device_gives_friendly_error(monkeypatch, capsys):
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: None)
    monkeypatch.setattr("labelwerk.cli.brother_busy", lambda: False)
    rc = main(["print", "Hallo", "-l", "62"])
    assert rc == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_auto_printer_with_pyusb_uses_usb_discovery(monkeypatch):
    monkeypatch.setattr("labelwerk.cli.find_brother_usb", lambda: "usb://0x04f9:0x20c0")
    sent = {}
    def fake_print(img, label, **kw):
        sent.update(kw)
        return {"outcome": "printed", "did_print": True}
    monkeypatch.setattr("labelwerk.cli.prn.print_image", fake_print)
    rc = main(["print", "Hallo", "-l", "62", "-b", "pyusb"])
    assert rc == 0
    assert sent["printer"] == "usb://0x04f9:0x20c0"


def test_auto_printer_with_network_asks_for_address(capsys):
    rc = main(["print", "Hallo", "-l", "62", "-b", "network"])
    assert rc == 2
    assert "tcp://" in capsys.readouterr().err


def test_print_error_gives_friendly_message(monkeypatch, capsys):
    from labelwerk.printer import PrintError
    def fail(*a, **kw):
        raise PrintError("Eingelegte Rolle passt nicht")
    monkeypatch.setattr("labelwerk.cli.prn.print_image", fail)
    rc = main(["print", "Hallo", "-l", "62", "-p", "file:///dev/usb/lp0"])
    assert rc == 2
    assert "Rolle passt nicht" in capsys.readouterr().err


def test_unknown_label_gives_friendly_error(capsys):
    rc = main(["print", "Hallo", "-l", "99", "--preview", "x.png"])
    assert rc == 2
    assert "Unbekanntes Etikett" in capsys.readouterr().err


def test_font_size_too_large_gives_friendly_error(capsys):
    rc = main(["print", "Sehr langer Text", "-l", "29", "-s", "48", "--preview", "x.png"])
    assert rc == 2
    assert "passt nicht" in capsys.readouterr().err


def _png(tmp_path, w_mm=40, h_mm=20):
    path = tmp_path / "motiv.png"
    Image.new("L", (round(w_mm * 300 / 25.4), round(h_mm * 300 / 25.4)), 0).save(path)
    return path


def test_print_file_preview_reports_size_in_mm(tmp_path, capsys):
    out = tmp_path / "vorschau.png"
    rc = main(["print-file", str(_png(tmp_path)), "-l", "62", "--preview", str(out)])
    assert rc == 0
    assert out.exists()
    assert "58,9 × 22,0 mm" in capsys.readouterr().out


def test_print_file_sends_image_in_label_width(tmp_path, monkeypatch):
    sent = {}
    def fake_print(img, label, **kw):
        sent["size"] = img.size
        return {"outcome": "printed", "did_print": True}
    monkeypatch.setattr("labelwerk.cli.prn.print_image", fake_print)
    rc = main(["print-file", str(_png(tmp_path)), "-l", "62", "-p", "file:///dev/usb/lp0"])
    assert rc == 0
    assert sent["size"][0] == 696


def test_print_file_unsupported_type(tmp_path, capsys):
    path = tmp_path / "notiz.txt"
    path.write_text("x")
    rc = main(["print-file", str(path), "--preview", str(tmp_path / "x.png")])
    assert rc == 2
    assert "nicht unterstützt" in capsys.readouterr().err


def test_print_file_missing_file(tmp_path, capsys):
    rc = main(["print-file", str(tmp_path / "fehlt.pdf"), "--preview", str(tmp_path / "x.png")])
    assert rc == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_print_file_too_large_suggests_fit(tmp_path, capsys):
    rc = main(["print-file", str(_png(tmp_path, 120, 70)), "--preview", str(tmp_path / "x.png")])
    assert rc == 2
    assert "--fit" in capsys.readouterr().err


def test_corrupt_file_gives_friendly_error(tmp_path, capsys):
    path = tmp_path / "kaputt.pdf"
    path.write_bytes(b"kein pdf")
    rc = main(["print-file", str(path), "--preview", str(tmp_path / "o.png")])
    assert rc == 2
    assert "kann nicht gelesen werden" in capsys.readouterr().err


def test_preview_into_missing_directory_gives_friendly_error(tmp_path, capsys):
    rc = main(["print", "Hallo", "--preview", str(tmp_path / "nodir" / "o.png")])
    assert rc == 2
    assert "Vorschau kann nicht gespeichert werden" in capsys.readouterr().err


def test_preview_with_unknown_extension_gives_friendly_error(tmp_path, capsys):
    rc = main(["print-file", str(_png(tmp_path)), "--preview", str(tmp_path / "o.txt")])
    assert rc == 2
    assert "Vorschau kann nicht gespeichert werden" in capsys.readouterr().err


def test_print_file_rotate_0_with_fit(tmp_path, capsys):
    out = tmp_path / "vorschau.png"
    rc = main(["print-file", str(_png(tmp_path, 90, 47)), "-l", "62", "--rotate", "0", "--fit",
               "--preview", str(out)])
    assert rc == 0
    assert "58,9 × 32,8 mm" in capsys.readouterr().out


def test_busy_printer_gives_specific_hint(monkeypatch, capsys):
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: None)
    monkeypatch.setattr("labelwerk.cli.brother_busy", lambda: True)
    rc = main(["print", "Hallo", "-l", "62"])
    assert rc == 2
    assert "von einem anderen Programm belegt" in capsys.readouterr().err


def test_install_desktop_uses_xdg_data_home(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    rc = main(["install-desktop"])
    assert rc == 0
    assert (tmp_path / "applications" / "labelwerk.desktop").exists()
    assert "labelwerk.desktop" in capsys.readouterr().out
    assert main(["install-desktop", "--remove"]) == 0
    assert not (tmp_path / "applications" / "labelwerk.desktop").exists()


def _write_settings(**values):
    import json
    import os
    from pathlib import Path
    path = Path(os.environ["XDG_CONFIG_HOME"]) / "labelwerk" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values))


def test_default_label_comes_from_settings(tmp_path, capsys):
    _write_settings(label_id="62x29")
    rc = main(["print", "Hallo", "--preview", str(tmp_path / "v.png")])
    assert rc == 0
    assert "58,9 × 22,9 mm" in capsys.readouterr().out


def _preview(tmp_path, *args):
    out = tmp_path / "v.png"
    assert main(["print", "Hallo Welt", *args, "--preview", str(out)]) == 0
    return Image.open(out).convert("RGB").tobytes()


def _expected(orientation="vertical", margin=1.0):
    from labelwerk.document import Document, TextObject
    from labelwerk.render import render_document
    doc = Document("62", orientation=orientation, margin_mm=margin, objects=[TextObject("Hallo Welt")])
    return render_document(doc).convert("RGB").tobytes()


def test_default_orientation_comes_from_settings(tmp_path):
    _write_settings(orientation="horizontal")
    assert _preview(tmp_path) == _expected("horizontal")


def test_orientation_option_overrides_settings(tmp_path):
    _write_settings(orientation="horizontal")
    assert _preview(tmp_path, "--orientation", "vertical") == _expected("vertical")


def test_margin_option(tmp_path):
    assert _preview(tmp_path, "--margin", "5") == _expected(margin=5.0)


def test_broken_settings_warn_but_work(tmp_path, capsys):
    import os
    from pathlib import Path
    path = Path(os.environ["XDG_CONFIG_HOME"]) / "labelwerk" / "settings.json"
    path.parent.mkdir(parents=True)
    path.write_text("{kaputt")
    assert main(["print", "Hallo", "--preview", str(tmp_path / "v.png")]) == 0
    assert "nicht lesbar" in capsys.readouterr().err


def test_media_command_shows_loaded_roll(monkeypatch, capsys):
    from labelwerk.media import Media
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: "file:///dev/usb/lp0")
    monkeypatch.setattr("labelwerk.cli.read_media", lambda printer: Media(62, 0, "endless"))
    assert main(["media"]) == 0
    assert "Eingelegt: 62 mm endlos (Etikett 62)" in capsys.readouterr().out


def test_media_command_error(monkeypatch, capsys):
    from labelwerk.media import MediaError
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: "file:///dev/usb/lp0")

    def fail(printer):
        raise MediaError("Keine Antwort vom Drucker auf die Statusabfrage.")
    monkeypatch.setattr("labelwerk.cli.read_media", fail)
    assert main(["media"]) == 2
    assert "Keine Antwort" in capsys.readouterr().err


def test_media_command_without_printer(monkeypatch, capsys):
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: None)
    monkeypatch.setattr("labelwerk.cli.brother_busy", lambda: False)
    assert main(["media"]) == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_font_size_auto_overrides_saved_size(tmp_path):
    from labelwerk.document import Document, TextObject
    from labelwerk.render import render_document
    _write_settings(font_size=80)
    expected = render_document(Document("62", objects=[TextObject("Hallo Welt", size_pt=None)]))
    assert _preview(tmp_path, "-s", "auto") == expected.convert("RGB").tobytes()


def test_font_size_option_beats_settings(tmp_path):
    from labelwerk.document import Document, TextObject
    from labelwerk.render import render_document
    _write_settings(font_size=80)
    expected = render_document(Document("62", objects=[TextObject("Hallo Welt", size_pt=24)]))
    assert _preview(tmp_path, "-s", "24") == expected.convert("RGB").tobytes()


@pytest.mark.parametrize("value", ["3", "101", "abc", "1.5"])
def test_font_size_invalid_is_argparse_error(value, capsys):
    with pytest.raises(SystemExit) as e:
        main(["print", "X", "-s", value])
    assert e.value.code == 2
    assert "Schriftgröße" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["25", "-1", "nan", "inf", "abc"])
def test_margin_invalid_is_argparse_error(value, capsys):
    with pytest.raises(SystemExit) as e:
        main(["print", "X", f"--margin={value}"])
    assert e.value.code == 2
    assert "Rand" in capsys.readouterr().err
```

`tests/test_document.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
from labelwerk.document import Document, TextObject
from labelwerk.render import render_document, render_text


def test_empty_document():
    assert Document().is_empty()
    assert Document(objects=[TextObject("")]).is_empty()
    assert Document(objects=[TextObject("  \n ")]).is_empty()
    assert not Document(objects=[TextObject("Hallo")]).is_empty()


def test_render_document_equals_render_text():
    doc = Document("62", objects=[TextObject("Hallo\nWelt")])
    assert render_document(doc).tobytes() == render_text("Hallo\nWelt", "62").tobytes()


def test_fixed_length_sets_height():
    doc = Document("62", length_mm=50, objects=[TextObject("Hallo")])
    assert render_document(doc).height == 591


def test_length_is_clamped_to_model_limits():
    assert render_document(Document("62", length_mm=5, objects=[TextObject("A")])).height == 150
    assert render_document(Document("62", length_mm=2000, objects=[TextObject("A")])).height == 11811


def test_short_auto_length_is_raised_to_minimum():
    assert render_document(Document("62", objects=[TextObject(".")])).height == 150


def test_too_tall_text_for_fixed_length_raises():
    import pytest
    from labelwerk.render import TextTooLarge
    doc = Document("62", length_mm=15, objects=[TextObject("A\nB\nC", size_pt=24)])
    with pytest.raises(TextTooLarge):
        render_document(doc)


def test_length_is_ignored_for_die_cut():
    doc = Document("62x29", length_mm=50, objects=[TextObject("Hallo")])
    assert render_document(doc).size == (696, 271)


def test_empty_document_renders_blank_label():
    img = render_document(Document("62"))
    assert img.convert("L").getextrema() == (255, 255)


def _ink(img):
    return img.convert("L").point(lambda v: 255 if v < 128 else 0)


def test_horizontal_endless_prints_across_full_width_and_grows_with_text():
    short = render_document(Document("62", orientation="horizontal", objects=[TextObject("Hi")]))
    long = render_document(Document("62", orientation="horizontal",
                                    objects=[TextObject("Max Mustermann")]))
    assert short.width == long.width == 696
    assert long.height > short.height


def test_horizontal_text_reads_along_the_tape():
    img = render_document(Document("62", orientation="horizontal",
                                   objects=[TextObject("Hallo\n.", size_pt=36)]))
    reading = img.rotate(90, expand=True)              # zurück in Leserichtung
    ink = _ink(reading)
    top = ink.crop((0, 0, reading.width, reading.height // 2)).histogram()[255]
    bottom = ink.crop((0, reading.height // 2, reading.width, reading.height)).histogram()[255]
    assert top > 3 * bottom                             # „Hallo“ oben, kleiner Punkt unten


def test_horizontal_auto_font_matches_vertical():
    def ink_height(orientation):
        img = render_document(Document("62", orientation=orientation, objects=[TextObject("Hallo")]))
        reading = img.rotate(90, expand=True) if orientation == "horizontal" else img
        box = _ink(reading).getbbox()
        return box[3] - box[1]
    assert ink_height("horizontal") == ink_height("vertical")   # gleiche Obergrenze


def test_horizontal_fixed_length():
    doc = Document("62", length_mm=50, orientation="horizontal", objects=[TextObject("Hallo")])
    assert render_document(doc).size == (696, 591)


def test_horizontal_die_cut_keeps_print_size():
    doc = Document("62x29", orientation="horizontal", objects=[TextObject("Hallo")])
    assert render_document(doc).size == (696, 271)


def test_margin_extends_auto_length():
    def height(margin):
        doc = Document("62", margin_mm=margin, objects=[TextObject("A", size_pt=48)])
        return render_document(doc).height
    assert height(5) - height(1) == 2 * (59 - 12)        # 5 mm = 59 Punkte, 1 mm = 12


def test_margin_is_clamped_to_20_mm():
    def height(margin):
        doc = Document("62", margin_mm=margin, objects=[TextObject("A", size_pt=48)])
        return render_document(doc).height
    assert height(50) == height(20)
    assert height(-3) == height(0)


def test_unknown_orientation_raises():
    import pytest
    with pytest.raises(ValueError, match="Ausrichtung"):
        render_document(Document("62", orientation="schräg", objects=[TextObject("A")]))


def test_horizontal_render_is_fast_enough_for_live_preview():
    import time
    doc = Document("62", orientation="horizontal",
                   objects=[TextObject("Max Mustermann\nMusterstr. 5\n12345 Musterstadt")])
    render_document(doc)                      # Aufwärmen (Schrift laden)
    start = time.perf_counter()
    render_document(doc)
    assert time.perf_counter() - start < 0.5


def _ink_bbox(img):
    from PIL import ImageOps
    return ImageOps.invert(img.convert("L")).getbbox()


def test_margin_larger_than_fixed_length_is_limited():
    img = render_document(Document("62", length_mm=10, margin_mm=20, objects=[TextObject("A")]))
    assert img.height == 150
    left, top, right, bottom = _ink_bbox(img)
    assert top > 0 and bottom < img.height
    assert bottom - top >= 20                 # nicht auf Mindestschrift geschrumpft


def test_margin_larger_than_die_cut_label_is_limited():
    img = render_document(Document("62x29", margin_mm=20, objects=[TextObject("A")]))
    assert img.size == (696, 271)
    box = _ink_bbox(img)
    assert box is not None and box[3] - box[1] >= 20
```

`tests/test_render.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
import pytest

from labelwerk.render import TextTooLarge, render_text


def test_endless_label_uses_full_printable_width():
    img = render_text("Hallo", "62")
    assert img.width == 696


def test_die_cut_label_matches_exact_size():
    img = render_text("Hallo", "62x29")
    assert img.size == (696, 271)


def test_multiline_text_makes_endless_label_longer():
    one = render_text("A", "62", size_pt=29)
    two = render_text("A\nB", "62", size_pt=29)
    assert two.height > one.height


def test_long_text_is_shrunk_to_fit_width():
    img = render_text("Sehr langer Text, der niemals passt", "29")
    assert img.width == 306
    # rechter Rand bleibt weiß -> nichts abgeschnitten
    right_edge = img.crop((img.width - 2, 0, img.width, img.height)).convert("L")
    assert right_edge.getextrema()[0] == 255


def test_fixed_font_size_too_large_raises_with_max_size():
    with pytest.raises(TextTooLarge, match=r"Schriftgröße 48 pt .*höchstens \d+ pt") as exc:
        render_text("Sehr langer Text", "29", size_pt=48)
    assert isinstance(exc.value, ValueError)
    render_text("Sehr langer Text", "29", size_pt=exc.value.max_pt)  # passt


def test_fixed_font_size_is_not_shrunk():
    small = render_text("A", "62", size_pt=24)
    large = render_text("A", "62", size_pt=72)
    assert large.height > small.height
```

`tests/test_rich_text.py` – **anlegen** (vollständiger Inhalt):

```python
"""Zeichenweise Formatierung im Kern (Etappe 3a)."""
import pytest
from PIL import Image, ImageDraw

from labelwerk import fonts
from labelwerk.document import Document, Paragraph, Span, TextObject
from labelwerk.render import TextTooLarge, font_warnings, render_document

DEJAVU_BOLD = fonts.resolve(None, True, False).path


def _ink(img):
    return img.convert("L").point(lambda v: 255 if v < 128 else 0)


def _old_render(text: str, size: int | None = None) -> Image.Image:
    """Der Algorithmus vor Etappe 3a (Pillow multiline_text, zentriert), Etikett 62 vertikal."""
    def box(font):
        probe = ImageDraw.Draw(Image.new("1", (1, 1)))
        return tuple(round(v) for v in probe.multiline_textbbox((0, 0), text, font=font,
                                                                 align="center"))

    def fits(s):
        l, t, r, b = box(fonts.load(DEJAVU_BOLD, s))
        return r - l <= 696 - 24 and b - t <= 11811 - 24

    start = size or max(10, 696 // 5)
    best = start if fits(start) else max(s for s in range(8, start) if fits(s))
    font = fonts.load(DEJAVU_BOLD, best)
    l, t, r, b = box(font)
    height = min(max(b - t + 24, 150), 11811)
    img = Image.new("RGB", (696, height), "white")
    ImageDraw.Draw(img).multiline_text(((696 - (r - l)) // 2 - l, (height - (b - t)) // 2 - t),
                                       text, fill="black", font=font, align="center")
    return img


@pytest.mark.parametrize("text", ["Hallo", "X1 -K3\nKlemme 24V", "Sehr langer Text der schrumpft",
                                  "", "A\n\nB"])
def test_plain_text_is_pixel_identical_to_before(text):
    assert render_document(Document("62", objects=[TextObject(text)])).tobytes() == \
        _old_render(text).tobytes()


def test_plain_text_with_fixed_size_is_pixel_identical_to_before():
    new = render_document(Document("62", objects=[TextObject("A\nB", size_pt=48)]))
    assert new.tobytes() == _old_render("A\nB", 200).tobytes()


def test_mixed_sizes_share_one_baseline():
    obj = TextObject([Paragraph([Span("H", size_pt=10), Span("H", size_pt=30)], "left")],
                     size_pt=20)
    # beide „H“ haben keine Unterlänge: gleiche Unterkante = gemeinsame Grundlinie
    h_boxes = _letter_boxes(_ink(render_document(Document("62", objects=[obj]))))
    assert len(h_boxes) == 2
    assert abs(h_boxes[0][3] - h_boxes[1][3]) <= 1
    assert (h_boxes[1][3] - h_boxes[1][1]) > 2 * (h_boxes[0][3] - h_boxes[0][1])


def _letter_boxes(ink):
    """Tintenboxen getrennter Buchstaben (spaltenweise getrennt)."""
    cols = [x for x in range(ink.width) if ink.crop((x, 0, x + 1, ink.height)).getbbox()]
    groups, current = [], [cols[0]]
    for x in cols[1:]:
        if x == current[-1] + 1:
            current.append(x)
        else:
            groups.append(current)
            current = [x]
    groups.append(current)
    boxes = []
    for g in groups:
        _, top, _, bottom = ink.crop((g[0], 0, g[-1] + 1, ink.height)).getbbox()
        boxes.append((g[0], top, g[-1] + 1, bottom))
    return boxes


def _line_boxes(ink):
    """Tintenboxen der Zeilen (an leeren Pixelzeilen getrennt)."""
    rows = [y for y in range(ink.height) if ink.crop((0, y, ink.width, y + 1)).getbbox()]
    groups, current = [], [rows[0]]
    for y in rows[1:]:
        if y == current[-1] + 1:
            current.append(y)
        else:
            groups.append(current)
            current = [y]
    groups.append(current)
    boxes = []
    for g in groups:
        l, _, r, _ = ink.crop((0, g[0], ink.width, g[-1] + 1)).getbbox()
        boxes.append((l, g[0], r, g[-1] + 1))
    return boxes


def _line_edges(img, align):
    obj = TextObject.plain("Kurz\nDeutlich laengere Zeile", size_pt=12, align=align)
    top, bottom = _line_boxes(_ink(render_document(Document("62", objects=[obj]))))
    return top, bottom


def test_left_aligned_lines_share_left_edge():
    top, bottom = _line_edges(None, "left")
    assert abs(top[0] - bottom[0]) <= 3
    assert top[2] < bottom[2] - 50


def test_right_aligned_lines_share_right_edge():
    top, bottom = _line_edges(None, "right")
    assert abs(top[2] - bottom[2]) <= 3
    assert top[0] > bottom[0] + 50


def test_justify_spreads_words_to_block_width():
    obj = TextObject([Paragraph([Span("ein zwei drei")], "justify"),
                      Paragraph([Span("eine laengere Zeile")], "left")], size_pt=12)
    top, bottom = _line_boxes(_ink(render_document(Document("62", objects=[obj]))))
    assert abs(top[0] - bottom[0]) <= 3 and abs(top[2] - bottom[2]) <= 6


def test_underline_draws_below_baseline():
    plain = _ink(render_document(Document("62", objects=[TextObject.plain("ma", size_pt=40)])))
    under = _ink(render_document(Document("62", objects=[TextObject.plain("ma", size_pt=40,
                                                                          underline=True)])))
    assert under.getbbox()[3] > plain.getbbox()[3]


def test_italic_without_real_italic_is_slanted():
    upright = render_document(Document("62", objects=[TextObject.plain("I", size_pt=40)]))
    slanted = render_document(Document("62", objects=[TextObject.plain("I", size_pt=40,
                                                                       italic=True)]))
    assert upright.tobytes() != slanted.tobytes()
    a, b = _ink(upright).getbbox(), _ink(slanted).getbbox()
    assert (b[2] - b[0]) > (a[2] - a[0])          # geschert = breiter


def test_regular_and_bold_differ():
    bold = render_document(Document("62", objects=[TextObject.plain("Hallo", size_pt=30)]))
    regular = render_document(Document("62", objects=[TextObject.plain("Hallo", size_pt=30,
                                                                       bold=False)]))
    assert bold.tobytes() != regular.tobytes()


def test_auto_size_keeps_ratios():
    obj = TextObject([Paragraph([Span("H", size_pt=8)], "left"),
                      Paragraph([Span("H", size_pt=16)], "left")])
    top, bottom = _line_boxes(_ink(render_document(Document("62", objects=[obj]))))
    ratio = (bottom[3] - bottom[1]) / (top[3] - top[1])
    assert 1.8 < ratio < 2.2


def test_fixed_size_too_large_reports_pt():
    with pytest.raises(TextTooLarge, match=r"bei Schriftgröße 60 pt \(höchstens \d+ pt\)"):
        render_document(Document("29", objects=[TextObject.plain("Langer Text", size_pt=60)]))


def test_unknown_alignment_raises():
    with pytest.raises(ValueError, match="Textposition"):
        render_document(Document("62", objects=[TextObject.plain("A", align="mittig")]))


def test_font_warnings_for_unknown_family():
    doc = Document("62", objects=[TextObject.plain("A", family="GibtsGarNicht 4711")])
    warnings = font_warnings(doc)
    assert len(warnings) == 1 and "GibtsGarNicht 4711" in warnings[0]
    assert font_warnings(Document("62", objects=[TextObject("A")])) == []


def test_text_property_and_plain_roundtrip():
    obj = TextObject.plain("Zeile 1\nZeile 2", align="left")
    assert obj.text == "Zeile 1\nZeile 2"
    assert [p.align for p in obj.paragraphs] == ["left", "left"]
```

`tests/test_settings.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
import json

import pytest

from labelwerk.settings import Settings, load_settings, new_document, save_settings, settings_path


def test_defaults_match_todays_behavior(tmp_path):
    s = load_settings(tmp_path / "fehlt.json")
    assert (s.label_id, s.orientation, s.margin_mm, s.font_size_pt) == ("62", "vertical", 1.0, None)
    assert s.check_media_on_start is True and s.start_zoom == 200
    assert s.warnings == []


def test_path_follows_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert settings_path() == tmp_path / "labelwerk" / "settings.json"


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "cfg" / "settings.json"
    save_settings(Settings(label_id="62x29", orientation="horizontal", margin_mm=3,
                           font_size_pt=19, check_media_on_start=False, start_zoom=150), path)
    s = load_settings(path)
    assert (s.label_id, s.orientation, s.margin_mm, s.font_size_pt) == ("62x29", "horizontal", 3.0, 19)
    assert (s.check_media_on_start, s.start_zoom) == (False, 150)
    assert "warnings" not in json.loads(path.read_text())


def test_invalid_values_fall_back_with_warning(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"label_id": "999", "orientation": "schräg", "margin_mm": 99,
                                "font_size_pt": "groß", "start_zoom": True, "unbekannt": 1,
                                "check_media_on_start": False}))
    s = load_settings(path)
    assert (s.label_id, s.orientation, s.margin_mm, s.font_size_pt, s.start_zoom) == \
        ("62", "vertical", 1.0, None, 200)
    assert s.check_media_on_start is False                 # gültige Werte bleiben
    assert len(s.warnings) == 5
    assert all("ungültig" in w for w in s.warnings)


def test_broken_json_gives_defaults_and_warning(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{kaputt")
    s = load_settings(path)
    assert s.label_id == "62"
    assert len(s.warnings) == 1 and "nicht lesbar" in s.warnings[0]


def test_save_error_has_clear_message(tmp_path):
    blocker = tmp_path / "datei"
    blocker.write_text("x")                                # Ordner kann nicht angelegt werden
    with pytest.raises(OSError, match="nicht gespeichert"):
        save_settings(Settings(), blocker / "settings.json")


def test_new_document_uses_settings():
    doc = new_document(Settings(label_id="62x29", orientation="horizontal", margin_mm=3, font_size_pt=19))
    assert (doc.label_id, doc.orientation, doc.margin_mm) == ("62x29", "horizontal", 3)
    assert doc.objects[0].size_pt == 19 and doc.objects[0].text == ""


import pytest


@pytest.mark.parametrize("label", ["102", "62red"])
def test_label_not_in_model_list_falls_back(tmp_path, label):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"label_id": label}))
    s = load_settings(path)
    assert s.label_id == "62"
    assert len(s.warnings) == 1


def test_unreadable_config_dir_gives_warning_not_exception(tmp_path, monkeypatch):
    from pathlib import Path

    def denied(self, *a, **kw):
        raise PermissionError(13, "Keine Berechtigung")
    monkeypatch.setattr(Path, "exists", denied)
    monkeypatch.setattr(Path, "read_text", denied)
    s = load_settings(tmp_path / "settings.json")
    assert s == Settings()
    assert any("nicht lesbar" in w for w in s.warnings)


def test_old_font_size_in_dots_is_converted_to_pt(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"font_size": 80}))
    s = load_settings(path)
    assert s.font_size_pt == 19
    assert any("umgerechnet" in w for w in s.warnings)
    save_settings(s, path)
    assert "font_size" not in json.loads(path.read_text()) and \
        json.loads(path.read_text())["font_size_pt"] == 19
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Tests schlagen fehl (z. B. `ImportError: cannot import name 'Paragraph'`, `TypeError` bei `size_pt=`).

- [ ] **Step 3: Implementierung**

`src/labelwerk/cli.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
"""Kommandozeile: labelwerk labels | print "Text" | print-file datei.pdf | media | install-desktop"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from . import desktop
from . import printer as prn
from .detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp, find_brother_usb
from .files import crop, fit_to_label, load_file
from .document import MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
from .labels import format_mm, labels_for_model
from .media import MediaError, label_for_media, read_media
from .render import render_document
from .settings import load_settings


def _font_size(value: str) -> float | None:
    """'auto' (= None) oder Größe in pt, 4–100."""
    if value.lower() == "auto":
        return None
    try:
        size = float(value.replace(",", "."))
    except ValueError:
        size = 0.0
    if not MIN_PT <= size <= MAX_PT:
        raise argparse.ArgumentTypeError("Schriftgröße: 'auto' oder 4–100 (pt)")
    return size


def _margin(value: str) -> float:
    try:
        mm = float(value)
    except ValueError:
        mm = float("nan")
    if not 0 <= mm <= MAX_MARGIN_MM:      # nan fällt hier ebenfalls durch
        raise argparse.ArgumentTypeError(f"Rand: Zahl von 0 bis {MAX_MARGIN_MM:g} mm")
    return mm


def _add_output_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-l", "--label", help="Etikett, z. B. 62 (Standard aus den Einstellungen)")
    p.add_argument("-p", "--printer", default="auto",
                   help="auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP")
    p.add_argument("-b", "--backend", default=prn.DEFAULT_BACKEND,
                   choices=["linux_kernel", "pyusb", "network"])
    p.add_argument("--no-cut", action="store_true")
    p.add_argument("--preview", metavar="PNG", help="nur Vorschau speichern, nicht drucken")


_UNSET = object()   # -s nicht angegeben (None bedeutet „auto“)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=desktop.APP_NAME)
    p.add_argument("-m", "--model", default=prn.DEFAULT_MODEL)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("labels", help="Etiketten für das Modell auflisten")

    pr = sub.add_parser("print", help="Text drucken")
    pr.add_argument("text", help="Text, Zeilenumbruch mit \\n")
    pr.add_argument("-s", "--font-size", type=_font_size, default=_UNSET, metavar="GRÖSSE",
                    help="'auto' oder 8–400 (Standard aus den Einstellungen)")
    pr.add_argument("--font", help="Pfad zu einer .ttf-Datei")
    pr.add_argument("--orientation", choices=ORIENTATIONS,
                    help="vertical: Text quer zum Band, horizontal: längs (Standard aus den Einstellungen)")
    pr.add_argument("--margin", type=_margin, metavar="MM",
                    help="Rand in Bandlaufrichtung in mm (Standard aus den Einstellungen)")
    _add_output_options(pr)

    pf = sub.add_parser("print-file", help="PDF/Bild 1:1 drucken")
    pf.add_argument("file", help="PDF, PNG oder JPG")
    pf.add_argument("--page", type=int, default=1, help="PDF-Seite (Standard 1)")
    pf.add_argument("--fit", action="store_true",
                    help="verkleinern, falls zu groß (Codes evtl. nicht mehr lesbar)")
    pf.add_argument("--rotate", default="auto", choices=["auto", "0", "90", "180", "270"],
                    help="auto (Standard: nur drehen wenn nötig) oder Grad im Uhrzeigersinn")
    _add_output_options(pf)

    sub.add_parser("media", help="eingelegte Rolle vom Drucker abfragen (druckt nichts)")

    di = sub.add_parser("install-desktop", help="labelwerk-gui im Starter (Super-Taste) eintragen")
    di.add_argument("--remove", action="store_true", help="Eintrag und Icon wieder entfernen")
    return p


_HARDWARE_HINT = "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb'"
_NOT_DETECTED = {
    "linux_kernel": f"{PRINTER_NOT_FOUND}\nManuell angeben mit -p file:///dev/usb/lpN",
    "pyusb": "Brother-Drucker per USB (pyusb) nicht gefunden.\n"
             f"{_HARDWARE_HINT}, Zugriff auf den USB-Bus (udev-Regel).\n"
             "Manuell angeben mit -p usb://0x04f9:0xPID",
    "network": "Netzwerkdrucker werden nicht automatisch erkannt.\n"
               "Adresse angeben mit -p tcp://IP",
}


def _detect_printer(backend: str) -> str | None:
    if backend == "linux_kernel":
        return find_brother_lp()
    if backend == "pyusb":
        return find_brother_usb()
    return None


def _make_image(args: argparse.Namespace) -> Image.Image:
    if args.cmd == "print-file":
        img = crop(load_file(args.file, page=args.page))
        rotate = args.rotate if args.rotate == "auto" else int(args.rotate)
        return fit_to_label(img, args.label, fit=args.fit, model=args.model, rotate=rotate)
    text = args.text.replace("\\n", "\n")
    doc = Document(args.label, orientation=args.orientation, margin_mm=args.margin,
                   objects=[TextObject.plain(text, size_pt=args.font_size, font_path=args.font)])
    return render_document(doc, args.model)


def _send(img: Image.Image, args: argparse.Namespace) -> int:
    if args.printer == "auto":
        args.printer = _detect_printer(args.backend)
        if args.printer is None:
            busy = args.backend == "linux_kernel" and brother_busy()
            print(BUSY_MESSAGE if busy else _NOT_DETECTED[args.backend], file=sys.stderr)
            return 2

    try:
        status = prn.print_image(img, args.label, model=args.model, printer=args.printer,
                                 backend=args.backend, cut=not args.no_cut)
    except prn.PrintError as e:
        print(e, file=sys.stderr)
        return 2
    ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
    print(f"Status: {status.get('outcome')}")
    return 0 if ok else 1


def _show_media() -> int:
    printer = find_brother_lp()
    if printer is None:
        print(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND, file=sys.stderr)
        return 2
    try:
        media = read_media(printer)
    except MediaError as e:
        print(e, file=sys.stderr)
        return 2
    label = label_for_media(media)
    hint = f" (Etikett {label})" if label else " (kein passendes Etikett)" if media.kind != "none" else ""
    print(f"Eingelegt: {media.describe()}{hint}")
    return 0


def _apply_settings(args: argparse.Namespace) -> None:
    """Nicht angegebene Optionen mit den Standardwerten aus den Einstellungen füllen."""
    settings = load_settings(model=args.model)
    for warning in settings.warnings:
        print(warning, file=sys.stderr)
    if hasattr(args, "label") and args.label is None:
        args.label = settings.label_id
    if args.cmd == "print":
        args.orientation = args.orientation or settings.orientation
        args.margin = settings.margin_mm if args.margin is None else args.margin
        if args.font_size is _UNSET:
            args.font_size = settings.font_size_pt


def _install_desktop(remove: bool) -> int:
    if remove:
        removed = desktop.uninstall()
        print("\n".join(f"Entfernt: {p}" for p in removed) or "Nichts zu entfernen.")
        return 0
    gui_exe = Path(sys.executable).parent / "labelwerk-gui"
    try:
        paths = desktop.install(gui_exe)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    for path in paths:
        print(f"Installiert: {path}")
    print("labelwerk erscheint jetzt im Starter (ggf. kurz warten oder neu anmelden).")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.cmd == "labels":
        for lbl in labels_for_model(args.model):
            size = f"{lbl.width}x{lbl.height}" if lbl.height else f"{lbl.width}"
            print(f"{lbl.id:<10} {size:<10} {lbl.description}")
        return 0

    if args.cmd == "install-desktop":
        return _install_desktop(args.remove)
    if args.cmd == "media":
        return _show_media()

    _apply_settings(args)

    try:
        img = _make_image(args)
    except (ValueError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        return 2

    if args.preview:
        try:
            img.save(args.preview)
        except (OSError, ValueError) as e:
            print(f"Vorschau kann nicht gespeichert werden: {args.preview} ({e})", file=sys.stderr)
            return 2
        print(f"Vorschau: {args.preview} ({format_mm(img.width)} × {format_mm(img.height)} mm)")
        return 0

    return _send(img, args)


if __name__ == "__main__":
    sys.exit(main())
```

`src/labelwerk/document.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
"""Etikett-Dokument: Etikett und Liste von Objekten (UI-unabhängig, JSON-tauglich)."""
from __future__ import annotations

from dataclasses import dataclass, field

ORIENTATIONS = ("vertical", "horizontal")
ALIGNMENTS = ("left", "center", "right", "justify")
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
    size_pt: float | None = None    # Grundgröße; None = automatisch („feste Rahmengröße“)
    font_path: str | None = None    # feste TTF-Datei für Stücke ohne Familie (CLI --font)

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
```

`src/labelwerk/gui/panels/text.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
"""Panel „Text“: Inhalt und Schriftgröße des Textobjekts."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit

from ...document import MAX_PT, MIN_PT, Document, TextObject
from ..widgets import SpinBox
from . import Panel


class TextPanel(Panel):
    def __init__(self, doc: Document):
        super().__init__(doc, "Text")
        if not doc.objects:
            doc.objects.append(TextObject(""))

        self.section("Inhalt")
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("Text eingeben …")
        self.layout_.addWidget(self.edit)

        self.section("Schriftgröße (pt)")
        row = QHBoxLayout()
        self.auto = QCheckBox("Automatisch")
        self.size = SpinBox()
        self.size.setRange(int(MIN_PT), int(MAX_PT))
        self.size.setValue(19)
        row.addWidget(self.auto)
        row.addWidget(self.size)
        self.layout_.addLayout(row)

        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        self.layout_.addWidget(self.error)
        self.layout_.addStretch()

        self.refresh()
        self.edit.textChanged.connect(self._apply)
        self.auto.toggled.connect(self._apply)
        self.size.valueChanged.connect(self._apply)

    @property
    def obj(self) -> TextObject:
        return self.doc.objects[0]

    def _apply(self) -> None:
        size = None if self.auto.isChecked() else self.size.value()
        self.doc.objects[0] = TextObject.plain(self.edit.toPlainText(), size_pt=size,
                                               font_path=self.obj.font_path)
        self.size.setEnabled(not self.auto.isChecked())
        self.changed.emit()

    def refresh(self) -> None:
        for w in (self.edit, self.auto, self.size):
            w.blockSignals(True)
        if self.edit.toPlainText() != self.obj.text:
            self.edit.setPlainText(self.obj.text)
        self.auto.setChecked(self.obj.size_pt is None)
        if self.obj.size_pt is not None:
            self.size.setValue(round(self.obj.size_pt))
        self.size.setEnabled(not self.auto.isChecked())
        for w in (self.edit, self.auto, self.size):
            w.blockSignals(False)

    def show_error(self, message: str | None) -> None:
        self.error.setText(message or "")
        self.error.setVisible(bool(message))
```

`src/labelwerk/gui/settings_dialog.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
"""Dialog „Einstellungen“: Standardwerte für neue Etiketten, Drucker, Ansicht.

Neue Einstellung = Feld in settings.Settings + eine Zeile im passenden Abschnitt hier.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QVBoxLayout)

from ..document import MAX_MARGIN_MM, MAX_PT, MIN_PT
from ..labels import labels_for_model
from ..printer import DEFAULT_MODEL
from ..settings import Settings, save_settings
from .widgets import DoubleSpinBox, SpinBox


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, path: str | Path | None = None,
                 model: str = DEFAULT_MODEL, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.path = path
        self.saved: Settings | None = None
        layout = QVBoxLayout(self)

        form = self._section(layout, "Neues Etikett")
        self.label = QComboBox()
        for lbl in labels_for_model(model):
            self.label.addItem(lbl.description, lbl.id)
        self.label.setCurrentIndex(max(0, self.label.findData(settings.label_id)))
        form.addRow("Etikett", self.label)
        self.orientation = QComboBox()
        self.orientation.addItem("Horizontal (Text längs zum Band)", "horizontal")
        self.orientation.addItem("Vertikal (Text quer zum Band)", "vertical")
        self.orientation.setCurrentIndex(self.orientation.findData(settings.orientation))
        form.addRow("Ausrichtung", self.orientation)
        self.margin = DoubleSpinBox()
        self.margin.setSuffix(" mm")
        self.margin.setDecimals(1)
        self.margin.setSingleStep(0.5)
        self.margin.setRange(0.0, MAX_MARGIN_MM)
        self.margin.setValue(settings.margin_mm)
        form.addRow("Ränder", self.margin)
        row = QHBoxLayout()
        self.font_auto = QCheckBox("Automatisch")
        self.font_size = SpinBox()
        self.font_size.setRange(int(MIN_PT), int(MAX_PT))
        self.font_size.setSuffix(" pt")
        self.font_size.setValue(round(settings.font_size_pt or 19))
        self.font_auto.setChecked(settings.font_size_pt is None)
        self.font_size.setEnabled(settings.font_size_pt is not None)
        self.font_auto.toggled.connect(lambda auto: self.font_size.setEnabled(not auto))
        row.addWidget(self.font_auto)
        row.addWidget(self.font_size)
        form.addRow("Schriftgröße", row)

        form = self._section(layout, "Drucker")
        self.check_media = QCheckBox("Rolle beim Start und beim Einschalten prüfen")
        self.check_media.setChecked(settings.check_media_on_start)
        form.addRow(self.check_media)

        form = self._section(layout, "Ansicht")
        self.zoom = SpinBox()
        self.zoom.setSuffix(" %")
        self.zoom.setRange(25, 400)
        self.zoom.setSingleStep(10)
        self.zoom.setValue(settings.start_zoom)
        form.addRow("Startzoom", self.zoom)

        hint = QLabel("Gilt für neue Etiketten bzw. ab dem nächsten Start.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _section(self, layout: QVBoxLayout, title: str) -> QFormLayout:
        box = QGroupBox(title.upper())
        form = QFormLayout(box)
        layout.addWidget(box)
        return form

    def values(self) -> Settings:
        return Settings(
            label_id=self.label.currentData(),
            orientation=self.orientation.currentData(),
            margin_mm=self.margin.value(),
            font_size_pt=None if self.font_auto.isChecked() else self.font_size.value(),
            check_media_on_start=self.check_media.isChecked(),
            start_zoom=self.zoom.value(),
        )

    def accept(self) -> None:
        settings = self.values()
        try:
            save_settings(settings, self.path)
        except OSError as e:
            self.error.setText(str(e))
            self.error.show()
            return                                   # Dialog bleibt offen
        self.saved = settings
        super().accept()
```

`src/labelwerk/render.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
"""Rendert Etiketteninhalte als Bild in exakter Druckauflösung.

Der Zeilensatz verallgemeinert Pillows ``multiline_text`` auf formatierte Textstücke:
gleicher Zeilenabstand (Unterkante von „A“ + 4 Punkte), gleiche Ausrichtungsrechnung –
reiner Text sieht dadurch pixelgleich aus wie früher.
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from . import fonts
from .document import (ALIGNMENTS, MAX_MARGIN_MM, ORIENTATIONS, Document, Paragraph, Span,
                       TextObject)
from .labels import DPI, get_label, length_limits

MARGIN = 12            # Punkte, ca. 1 mm
PT = DPI / 72          # Druckpunkte pro typografischem Punkt
REF_PT = 12.0          # Bezugsgröße für automatische Skalierung von Stücken mit eigener Größe
MIN_DOTS = 8           # kleinste Schrift in Druckpunkten
_LINE_GAP = 4          # wie Pillow multiline_text
_SLANT = 0.2           # Ersatzkursive: Scherung, wenn die Schrift keine echte Kursive hat


class TextTooLarge(ValueError):
    """Text passt bei fester Schriftgröße nicht aufs Etikett."""

    def __init__(self, size_pt: float, max_pt: float, label_id: str):
        super().__init__(f"Text passt nicht auf Etikett {label_id!r} bei Schriftgröße "
                         f"{_fmt_pt(size_pt)} pt (höchstens {_fmt_pt(max_pt)} pt).")
        self.size_pt, self.max_pt = size_pt, max_pt


def _fmt_pt(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def render_text(text: str, label_id: str, size_pt: float | None = None,
                font_path: str | None = None) -> Image.Image:
    """Reinen Text rendern (Standardformatierung)."""
    obj = TextObject.plain(text, size_pt=size_pt, font_path=font_path)
    return render_document(Document(label_id, objects=[obj]))


def font_warnings(doc: Document) -> list[str]:
    """Hinweise zu ersetzten Schriften (je Familie einmal)."""
    warnings: list[str] = []
    for obj in doc.objects:
        for para in obj.paragraphs:
            for span in para.spans:
                if span.family is None or (obj.font_path and span.family is None):
                    continue
                match = fonts.resolve(span.family, span.bold, span.italic)
                text = f"Schrift „{span.family}“ nicht gefunden – ersetzt durch „{match.family}“."
                if match.family.casefold() != span.family.casefold() and text not in warnings:
                    warnings.append(text)
    return warnings


def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
    """Dokument als Druckbild in exakter Auflösung (Vorschau = Druck).

    Gerendert wird in Leserichtung; bei Ausrichtung „horizontal“ (Text längs zum Band)
    wird das Bild danach für den Drucker um 90° im Uhrzeigersinn gedreht – so kommt der
    Textanfang zuerst aus dem Drucker und das veränderliche Ende liegt in Leserichtung rechts.
    """
    if doc.orientation not in ORIENTATIONS:
        raise ValueError(f"Unbekannte Ausrichtung {doc.orientation!r} – erlaubt: horizontal, vertical")
    horizontal = doc.orientation == "horizontal"
    label = get_label(doc.label_id)
    min_len, max_len = length_limits(model)
    margin = round(min(max(doc.margin_mm, 0.0), MAX_MARGIN_MM) * DPI / 25.4)
    across = label.width                      # quer zum Band (fest)
    feed = label.height                       # in Bandlaufrichtung; None = automatisch
    if feed is None and doc.length_mm is not None:
        feed = min(max(round(doc.length_mm * DPI / 25.4), min_len), max_len)
    if feed is not None:                      # feste Länge: Rand darf nicht alles aufbrauchen
        margin = min(margin, max(0, (feed - 2 * MARGIN) // 2))
    obj = doc.objects[0] if doc.objects else TextObject("")
    for para in obj.paragraphs:
        if para.align not in ALIGNMENTS:
            raise ValueError(f"Unbekannte Textposition {para.align!r} – erlaubt: links, zentriert, "
                             "rechts, Blocksatz (left, center, right, justify)")

    across_room = across - 2 * MARGIN
    feed_room = (feed if feed else max_len) - 2 * margin
    max_w, max_h = (feed_room, across_room) if horizontal else (across_room, feed_room)
    base = _fit(obj, max(10, across // 5), max_w, max_h, doc.label_id)
    lines = _shape(obj, base)
    l, t, r, b = _block_box(lines)

    text_w, text_h = r - l, b - t
    if feed is None:
        feed = min(max((text_w if horizontal else text_h) + 2 * margin, min_len), max_len)
    width, height = (feed, across) if horizontal else (across, feed)
    img = Image.new("RGB", (width, height), "white")
    _draw(img, lines, (width - text_w) // 2 - l, (height - text_h) // 2 - t)
    return img.rotate(-90, expand=True) if horizontal else img


# --- Schriftgrößen ----------------------------------------------------------
def _span_dots(obj: TextObject, span: Span, base: int) -> int:
    """Größe eines Stücks in Druckpunkten bei Grundgröße ``base`` (gemeinsam skaliert)."""
    if span.size_pt is None:
        return base
    ref = obj.size_pt or REF_PT
    return max(1, round(base * span.size_pt / ref))


def _fit(obj: TextObject, auto_start: int, max_w: int, max_h: int, label_id: str) -> int:
    """Grundgröße in Druckpunkten: fest, oder größte passende ≤ auto_start (Halbierung)."""
    def fits(base: int) -> bool:
        l, t, r, b = _block_box(_shape(obj, base, mode="1"))
        return (r - l) <= max_w and (b - t) <= max_h

    start = round(obj.size_pt * PT) if obj.size_pt else auto_start
    if fits(start):
        return start
    best, lo, hi = None, MIN_DOTS, start - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if fits(mid):
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    if obj.size_pt is not None:
        max_pt = int((best if best else MIN_DOTS) / PT)
        raise TextTooLarge(obj.size_pt, max_pt, label_id)
    return best if best else MIN_DOTS          # passt nicht einmal klein – kleinste Größe zeigen


# --- Zeilensatz ---------------------------------------------------------------
@dataclass
class _Piece:
    text: str
    font: object
    dots: int
    underline: bool
    slant: bool                # Ersatzkursive
    x: float = 0.0             # links, relativ zum Block
    y: float = 0.0             # Oberkante (Ascender-Linie), relativ zum Block


def _font_for(obj: TextObject, span: Span, dots: int):
    if span.family is None and obj.font_path:
        return fonts.load(obj.font_path, dots), False
    match = fonts.resolve(span.family, span.bold, span.italic)
    return fonts.load(match.path, dots), span.italic and not match.italic


def _shape(obj: TextObject, base: int, mode: str = "L") -> list[list[_Piece]]:
    """Stücke mit Position im Block (mode „1“ zum Messen, „L“ zum Zeichnen – wie Pillow)."""
    rows = []
    for para in obj.paragraphs:
        spans = para.spans or [Span("")]
        pieces = []
        for span in spans:
            dots = _span_dots(obj, span, base)
            font, slant = _font_for(obj, span, dots)
            pieces.append(_Piece(span.text, font, dots, span.underline, slant))
        rows.append((para, pieces))

    widths = [sum(p.font.getlength(p.text, mode) for p in pieces) for _, pieces in rows]
    max_width = max(widths, default=0)
    top = 0.0
    lines = []
    for (para, pieces), width in zip(rows, widths):
        ascent = max(p.font.getmetrics()[0] for p in pieces)
        spacing = max(p.font.getbbox("A", mode)[3] for p in pieces) + _LINE_GAP
        if para.align == "justify":
            pieces = _justify(pieces, max_width, mode)
        else:
            x = {"left": 0.0, "center": (max_width - width) / 2.0,
                 "right": max_width - width}[para.align]
            for p in pieces:
                p.x = x
                x += p.font.getlength(p.text, mode)
        for p in pieces:
            p.y = top + ascent - p.font.getmetrics()[0]    # gemeinsame Grundlinie
        lines.append(pieces)
        top += spacing
    return lines


def _justify(pieces: list[_Piece], max_width: float, mode: str) -> list[_Piece]:
    """Wortabstände dehnen, bis die Zeile die Blockbreite füllt (ein Wort: linksbündig)."""
    words: list[_Piece] = []
    gaps_before: list[bool] = []
    for p in pieces:
        for i, part in enumerate(p.text.split(" ")):
            words.append(_Piece(part, p.font, p.dots, p.underline, p.slant))
            gaps_before.append(i > 0)
    gaps = sum(gaps_before[1:])
    used = sum(w.font.getlength(w.text, mode) for w in words)
    extra = (max_width - used) / gaps if gaps else 0.0
    x = 0.0
    for word, gap in zip(words, gaps_before):
        if gap and word is not words[0]:
            x += extra
        word.x = x
        x += word.font.getlength(word.text, mode)
    return words


def _block_box(lines: list[list[_Piece]]) -> tuple[int, int, int, int]:
    """Tintenbox des Blocks (wie Pillow multiline_textbbox), auf ganze Punkte gerundet."""
    boxes = []
    for pieces in lines:
        for p in pieces:
            l, t, r, b = p.font.getbbox(p.text, "1", anchor="la")
            if p.underline:
                b = max(b, p.font.getmetrics()[0] + _underline(p.dots)[0] + _underline(p.dots)[1])
            if p.slant:
                r += _SLANT * p.font.getmetrics()[0]
            boxes.append((p.x + l, p.y + t, p.x + r, p.y + b))
    if not boxes:
        return (0, 0, 0, 0)
    return tuple(round(v) for v in (min(b[0] for b in boxes), min(b[1] for b in boxes),
                                    max(b[2] for b in boxes), max(b[3] for b in boxes)))


def _underline(dots: int) -> tuple[int, int]:
    """(Abstand unter der Grundlinie, Stärke) in Druckpunkten."""
    return max(1, round(dots * 0.10)), max(1, round(dots * 0.06))


def _draw(img: Image.Image, lines: list[list[_Piece]], x0: int, y0: int) -> None:
    draw = ImageDraw.Draw(img)
    for pieces in lines:
        for p in pieces:
            x, y = x0 + p.x, y0 + p.y
            if p.slant:
                _draw_slanted(img, p, x, y)
            else:
                draw.text((x, y), p.text, fill="black", font=p.font, anchor="la")
            if p.underline and p.text:
                offset, thickness = _underline(p.dots)
                base_y = round(y + p.font.getmetrics()[0] + offset)
                length = p.font.getlength(p.text)
                draw.rectangle((round(x), base_y, round(x + length), base_y + thickness - 1),
                               fill="black")


def _draw_slanted(img: Image.Image, p: _Piece, x: float, y: float) -> None:
    """Ersatzkursive: Stück einzeln zeichnen und um die Grundlinie nach rechts scheren."""
    ascent, descent = p.font.getmetrics()
    width = int(p.font.getlength(p.text) + _SLANT * ascent) + 2
    mask = Image.new("L", (width, ascent + descent), 0)
    ImageDraw.Draw(mask).text((0, 0), p.text, fill=255, font=p.font, anchor="la")
    sheared = mask.transform(mask.size, Image.Transform.AFFINE,
                             (1, _SLANT, -_SLANT * ascent, 0, 1, 0), Image.Resampling.BICUBIC)
    img.paste((0, 0, 0), (round(x), round(y)), sheared)
```

`src/labelwerk/settings.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
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
```

- [ ] **Step 4: Grün prüfen** – Run: `.venv/bin/python -m pytest -q` (dreimal) – Expected: `235 passed`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/cli.py src/labelwerk/document.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/settings_dialog.py src/labelwerk/render.py src/labelwerk/settings.py tests/gui/test_gui_papier.py tests/gui/test_gui_settings.py tests/gui/test_gui_window.py tests/test_cli.py tests/test_document.py tests/test_render.py tests/test_rich_text.py tests/test_settings.py
git commit -m "Text: Abschnitte mit eigener Formatierung, Zeilensatz auf gemeinsamer Grundlinie, Größen in pt

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: CLI – Formatoptionen, `labelwerk fonts`, Standard-Schriftart

**Files:**
- Modify: `src/labelwerk/cli.py`
- Modify: `src/labelwerk/settings.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_settings.py`

**Interfaces / Produces:** `print --align left|center|right|justify --font-family NAME --bold/--no-bold --italic --underline`; Befehl `fonts`; Ersatzschrift-Hinweise auf stderr; `Settings.font_family` (Standard `DEFAULT_FAMILY`), `new_document` setzt die Familie.

- [ ] **Step 1: Tests schreiben bzw. anpassen**

An `tests/test_cli.py` **anhängen**:

```python
def _rich_expected(**plain):
    from labelwerk.document import Document, TextObject
    from labelwerk.render import render_document
    obj = TextObject.plain("Hallo\nWelt", **plain)
    return render_document(Document("62", objects=[obj])).convert("RGB").tobytes()


def _rich_preview(tmp_path, *args):
    out = tmp_path / "v.png"
    assert main(["print", "Hallo\\nWelt", *args, "--preview", str(out)]) == 0
    return Image.open(out).convert("RGB").tobytes()


def test_align_option(tmp_path):
    assert _rich_preview(tmp_path, "--align", "left") == _rich_expected(align="left")


def test_style_options(tmp_path):
    assert _rich_preview(tmp_path, "--no-bold", "--italic", "--underline") == \
        _rich_expected(bold=False, italic=True, underline=True)


def test_font_family_option_and_warning(tmp_path, capsys):
    assert _rich_preview(tmp_path, "--font-family", "GibtsGarNicht 4711") == \
        _rich_expected(family="GibtsGarNicht 4711")
    assert "GibtsGarNicht 4711" in capsys.readouterr().err


def test_default_font_family_from_settings(tmp_path):
    _write_settings(font_family="DejaVu Sans")
    assert _rich_preview(tmp_path) == _rich_expected()


def test_fonts_command_lists_families(capsys):
    assert main(["fonts"]) == 0
    assert "DejaVu Sans" in capsys.readouterr().out.splitlines()


def test_align_invalid_is_argparse_error():
    with pytest.raises(SystemExit) as e:
        main(["print", "X", "--align", "mittig"])
    assert e.value.code == 2
```

An `tests/test_settings.py` **anhängen**:

```python
def test_font_family_setting(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"font_family": "Liberation Sans"}))
    assert load_settings(path).font_family == "Liberation Sans"
    path.write_text(json.dumps({"font_family": 42}))
    s = load_settings(path)
    assert s.font_family == "DejaVu Sans" and s.warnings


def test_new_document_uses_font_family():
    doc = new_document(Settings(font_family="Liberation Sans"))
    assert doc.objects[0].paragraphs[0].spans[0].family == "Liberation Sans"
    assert new_document(Settings()).objects[0].paragraphs[0].spans[0].family is None
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen CLI-/Einstellungs-Tests schlagen fehl (`unrecognized arguments: --align`, `invalid choice: 'fonts'`, fehlendes `font_family`).

- [ ] **Step 3: Implementierung**

`src/labelwerk/cli.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
"""Kommandozeile: labelwerk labels | print "Text" | print-file datei.pdf | media | install-desktop"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from . import desktop
from . import printer as prn
from .detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp, find_brother_usb
from .files import crop, fit_to_label, load_file
from .fonts import DEFAULT_FAMILY, families
from .document import ALIGNMENTS, MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
from .labels import format_mm, labels_for_model
from .media import MediaError, label_for_media, read_media
from .render import font_warnings, render_document
from .settings import load_settings


def _font_size(value: str) -> float | None:
    """'auto' (= None) oder Größe in pt, 4–100."""
    if value.lower() == "auto":
        return None
    try:
        size = float(value.replace(",", "."))
    except ValueError:
        size = 0.0
    if not MIN_PT <= size <= MAX_PT:
        raise argparse.ArgumentTypeError("Schriftgröße: 'auto' oder 4–100 (pt)")
    return size


def _margin(value: str) -> float:
    try:
        mm = float(value)
    except ValueError:
        mm = float("nan")
    if not 0 <= mm <= MAX_MARGIN_MM:      # nan fällt hier ebenfalls durch
        raise argparse.ArgumentTypeError(f"Rand: Zahl von 0 bis {MAX_MARGIN_MM:g} mm")
    return mm


def _add_output_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-l", "--label", help="Etikett, z. B. 62 (Standard aus den Einstellungen)")
    p.add_argument("-p", "--printer", default="auto",
                   help="auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP")
    p.add_argument("-b", "--backend", default=prn.DEFAULT_BACKEND,
                   choices=["linux_kernel", "pyusb", "network"])
    p.add_argument("--no-cut", action="store_true")
    p.add_argument("--preview", metavar="PNG", help="nur Vorschau speichern, nicht drucken")


_UNSET = object()   # -s nicht angegeben (None bedeutet „auto“)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=desktop.APP_NAME)
    p.add_argument("-m", "--model", default=prn.DEFAULT_MODEL)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("labels", help="Etiketten für das Modell auflisten")

    pr = sub.add_parser("print", help="Text drucken")
    pr.add_argument("text", help="Text, Zeilenumbruch mit \\n")
    pr.add_argument("-s", "--font-size", type=_font_size, default=_UNSET, metavar="PT",
                    help="'auto' oder 4–100 pt (Standard aus den Einstellungen)")
    pr.add_argument("--font", help="Pfad zu einer .ttf-Datei")
    pr.add_argument("--font-family", metavar="NAME",
                    help="Schriftfamilie, z. B. 'Liberation Sans' (siehe 'labelwerk fonts')")
    pr.add_argument("--align", choices=ALIGNMENTS, default="center",
                    help="Textposition: left, center (Standard), right, justify")
    pr.add_argument("--bold", action=argparse.BooleanOptionalAction, default=True,
                    help="fett (Standard) bzw. --no-bold")
    pr.add_argument("--italic", action="store_true", help="kursiv")
    pr.add_argument("--underline", action="store_true", help="unterstrichen")
    pr.add_argument("--orientation", choices=ORIENTATIONS,
                    help="vertical: Text quer zum Band, horizontal: längs (Standard aus den Einstellungen)")
    pr.add_argument("--margin", type=_margin, metavar="MM",
                    help="Rand in Bandlaufrichtung in mm (Standard aus den Einstellungen)")
    _add_output_options(pr)

    pf = sub.add_parser("print-file", help="PDF/Bild 1:1 drucken")
    pf.add_argument("file", help="PDF, PNG oder JPG")
    pf.add_argument("--page", type=int, default=1, help="PDF-Seite (Standard 1)")
    pf.add_argument("--fit", action="store_true",
                    help="verkleinern, falls zu groß (Codes evtl. nicht mehr lesbar)")
    pf.add_argument("--rotate", default="auto", choices=["auto", "0", "90", "180", "270"],
                    help="auto (Standard: nur drehen wenn nötig) oder Grad im Uhrzeigersinn")
    _add_output_options(pf)

    sub.add_parser("media", help="eingelegte Rolle vom Drucker abfragen (druckt nichts)")
    sub.add_parser("fonts", help="installierte Schriftfamilien auflisten")

    di = sub.add_parser("install-desktop", help="labelwerk-gui im Starter (Super-Taste) eintragen")
    di.add_argument("--remove", action="store_true", help="Eintrag und Icon wieder entfernen")
    return p


_HARDWARE_HINT = "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb'"
_NOT_DETECTED = {
    "linux_kernel": f"{PRINTER_NOT_FOUND}\nManuell angeben mit -p file:///dev/usb/lpN",
    "pyusb": "Brother-Drucker per USB (pyusb) nicht gefunden.\n"
             f"{_HARDWARE_HINT}, Zugriff auf den USB-Bus (udev-Regel).\n"
             "Manuell angeben mit -p usb://0x04f9:0xPID",
    "network": "Netzwerkdrucker werden nicht automatisch erkannt.\n"
               "Adresse angeben mit -p tcp://IP",
}


def _detect_printer(backend: str) -> str | None:
    if backend == "linux_kernel":
        return find_brother_lp()
    if backend == "pyusb":
        return find_brother_usb()
    return None


def _make_image(args: argparse.Namespace) -> Image.Image:
    if args.cmd == "print-file":
        img = crop(load_file(args.file, page=args.page))
        rotate = args.rotate if args.rotate == "auto" else int(args.rotate)
        return fit_to_label(img, args.label, fit=args.fit, model=args.model, rotate=rotate)
    text = args.text.replace("\\n", "\n")
    obj = TextObject.plain(text, size_pt=args.font_size, align=args.align,
                           family=args.font_family, bold=args.bold, italic=args.italic,
                           underline=args.underline, font_path=args.font)
    doc = Document(args.label, orientation=args.orientation, margin_mm=args.margin, objects=[obj])
    for warning in font_warnings(doc):
        print(warning, file=sys.stderr)
    return render_document(doc, args.model)


def _send(img: Image.Image, args: argparse.Namespace) -> int:
    if args.printer == "auto":
        args.printer = _detect_printer(args.backend)
        if args.printer is None:
            busy = args.backend == "linux_kernel" and brother_busy()
            print(BUSY_MESSAGE if busy else _NOT_DETECTED[args.backend], file=sys.stderr)
            return 2

    try:
        status = prn.print_image(img, args.label, model=args.model, printer=args.printer,
                                 backend=args.backend, cut=not args.no_cut)
    except prn.PrintError as e:
        print(e, file=sys.stderr)
        return 2
    ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
    print(f"Status: {status.get('outcome')}")
    return 0 if ok else 1


def _show_media() -> int:
    printer = find_brother_lp()
    if printer is None:
        print(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND, file=sys.stderr)
        return 2
    try:
        media = read_media(printer)
    except MediaError as e:
        print(e, file=sys.stderr)
        return 2
    label = label_for_media(media)
    hint = f" (Etikett {label})" if label else " (kein passendes Etikett)" if media.kind != "none" else ""
    print(f"Eingelegt: {media.describe()}{hint}")
    return 0


def _apply_settings(args: argparse.Namespace) -> None:
    """Nicht angegebene Optionen mit den Standardwerten aus den Einstellungen füllen."""
    settings = load_settings(model=args.model)
    for warning in settings.warnings:
        print(warning, file=sys.stderr)
    if hasattr(args, "label") and args.label is None:
        args.label = settings.label_id
    if args.cmd == "print":
        args.orientation = args.orientation or settings.orientation
        args.margin = settings.margin_mm if args.margin is None else args.margin
        if args.font_size is _UNSET:
            args.font_size = settings.font_size_pt
        if args.font_family is None and settings.font_family != DEFAULT_FAMILY:
            args.font_family = settings.font_family


def _install_desktop(remove: bool) -> int:
    if remove:
        removed = desktop.uninstall()
        print("\n".join(f"Entfernt: {p}" for p in removed) or "Nichts zu entfernen.")
        return 0
    gui_exe = Path(sys.executable).parent / "labelwerk-gui"
    try:
        paths = desktop.install(gui_exe)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    for path in paths:
        print(f"Installiert: {path}")
    print("labelwerk erscheint jetzt im Starter (ggf. kurz warten oder neu anmelden).")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.cmd == "labels":
        for lbl in labels_for_model(args.model):
            size = f"{lbl.width}x{lbl.height}" if lbl.height else f"{lbl.width}"
            print(f"{lbl.id:<10} {size:<10} {lbl.description}")
        return 0

    if args.cmd == "install-desktop":
        return _install_desktop(args.remove)
    if args.cmd == "media":
        return _show_media()
    if args.cmd == "fonts":
        print("\n".join(families()))
        return 0

    _apply_settings(args)

    try:
        img = _make_image(args)
    except (ValueError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        return 2

    if args.preview:
        try:
            img.save(args.preview)
        except (OSError, ValueError) as e:
            print(f"Vorschau kann nicht gespeichert werden: {args.preview} ({e})", file=sys.stderr)
            return 2
        print(f"Vorschau: {args.preview} ({format_mm(img.width)} × {format_mm(img.height)} mm)")
        return 0

    return _send(img, args)


if __name__ == "__main__":
    sys.exit(main())
```

`src/labelwerk/settings.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
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
from .fonts import DEFAULT_FAMILY
from .labels import labels_for_model


@dataclass
class Settings:
    label_id: str = "62"
    orientation: str = "vertical"
    margin_mm: float = 1.0
    font_size_pt: float | None = None      # None = automatisch
    font_family: str = DEFAULT_FAMILY
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
        "font_family": lambda v: isinstance(v, str) and bool(v.strip()),
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
    family = None if settings.font_family == DEFAULT_FAMILY else settings.font_family
    return Document(label_id=settings.label_id, orientation=settings.orientation,
                    margin_mm=settings.margin_mm,
                    objects=[TextObject.plain("", size_pt=settings.font_size_pt, family=family)])
```

- [ ] **Step 4: Grün prüfen** – Run: `.venv/bin/python -m pytest -q` (dreimal) – Expected: `243 passed`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/cli.py src/labelwerk/settings.py tests/test_cli.py tests/test_settings.py
git commit -m "CLI: Ausrichtung, Schriftart, fett/kursiv/unterstrichen, Befehl fonts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: GUI – Rich-Text-Editor mit Formatleiste (P-touch-Aufbau)

**Files:**
- Modify: `src/labelwerk/document.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/gui/theme/rawblock.qss`
- Modify: `src/labelwerk/render.py`
- Modify: `tests/gui/test_gui_papier.py`
- Modify: `tests/gui/test_gui_settings.py`
- Create: `tests/gui/test_gui_text.py`
- Modify: `tests/gui/test_gui_window.py`
- Modify: `tests/test_rich_text.py`

**Interfaces / Produces:** `TextObject.fit` + `.auto` (Feste Rahmengröße mit Grundgröße als Bezug); Text-Panel: `edit` (PlainPasteEdit), `family` (QFontComboBox), `size` (editierbare QComboBox, pt), `grow`/`shrink`, `bold`/`italic`/`underline`, `align_buttons[left|center|right|justify]`, `fit`, `set_size_pt(pt)`, `to_text_object()`; eigenes Grundformat (`_base`), ohne Markierung wirkt Formatierung auf den ganzen Text; Einstellungsdialog mit `font_family`; Theme für Formatknöpfe.

- [ ] **Step 1: Tests schreiben bzw. anpassen**

`tests/gui/test_gui_papier.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import MM, Canvas
from labelwerk.gui.main_window import MainWindow
from labelwerk.labels import get_label
from labelwerk.render import render_document
from labelwerk.settings import Settings


@pytest.fixture
def window(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.panel("text").edit.setPlainText("Max Mustermann")
    win.render_now()
    return win


def test_orientation_switch_changes_document_and_preview(window):
    paper = window.panel("paper")
    assert paper.vertical.isChecked()
    paper.horizontal.setChecked(True)
    window.render_now()
    assert window.doc.orientation == "horizontal"
    assert window.image.tobytes() == render_document(window.doc).tobytes()


def test_margin_changes_document_and_length(window):
    paper = window.panel("paper")
    paper.horizontal.setChecked(True)
    window.render_now()
    before = window.image.height
    paper.margin.setValue(5.0)
    window.render_now()
    assert window.doc.margin_mm == 5.0
    assert window.image.height == before + 2 * (59 - 12)


def test_horizontal_view_shows_handle_right_of_label(window):
    window.panel("paper").horizontal.setChecked(True)
    window.render_now()
    canvas = window.canvas
    label_box = canvas.label_view_rect()
    handle = canvas.mapFromScene(canvas.handle.sceneBoundingRect().center())
    assert handle.x() > label_box.right()
    assert label_box.width() > label_box.height()          # Adresse liegt quer im Bild


def test_horizontal_caption_reads_length_first(qtbot):
    view = Canvas()
    qtbot.addWidget(view)
    doc = Document("62", length_mm=50, orientation="horizontal", objects=[TextObject("A")])
    view.set_document(get_label("62"), render_document(doc), "horizontal")
    assert view._caption == "50,0 × 62 mm"


def _mouse(view, kind, scene_point, buttons):
    pos = QPointF(view.mapFromScene(scene_point))
    event = QMouseEvent(kind, pos, QPointF(view.viewport().mapToGlobal(pos.toPoint())),
                        Qt.MouseButton.LeftButton if kind != QMouseEvent.Type.MouseMove
                        else Qt.MouseButton.NoButton,
                        buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), event)


def test_dragging_in_horizontal_view_sets_length(window):
    window.panel("paper").horizontal.setChecked(True)
    window.render_now()
    canvas = window.canvas
    start = canvas.handle.sceneBoundingRect().center()
    end = QPointF(start.x(), start.y() + 80.1 * MM - canvas.label_height())
    _mouse(canvas, QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseMove, end, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
    assert window.doc.length_mm == 80.0


def test_window_starts_with_settings(qtbot):
    settings = Settings(label_id="62x29", orientation="horizontal", margin_mm=3, font_size_pt=19,
                        start_zoom=150)
    win = MainWindow(settings=settings)
    qtbot.addWidget(win)
    assert (win.doc.label_id, win.doc.orientation, win.doc.margin_mm) == ("62x29", "horizontal", 3)
    assert win.panel("paper").horizontal.isChecked()
    assert win.panel("paper").margin.value() == 3.0
    assert not win.panel("text").fit.isChecked() and win.panel("text").size.currentText() == "19"
    assert win.canvas.zoom == 150


def test_settings_warnings_appear_in_status_bar(qtbot):
    win = MainWindow(settings=Settings(warnings=["Einstellung 'start_zoom' ungültig"]))
    qtbot.addWidget(win)
    assert "start_zoom" in win.result.text()
```

An `tests/gui/test_gui_settings.py` **anhängen**:

```python
def test_dialog_font_family_roundtrip(qtbot, tmp_path):
    from PySide6.QtGui import QFont
    path = tmp_path / "settings.json"
    dialog = SettingsDialog(Settings(font_family="Liberation Sans"), path=path)
    qtbot.addWidget(dialog)
    assert dialog.values().font_family == "Liberation Sans"
    dialog.font_family.setCurrentFont(QFont("DejaVu Sans"))
    dialog.accept()
    assert load_settings(path).font_family == "DejaVu Sans"
```

`tests/gui/test_gui_text.py` – **anlegen** (vollständiger Inhalt):

```python
import pytest
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QTextCursor

from labelwerk.gui.main_window import MainWindow
from labelwerk.render import render_document
from labelwerk.settings import Settings


@pytest.fixture
def window(qtbot):
    win = MainWindow(settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    return win


def _select(panel, start, end):
    cursor = panel.edit.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    panel.edit.setTextCursor(cursor)


def test_bold_on_selected_word_gives_three_spans(window):
    panel = window.panel("text")
    panel.edit.setPlainText("aaa bbb ccc")
    _select(panel, 0, 11)
    panel.bold.click()                      # alles normal …
    _select(panel, 4, 7)
    panel.bold.click()                      # … nur „bbb“ fett
    spans = window.doc.objects[0].paragraphs[0].spans
    assert [(s.text, s.bold) for s in spans] == [("aaa ", False), ("bbb", True), (" ccc", False)]


def test_format_without_selection_applies_to_whole_text(window):
    panel = window.panel("text")
    panel.edit.setPlainText("eins\nzwei")
    panel.italic.click()
    assert all(s.italic for p in window.doc.objects[0].paragraphs for s in p.spans)


def test_alignment_lands_in_selected_paragraph(window):
    panel = window.panel("text")
    panel.edit.setPlainText("eins\nzwei")
    _select(panel, 5, 7)                    # in „zwei“
    panel.align_buttons["left"].click()
    assert [p.align for p in window.doc.objects[0].paragraphs] == ["center", "left"]


def test_grow_changes_only_selection(window):
    panel = window.panel("text")
    panel.edit.setPlainText("klein gross")
    _select(panel, 6, 11)
    panel.grow.click()
    spans = window.doc.objects[0].paragraphs[0].spans
    assert spans[0].text == "klein " and spans[0].size_pt is None      # Grundgröße
    assert spans[1].text == "gross" and spans[1].size_pt == 20         # 19 → nächste Stufe 20


def test_size_entry_applies_pt(window):
    panel = window.panel("text")
    panel.edit.setPlainText("Hallo")
    panel.set_size_pt(36)
    assert window.doc.objects[0].size_pt == 36


def test_fit_toggle_switches_auto(window):
    panel = window.panel("text")
    panel.edit.setPlainText("Hallo")
    panel.fit.setChecked(False)
    assert not window.doc.objects[0].auto
    panel.fit.setChecked(True)
    assert window.doc.objects[0].auto


def test_buttons_follow_cursor(window):
    panel = window.panel("text")
    panel.edit.setPlainText("aaa bbb")
    _select(panel, 0, 7)
    panel.bold.click()                     # alles normal
    _select(panel, 4, 7)
    panel.bold.click()                     # „bbb“ fett
    cursor = panel.edit.textCursor()
    cursor.setPosition(2)
    panel.edit.setTextCursor(cursor)
    assert not panel.bold.isChecked()
    cursor.setPosition(6)
    panel.edit.setTextCursor(cursor)
    assert panel.bold.isChecked()


def test_paste_inserts_plain_text_only(window):
    panel = window.panel("text")
    mime = QMimeData()
    mime.setHtml("<b style='font-size:40pt'>Fremd</b>")
    mime.setText("Fremd")
    panel.edit.insertFromMimeData(mime)
    span = window.doc.objects[0].paragraphs[0].spans[0]
    assert span.text == "Fremd" and span.size_pt is None


def test_preview_matches_core_render(window):
    panel = window.panel("text")
    panel.edit.setPlainText("Max Mustermann\nMusterstr. 5")
    _select(panel, 0, 3)
    panel.underline.click()
    window.render_now()
    assert window.image.tobytes() == render_document(window.doc).tobytes()


def test_start_uses_settings_family_and_size(qtbot):
    win = MainWindow(settings=Settings(check_media_on_start=False, font_size_pt=24,
                                       font_family="Liberation Sans"))
    qtbot.addWidget(win)
    panel = win.panel("text")
    assert panel.size.currentText() == "24"
    assert panel.family.currentFont().family() == "Liberation Sans"
    assert not panel.fit.isChecked()


def test_unformatted_text_uses_base_format_not_widget_font(window):
    from labelwerk.gui.app import load_theme
    window.window().setStyleSheet(load_theme())          # Stylesheet setzt eine andere Widget-Schrift
    panel = window.panel("text")
    panel.edit.setPlainText("Max")
    span = window.doc.objects[0].paragraphs[0].spans[0]
    assert span.family is None and span.size_pt is None and span.bold
    assert panel.size.currentText() == "19"
    assert panel.family.currentFont().family() == "DejaVu Sans"
    window.render_now()
    assert window.panel("text").error.isHidden()


def test_partial_size_change_keeps_rest_at_base(window):
    panel = window.panel("text")
    panel.edit.setPlainText("Absender\nEmpfänger")
    _select(panel, 0, 8)
    panel.set_size_pt(7)
    paras = window.doc.objects[0].paragraphs
    assert paras[0].spans[0].size_pt == 7
    assert paras[1].spans[0].size_pt is None
    window.render_now()
    assert window.panel("text").error.isHidden()
```

`tests/gui/test_gui_window.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from labelwerk.gui.app import load_theme
from labelwerk.gui.canvas import MM
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.tools import TOOLS


@pytest.fixture
def window(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    return win


def test_theme_is_packaged():
    assert "QToolBar" in load_theme()


def test_registry_creates_button_and_panel_per_tool(window):
    assert list(window.tool_actions) == [tool.key for tool in TOOLS]
    assert window.panels.count() == len(TOOLS)
    window.tool_actions["text"].trigger()
    assert window.panels.currentWidget() is window.panel("text")


def test_typing_updates_preview(window, qtbot):
    before = window.image.tobytes()
    window.panel("text").edit.setPlainText("Hallo")
    qtbot.waitUntil(lambda: window.image.tobytes() != before, timeout=1000)


def test_too_large_font_shows_hint_in_text_panel(window):
    panel = window.panel("text")
    panel.edit.setPlainText("Sehr langer Text")
    panel.fit.setChecked(False)
    panel.set_size_pt(72)
    window.render_now()
    assert not panel.error.isHidden()
    assert "höchstens" in panel.error.text()


def test_changing_label_changes_preview_size(window):
    paper = window.panel("paper")
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    window.render_now()
    assert window.image.size == (696, 271)


def test_paper_panel_shows_length_only_for_endless(window):
    paper = window.panel("paper")
    assert not paper.length_box.isHidden() and paper.fixed_size.isHidden()
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    assert paper.length_box.isHidden()
    assert paper.fixed_size.text() == "62 × 29 mm · gestanzt"


def test_fixed_length_sets_preview_height(window):
    paper = window.panel("paper")
    paper.length_auto.setChecked(False)
    paper.length.setValue(50.0)
    window.render_now()
    assert window.image.height == round(50 * MM)


def _mouse(view, kind, scene_point, buttons):
    pos = QPointF(view.mapFromScene(scene_point))
    event = QMouseEvent(kind, pos, QPointF(view.viewport().mapToGlobal(pos.toPoint())),
                        Qt.MouseButton.LeftButton if kind != QMouseEvent.Type.MouseMove
                        else Qt.MouseButton.NoButton,
                        buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), event)


def _drag_handle(window, to_y):
    """Untere Schnittkante am Anfasser auf Szene-y to_y ziehen (Greifversatz bleibt erhalten)."""
    canvas = window.canvas
    start = canvas.handle.sceneBoundingRect().center()
    end = QPointF(start.x(), start.y() + to_y - canvas.label_height())
    _mouse(canvas, QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseMove, end, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)


def test_dragging_handle_sets_fixed_length(window):
    _drag_handle(window, 40.1 * MM)   # ±1 Pixel Rundung bleibt im 0,5-mm-Raster
    assert window.doc.length_mm == 40.0                   # Raster 0,5 mm
    paper = window.panel("paper")
    assert not paper.length_auto.isChecked()
    assert paper.length.value() == 40.0


def test_dragging_below_minimum_stops_at_12_7_mm(window):
    _drag_handle(window, 2 * MM)
    assert window.doc.length_mm == pytest.approx(12.7, abs=0.01)


def test_double_click_on_handle_resets_to_automatic(window):
    _drag_handle(window, 40 * MM)
    window.render_now()
    center = window.canvas.handle.sceneBoundingRect().center()
    _mouse(window.canvas, QMouseEvent.Type.MouseButtonDblClick, center, Qt.MouseButton.LeftButton)
    assert window.doc.length_mm is None
    assert window.panel("paper").length_auto.isChecked()


def test_print_success_shows_status_and_reenables_button(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")
    sent = {}

    def fake_print(image, label_id, **kw):
        sent["size"] = image.size
        return {"outcome": "printed", "did_print": True}

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image", fake_print)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert window.result.text() == "Gedruckt ✓"
    assert sent["size"][0] == 696


def test_print_error_is_shown(window, qtbot, monkeypatch):
    from labelwerk.printer import PrintError

    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")

    def fail(*a, **kw):
        raise PrintError("Eingelegte Rolle passt nicht zum Etikett '62'")

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image", fail)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "Rolle passt nicht" in window.result.text()


def test_no_printer_message(window, qtbot):
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "nicht gefunden" in window.result.text()


def test_empty_label_asks_and_cancel_does_not_print(window, monkeypatch):
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **kw: asked.append(a) or QMessageBox.StandardButton.Cancel)
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: pytest.fail("darf nicht drucken"))
    window.print_label()
    assert asked
    assert window.print_action.isEnabled()
    assert window.result.text() == ""


def test_detection_error_does_not_hang_button(window, qtbot, monkeypatch):
    def broken():
        raise OSError("kaputt")

    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp", broken)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "kaputt" in window.result.text()


def test_new_print_resets_result_state(window, qtbot, monkeypatch):
    from labelwerk.printer import PrintError

    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")

    def fail(*a, **kw):
        raise PrintError("kaputt")

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image", fail)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert window.result.property("state") == "error"

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: {"outcome": "printed", "did_print": True})
    window.print_label()
    assert window.result.property("state") == ""
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert window.result.property("state") == "ok"


def _press_move(window, dy_mm, kind=QMouseEvent.Type.MouseMove, start=None):
    canvas = window.canvas
    point = QPointF(start.x(), start.y() + dy_mm * MM)
    _mouse(canvas, kind, point, Qt.MouseButton.LeftButton)


def test_drag_without_motion_does_not_drift_and_renders_only_on_release(window, qtbot):
    canvas = window.canvas
    start = canvas.handle.sceneBoundingRect().center()
    height_before = canvas.label_height()
    _mouse(canvas, QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton)
    _press_move(window, 10, start=start)
    first = window.doc.length_mm
    qtbot.wait(300)   # früher: Render mitten im Ziehen verschob das Etikett unter dem Cursor
    assert canvas.label_height() == height_before
    _press_move(window, 10, start=start)
    assert window.doc.length_mm == first
    end = QPointF(start.x(), start.y() + 10 * MM)
    _mouse(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
    assert not canvas.is_dragging()
    assert window.image.height == round(first * MM)
    assert canvas.label_height() == pytest.approx(round(first * MM))


def test_render_error_blocks_print_and_shows_in_status(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: pytest.fail("darf nicht drucken"))
    panel = window.panel("text")
    panel.edit.setPlainText("Sehr langer Text")
    panel.fit.setChecked(False)
    panel.set_size_pt(72)
    window.print_label()
    assert "höchstens" in window.result.text()
    assert window.result.property("state") == "error"
    assert window.print_action.isEnabled()
    panel.fit.setChecked(True)
    window.render_now()
    assert panel.error.isHidden()
    assert window.result.text() == ""


def test_render_success_keeps_print_result(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: {"outcome": "printed", "did_print": True})
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    window.render_now()
    assert window.result.text() == "Gedruckt ✓"


def test_printer_detection_error_at_startup(qtbot, monkeypatch):
    def broken():
        raise OSError("kaputt")

    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", broken)
    win = MainWindow()
    qtbot.addWidget(win)
    assert "unbekannt" in win.printer_status.text()


def test_busy_printer_message(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.brother_busy", lambda: True)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "belegt" in window.result.text()


def test_app_identity_sets_icon_and_desktop_name(qapp):
    from labelwerk.gui.app import apply_identity
    apply_identity(qapp)
    assert qapp.desktopFileName() == "labelwerk"
    assert not qapp.windowIcon().isNull()


def test_window_title_and_app_name_use_app_name(window, qapp):
    from labelwerk.desktop import APP_NAME
    from labelwerk.gui.app import apply_identity
    apply_identity(qapp)
    assert window.windowTitle() == APP_NAME
    assert qapp.applicationName() == APP_NAME


def test_theme_arrows_resolve_to_existing_files():
    import re
    from pathlib import Path
    theme = load_theme()
    assert "@THEME@" not in theme
    urls = [u.strip('"') for u in re.findall(r"url\(([^)]+)\)", theme)]
    assert urls and all(Path(u).exists() for u in urls)


def test_number_fields_keep_text_clear_of_frame(window):
    from PySide6.QtWidgets import QAbstractSpinBox
    from labelwerk.gui.settings_dialog import SettingsDialog
    from labelwerk.settings import Settings
    dialog = SettingsDialog(Settings())
    spins = window.findChildren(QAbstractSpinBox) + dialog.findChildren(QAbstractSpinBox)
    assert len(spins) >= 5
    assert all(s.lineEdit().textMargins().left() >= 8 for s in spins)


def test_theme_urls_are_quoted():
    import re
    assert all(u.startswith('"') for u in re.findall(r"url\(([^)]+)\)", load_theme()))


def test_toolbar_buttons_have_equal_space_above_and_below(qtbot, qapp):
    """Abstand Knopf ↔ Leistenrand oben gleich unten (gemessen an dunklen Pixelzeilen)."""
    from PySide6.QtWidgets import QToolBar
    from labelwerk.settings import Settings
    qapp.setStyleSheet(load_theme())
    try:
        win = MainWindow(settings=Settings(check_media_on_start=False))
        qtbot.addWidget(win)
        win.show()
        toolbar = win.findChild(QToolBar)
        img = toolbar.grab().toImage()
        x = toolbar.widgetForAction(win.tool_actions["text"]).geometry().center().x()
        dark = [y for y in range(img.height()) if img.pixelColor(x, y).lightness() < 80]
        bands, current = [], [dark[0]]
        for y in dark[1:]:
            if y == current[-1] + 1:
                current.append(y)
            else:
                bands.append(current)
                current = [y]
        bands.append(current)
        top_gap = bands[0][0]
        bottom_gap = bands[-1][0] - bands[-2][-1] - 1
        assert top_gap == bottom_gap
    finally:
        qapp.setStyleSheet("")
```

An `tests/test_rich_text.py` **anhängen**:

```python
def test_fit_scales_relative_to_base_size():
    """Feste Rahmengröße mit Grundgröße 20 pt: ein 10-pt-Stück bleibt halb so groß."""
    obj = TextObject([Paragraph([Span("H", size_pt=10)], "left"),
                      Paragraph([Span("H")], "left")], size_pt=20, fit=True)
    top, bottom = _line_boxes(_ink(render_document(Document("62", objects=[obj]))))
    ratio = (bottom[3] - bottom[1]) / (top[3] - top[1])
    assert 1.8 < ratio < 2.2


def test_fit_never_raises_text_too_large():
    obj = TextObject.plain("Sehr langer Text", size_pt=60)
    obj.fit = True
    render_document(Document("29", objects=[obj]))          # schrumpft statt Fehler
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen GUI-Tests schlagen fehl (z. B. `AttributeError: 'TextPanel' object has no attribute 'fit'`).

- [ ] **Step 3: Implementierung**

`src/labelwerk/document.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
"""Etikett-Dokument: Etikett und Liste von Objekten (UI-unabhängig, JSON-tauglich)."""
from __future__ import annotations

from dataclasses import dataclass, field

ORIENTATIONS = ("vertical", "horizontal")
ALIGNMENTS = ("left", "center", "right", "justify")
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
```

`src/labelwerk/gui/panels/text.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
"""Panel „Text“: zeichenweise Formatierung wie im P-touch Editor.

Regel wie bei einem ausgewählten Textrahmen in P-touch: Ist nichts markiert, wirkt eine
Formatierung auf den ganzen Text; sonst nur auf die Markierung.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (QFont, QKeySequence, QShortcut, QTextCharFormat, QTextCursor, QTextFormat,
                           QTextOption)
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QHBoxLayout, QLabel,
                               QPushButton, QTextEdit)

from ...document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
from ...fonts import DEFAULT_FAMILY
from . import Panel

_P = QTextFormat.Property

SIZES_PT = (6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72)
DEFAULT_PT = 19
_ALIGN_TO_QT = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                "right": Qt.AlignmentFlag.AlignRight, "justify": Qt.AlignmentFlag.AlignJustify}


class PlainPasteEdit(QTextEdit):
    """Rich-Text-Editor, der aus der Zwischenablage nur reinen Text übernimmt."""

    def insertFromMimeData(self, source) -> None:
        if source.hasText():
            self.textCursor().insertText(source.text())


def _button(text: str, tip: str, checkable: bool = True) -> QPushButton:
    button = QPushButton(text)
    button.setToolTip(tip)
    button.setCheckable(checkable)
    button.setObjectName("formatButton")
    return button


class TextPanel(Panel):
    def __init__(self, doc: Document):
        super().__init__(doc, "Text")
        if not doc.objects:
            doc.objects.append(TextObject(""))
        self._updating = False
        # Grundformat: gilt für alles, was nicht ausdrücklich formatiert ist (nicht Qts Widget-Schrift)
        self._base = {"family": DEFAULT_FAMILY, "pt": float(DEFAULT_PT), "bold": True,
                      "italic": False, "underline": False}

        self.section("Inhalt")
        self.edit = PlainPasteEdit()
        self.edit.setPlaceholderText("Text eingeben …")
        # Absätze ohne eigene Ausrichtung stehen zentriert – wie bisher in labelwerk
        self.edit.document().setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignHCenter))
        self.layout_.addWidget(self.edit)

        self.section("Schrift")
        self.family = QFontComboBox()
        self.layout_.addWidget(self.family)
        row = QHBoxLayout()
        self.size = QComboBox()
        self.size.setEditable(True)
        self.size.addItems([str(s) for s in SIZES_PT])
        self.size.setToolTip("Schriftgröße in pt")
        self.grow = _button("A⁺", "Schrift größer", checkable=False)
        self.shrink = _button("A⁻", "Schrift kleiner", checkable=False)
        row.addWidget(self.size, 1)
        row.addWidget(self.grow)
        row.addWidget(self.shrink)
        self.layout_.addLayout(row)

        self.section("Stil")
        row = QHBoxLayout()
        self.bold = _button("B", "Fett (Strg+B)")
        self.italic = _button("I", "Kursiv (Strg+I)")
        self.underline = _button("U", "Unterstrichen (Strg+U)")
        for button, attr in ((self.bold, "bold"), (self.italic, "italic"),
                             (self.underline, "underline")):
            button.setProperty("style", attr)
            row.addWidget(button)
        self.layout_.addLayout(row)

        self.section("Textposition")
        row = QHBoxLayout()
        self.align_group = QButtonGroup(self)
        self.align_buttons = {}
        for key, text, tip in (("left", "⯇", "Linksbündig"), ("center", "≡", "Zentriert"),
                               ("right", "⯈", "Rechtsbündig"), ("justify", "☰", "Blocksatz")):
            button = _button(text, tip)
            self.align_group.addButton(button)
            self.align_buttons[key] = button
            row.addWidget(button)
        self.layout_.addLayout(row)

        self.fit = _button("FESTE RAHMENGRÖSSE", "Text automatisch so skalieren, dass er passt")
        self.layout_.addWidget(self.fit)

        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        self.layout_.addWidget(self.error)
        self.layout_.addStretch()

        self.refresh()
        self.edit.document().contentsChanged.connect(self._apply)
        self.edit.currentCharFormatChanged.connect(self._sync_buttons)
        self.edit.cursorPositionChanged.connect(self._sync_buttons)
        self.family.currentFontChanged.connect(lambda font: self._format(family=font.family()))
        self.size.activated.connect(lambda _: self._size_entered())
        self.size.lineEdit().editingFinished.connect(self._size_entered)
        self.grow.clicked.connect(lambda: self._step_size(+1))
        self.shrink.clicked.connect(lambda: self._step_size(-1))
        self.bold.clicked.connect(lambda on: self._format(bold=on))
        self.italic.clicked.connect(lambda on: self._format(italic=on))
        self.underline.clicked.connect(lambda on: self._format(underline=on))
        for key, button in self.align_buttons.items():
            button.clicked.connect(lambda _=False, k=key: self._align(k))
        self.fit.toggled.connect(lambda _: self._apply())
        for keys, button in ((QKeySequence.StandardKey.Bold, self.bold),
                             (QKeySequence.StandardKey.Italic, self.italic),
                             (QKeySequence.StandardKey.Underline, self.underline)):
            QShortcut(keys, self.edit, activated=button.click)

    @property
    def obj(self) -> TextObject:
        return self.doc.objects[0]

    # --- Formatieren ------------------------------------------------------
    def _target(self) -> QTextCursor:
        """Markierung, sonst der ganze Text (wie ein ausgewählter Textrahmen)."""
        cursor = self.edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.Document)
        return cursor

    def _format(self, family: str | None = None, size: float | None = None,
                bold: bool | None = None, italic: bool | None = None,
                underline: bool | None = None) -> None:
        if self._updating:
            return
        fmt = QTextCharFormat()
        if family is not None:
            fmt.setFontFamilies([family])
        if size is not None:
            fmt.setFontPointSize(size)
        if bold is not None:
            fmt.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        if italic is not None:
            fmt.setFontItalic(italic)
        if underline is not None:
            fmt.setFontUnderline(underline)
        if not self.edit.textCursor().hasSelection():   # ganzer Text: Grundformat anpassen
            for key, value in (("family", family), ("pt", size), ("bold", bold),
                               ("italic", italic), ("underline", underline)):
                if value is not None:
                    self._base[key] = value
        self._target().mergeCharFormat(fmt)
        self.edit.mergeCurrentCharFormat(fmt)       # Weitertippen in gleicher Formatierung
        self._apply()

    def set_size_pt(self, size: float) -> None:
        size = min(max(size, MIN_PT), MAX_PT)
        self._format(size=size)
        self._sync_buttons()

    def _size_entered(self) -> None:
        try:
            self.set_size_pt(float(self.size.currentText().replace(",", ".")))
        except ValueError:
            self._sync_buttons()

    def _step_size(self, direction: int) -> None:
        current = self._props(self.edit.currentCharFormat())["pt"]
        if direction > 0:
            bigger = [s for s in SIZES_PT if s > current + 0.01]
            self.set_size_pt(bigger[0] if bigger else min(current + 12, MAX_PT))
        else:
            smaller = [s for s in SIZES_PT if s < current - 0.01]
            self.set_size_pt(smaller[-1] if smaller else MIN_PT)

    def _align(self, key: str) -> None:
        cursor = self.edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.Document)
        fmt = cursor.blockFormat()
        fmt.setAlignment(_ALIGN_TO_QT[key])
        cursor.mergeBlockFormat(fmt)
        self._apply()

    # --- Editor ↔ Modell --------------------------------------------------
    def _props(self, fmt: QTextCharFormat) -> dict:
        """Formatierung eines Textstücks: nur ausdrücklich Gesetztes, sonst Grundformat."""
        props = dict(self._base)
        families = fmt.fontFamilies() if fmt.hasProperty(_P.FontFamilies) else None
        if families:
            props["family"] = families[0]
        if fmt.hasProperty(_P.FontPointSize) and fmt.fontPointSize() > 0:
            props["pt"] = fmt.fontPointSize()
        if fmt.hasProperty(_P.FontWeight):
            props["bold"] = fmt.fontWeight() >= QFont.Weight.Bold
        if fmt.hasProperty(_P.FontItalic):
            props["italic"] = fmt.fontItalic()
        if fmt.hasProperty(_P.TextUnderlineStyle) or fmt.hasProperty(_P.FontUnderline):
            props["underline"] = fmt.fontUnderline()
        return props

    def _fill_base_formats(self) -> None:
        """Fehlende Eigenschaften aus dem Grundformat setzen – der Editor zeigt, was gedruckt wird."""
        document = self.edit.document()
        block = document.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.isValid() and not _complete(fragment.charFormat()):
                    cursor = QTextCursor(document)
                    cursor.setPosition(fragment.position())
                    cursor.setPosition(fragment.position() + fragment.length(),
                                       QTextCursor.MoveMode.KeepAnchor)
                    cursor.mergeCharFormat(_char_format_of(self._props(fragment.charFormat())))
                it += 1
            block = block.next()
        if not _complete(self.edit.currentCharFormat()):
            self.edit.mergeCurrentCharFormat(_char_format_of(self._props(self.edit.currentCharFormat())))

    def to_text_object(self) -> TextObject:
        base_pt = self._base["pt"]
        paragraphs = []
        block = self.edit.document().begin()
        while block.isValid():
            spans = []
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.isValid():
                    spans.append(_span(fragment.text(), self._props(fragment.charFormat()), base_pt))
                it += 1
            if not spans:
                spans.append(_span("", self._props(block.charFormat()), base_pt))
            paragraphs.append(Paragraph(spans, _block_align(block.blockFormat())))
            block = block.next()
        return TextObject(paragraphs, size_pt=base_pt, font_path=self.obj.font_path,
                          fit=self.fit.isChecked())

    def _apply(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            self._fill_base_formats()
        finally:
            self._updating = False
        self.doc.objects[0] = self.to_text_object()
        self._sync_buttons()
        self.changed.emit()

    def refresh(self) -> None:
        """Editor aus dem Modell aufbauen (Start mit Einstellungen, später „Öffnen“)."""
        obj = self.obj
        self._updating = True
        try:
            first = obj.paragraphs[0].spans[0] if obj.paragraphs and obj.paragraphs[0].spans else None
            self._base = {"family": (first.family if first else None) or DEFAULT_FAMILY,
                          "pt": float(obj.size_pt or DEFAULT_PT),
                          "bold": first.bold if first else True,
                          "italic": first.italic if first else False,
                          "underline": first.underline if first else False}
            document = self.edit.document()
            document.clear()
            cursor = QTextCursor(document)
            cursor.setCharFormat(_char_format_of(self._base))
            for index, para in enumerate(obj.paragraphs):
                if index:
                    cursor.insertBlock()
                block_fmt = cursor.blockFormat()
                block_fmt.setAlignment(_ALIGN_TO_QT.get(para.align, Qt.AlignmentFlag.AlignHCenter))
                cursor.setBlockFormat(block_fmt)
                for span in para.spans:
                    cursor.insertText(span.text, _char_format(span, obj.size_pt or DEFAULT_PT))
            self.edit.setTextCursor(cursor)
            self.edit.setCurrentCharFormat(_char_format_of(self._props(cursor.charFormat())))
            self.fit.setChecked(obj.auto)
        finally:
            self._updating = False
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        """Knöpfe zeigen die Formatierung an der Schreibmarke."""
        props = self._props(self.edit.currentCharFormat())
        widgets = (self.family, self.size, self.bold, self.italic, self.underline,
                   *self.align_buttons.values())
        for w in widgets:
            w.blockSignals(True)
        self.family.setCurrentFont(QFont(props["family"]))
        self.size.setEditText(f"{props['pt']:g}")
        self.bold.setChecked(props["bold"])
        self.italic.setChecked(props["italic"])
        self.underline.setChecked(props["underline"])
        align = _block_align(self.edit.textCursor().blockFormat())
        self.align_buttons[align].setChecked(True)
        for w in widgets:
            w.blockSignals(False)

    def show_error(self, message: str | None) -> None:
        self.error.setText(message or "")
        self.error.setVisible(bool(message))


def _span(text: str, props: dict, base_pt: float) -> Span:
    return Span(text,
                family=None if props["family"] == DEFAULT_FAMILY else props["family"],
                size_pt=None if abs(props["pt"] - base_pt) < 0.01 else props["pt"],
                bold=props["bold"], italic=props["italic"], underline=props["underline"])


def _char_format_of(props: dict) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setFontFamilies([props["family"]])
    fmt.setFontPointSize(props["pt"])
    fmt.setFontWeight(QFont.Weight.Bold if props["bold"] else QFont.Weight.Normal)
    fmt.setFontItalic(props["italic"])
    fmt.setFontUnderline(props["underline"])
    return fmt


def _char_format(span: Span, base_pt: float) -> QTextCharFormat:
    return _char_format_of({"family": span.family or DEFAULT_FAMILY,
                            "pt": span.size_pt or base_pt, "bold": span.bold,
                            "italic": span.italic, "underline": span.underline})


def _complete(fmt: QTextCharFormat) -> bool:
    """Sind alle vom Modell gelesenen Eigenschaften ausdrücklich gesetzt?"""
    return (fmt.hasProperty(_P.FontFamilies) and fmt.hasProperty(_P.FontPointSize)
            and fmt.fontPointSize() > 0 and fmt.hasProperty(_P.FontWeight)
            and fmt.hasProperty(_P.FontItalic)
            and (fmt.hasProperty(_P.TextUnderlineStyle) or fmt.hasProperty(_P.FontUnderline)))


def _block_align(fmt) -> str:
    """Ausrichtung eines Absatzes; nicht gesetzt (z. B. nach setPlainText) = zentriert."""
    if not fmt.hasProperty(QTextFormat.Property.BlockAlignment):
        return "center"
    return _align_of(fmt.alignment())


def _align_of(alignment) -> str:
    if alignment & Qt.AlignmentFlag.AlignJustify:
        return "justify"
    if alignment & Qt.AlignmentFlag.AlignRight:
        return "right"
    if alignment & Qt.AlignmentFlag.AlignLeft:
        return "left"
    return "center"
```

`src/labelwerk/gui/settings_dialog.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
"""Dialog „Einstellungen“: Standardwerte für neue Etiketten, Drucker, Ansicht.

Neue Einstellung = Feld in settings.Settings + eine Zeile im passenden Abschnitt hier.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFontComboBox,
                               QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QVBoxLayout)

from ..document import MAX_MARGIN_MM, MAX_PT, MIN_PT
from ..labels import labels_for_model
from ..printer import DEFAULT_MODEL
from ..settings import Settings, save_settings
from .widgets import DoubleSpinBox, SpinBox


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, path: str | Path | None = None,
                 model: str = DEFAULT_MODEL, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.path = path
        self.saved: Settings | None = None
        layout = QVBoxLayout(self)

        form = self._section(layout, "Neues Etikett")
        self.label = QComboBox()
        for lbl in labels_for_model(model):
            self.label.addItem(lbl.description, lbl.id)
        self.label.setCurrentIndex(max(0, self.label.findData(settings.label_id)))
        form.addRow("Etikett", self.label)
        self.orientation = QComboBox()
        self.orientation.addItem("Horizontal (Text längs zum Band)", "horizontal")
        self.orientation.addItem("Vertikal (Text quer zum Band)", "vertical")
        self.orientation.setCurrentIndex(self.orientation.findData(settings.orientation))
        form.addRow("Ausrichtung", self.orientation)
        self.margin = DoubleSpinBox()
        self.margin.setSuffix(" mm")
        self.margin.setDecimals(1)
        self.margin.setSingleStep(0.5)
        self.margin.setRange(0.0, MAX_MARGIN_MM)
        self.margin.setValue(settings.margin_mm)
        form.addRow("Ränder", self.margin)
        row = QHBoxLayout()
        self.font_auto = QCheckBox("Automatisch")
        self.font_size = SpinBox()
        self.font_size.setRange(int(MIN_PT), int(MAX_PT))
        self.font_size.setSuffix(" pt")
        self.font_size.setValue(round(settings.font_size_pt or 19))
        self.font_auto.setChecked(settings.font_size_pt is None)
        self.font_size.setEnabled(settings.font_size_pt is not None)
        self.font_auto.toggled.connect(lambda auto: self.font_size.setEnabled(not auto))
        row.addWidget(self.font_auto)
        row.addWidget(self.font_size)
        form.addRow("Schriftgröße", row)
        self.font_family = QFontComboBox()
        self.font_family.setCurrentFont(QFont(settings.font_family))
        form.addRow("Schriftart", self.font_family)

        form = self._section(layout, "Drucker")
        self.check_media = QCheckBox("Rolle beim Start und beim Einschalten prüfen")
        self.check_media.setChecked(settings.check_media_on_start)
        form.addRow(self.check_media)

        form = self._section(layout, "Ansicht")
        self.zoom = SpinBox()
        self.zoom.setSuffix(" %")
        self.zoom.setRange(25, 400)
        self.zoom.setSingleStep(10)
        self.zoom.setValue(settings.start_zoom)
        form.addRow("Startzoom", self.zoom)

        hint = QLabel("Gilt für neue Etiketten bzw. ab dem nächsten Start.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _section(self, layout: QVBoxLayout, title: str) -> QFormLayout:
        box = QGroupBox(title.upper())
        form = QFormLayout(box)
        layout.addWidget(box)
        return form

    def values(self) -> Settings:
        return Settings(
            label_id=self.label.currentData(),
            orientation=self.orientation.currentData(),
            margin_mm=self.margin.value(),
            font_size_pt=None if self.font_auto.isChecked() else self.font_size.value(),
            font_family=self.font_family.currentFont().family(),
            check_media_on_start=self.check_media.isChecked(),
            start_zoom=self.zoom.value(),
        )

    def accept(self) -> None:
        settings = self.values()
        try:
            save_settings(settings, self.path)
        except OSError as e:
            self.error.setText(str(e))
            self.error.show()
            return                                   # Dialog bleibt offen
        self.saved = settings
        super().accept()
```

`src/labelwerk/gui/theme/rawblock.qss` – **komplett ersetzen** (vollständiger Inhalt):

```css
/* labelwerk – an RawBlock angelehnt: Schwarz/Weiß, kräftige Rahmen, eckig.
   Austauschbar: andere .qss-Datei laden oder ganz weglassen (System-Look). */

* {
    font-family: "Work Sans", "Inter", "DejaVu Sans", sans-serif;
    font-size: 14px;
    color: #000000;
}
QMainWindow, QWidget { background: #FFFFFF; }

QToolBar {
    background: #FFFFFF;
    border: none;
    border-bottom: 3px solid #000000;
    padding: 6px;
    spacing: 6px;
}
/* Qt zieht den 3-px-Unterrand vom unteren Innenabstand ab – ausgleichen, damit oben = unten */
QToolBar QToolButton { margin-bottom: 3px; }
QToolBar QToolButton {
    background: #FFFFFF;
    border: 3px solid #000000;
    border-radius: 0;
    padding: 6px 14px;
    font-weight: 700;
    letter-spacing: 2px;
}
QToolBar QToolButton:hover, QToolBar QToolButton:checked {
    background: #000000;
    color: #FFFFFF;
}
QToolBar QToolButton#print { background: #000000; color: #FFFFFF; }
QToolBar QToolButton#print:hover { background: #FFFFFF; color: #000000; }
QToolBar QToolButton:disabled, QToolBar QToolButton#print:disabled {
    background: #F0F0F0;
    color: #999999;
    border-color: #CCCCCC;
}

#panels { border-right: 3px solid #000000; }
QLabel#panelTitle { font-size: 22px; font-weight: 900; padding: 4px 0 8px 0; }
QLabel[role="section"] { font-weight: 900; letter-spacing: 1px; padding-top: 10px; }
QLabel#fixedSize { font-family: "Space Mono", "DejaVu Sans Mono", monospace; }

QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #F0F0F0;
    border: 3px solid #000000;
    border-radius: 0;
    padding: 6px 8px;
    font-family: "Space Mono", "DejaVu Sans Mono", monospace;
}
QPlainTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { background: #E8E8E8; }
QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-width: 5px; }
/* Zahlenfelder: eigene Hoch/Runter-Knöpfe – mit eigenem Rahmen zeichnet Qt sonst keine Pfeile */
QSpinBox, QDoubleSpinBox { padding: 4px 32px 4px 8px; min-height: 26px; }
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: padding;
    width: 26px;
    background: #FFFFFF;
    border-left: 3px solid #000000;
}
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-position: top right; border-bottom: 1px solid #000000; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-position: bottom right; }
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover { background: #000000; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url(@THEME@/arrow-up-black.svg); width: 10px; height: 7px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url(@THEME@/arrow-down-black.svg); width: 10px; height: 7px; }
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover { image: url(@THEME@/arrow-up-white.svg); }
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover { image: url(@THEME@/arrow-down-white.svg); }
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled { image: url(@THEME@/arrow-up-gray.svg); }
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled { image: url(@THEME@/arrow-down-gray.svg); }
QSpinBox::up-button:disabled, QDoubleSpinBox::up-button:disabled,
QSpinBox::down-button:disabled, QDoubleSpinBox::down-button:disabled { border-left-color: #CCCCCC; background: #F5F5F5; }
QComboBox { padding: 4px 32px 4px 8px; min-height: 26px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 26px; border-left: 3px solid #000000; background: #FFFFFF; }
QComboBox::drop-down:hover { background: #000000; }
QComboBox::down-arrow { image: url(@THEME@/arrow-down-black.svg); width: 10px; height: 7px; }
QComboBox::down-arrow:hover { image: url(@THEME@/arrow-down-white.svg); }
QSpinBox:disabled, QDoubleSpinBox:disabled { border-color: #CCCCCC; background: #F5F5F5; color: #999999; }
QComboBox QAbstractItemView { border: 3px solid #000000; selection-background-color: #000000; selection-color: #FFFFFF; }

QCheckBox::indicator { width: 16px; height: 16px; border: 3px solid #000000; background: #FFFFFF; }
QCheckBox::indicator:checked { background: #000000; }

QLabel#error { color: #FF0000; border: 3px solid #FF0000; padding: 6px; }
QLabel#mediaStatus { padding: 0 10px; border-left: 2px solid #000000; font-weight: 700; }
QLabel#mediaStatus[state="ok"] { color: #008000; border-color: #008000; }
QLabel#mediaStatus[state="warn"] { color: #CC7A00; border-color: #FFA500; }
QLabel#mediaStatus[state="error"] { color: #FF0000; border-color: #FF0000; }
QPushButton { background: #FFFFFF; border: 3px solid #000000; border-radius: 0; padding: 6px 10px; font-weight: 700; letter-spacing: 1px; }
QPushButton:hover { background: #000000; color: #FFFFFF; }
QPushButton:disabled { border-color: #CCCCCC; color: #999999; background: #F0F0F0; }
QPushButton#formatButton { padding: 4px 8px; min-width: 22px; }
QPushButton#formatButton:checked { background: #000000; color: #FFFFFF; }
QPushButton#formatButton[style="italic"] { font-style: italic; }
QPushButton#formatButton[style="underline"] { text-decoration: underline; }
QTextEdit { background: #F0F0F0; border: 3px solid #000000; border-radius: 0; padding: 4px; }
QTextEdit:focus { border-width: 5px; }
QFontComboBox { min-width: 0; }

QStatusBar { border-top: 3px solid #000000; }
QStatusBar QLabel[state="ok"] { color: #008000; font-weight: 700; }
QStatusBar QLabel[state="error"] { color: #FF0000; font-weight: 700; }
QStatusBar QToolButton { border: 2px solid #000000; padding: 0 8px; font-weight: 700; }
QStatusBar QToolButton:hover { background: #000000; color: #FFFFFF; }

QGraphicsView { border: none; }
QToolTip { background: #000000; color: #FFFFFF; border: none; padding: 8px 12px; font-family: "Space Mono", "DejaVu Sans Mono", monospace; }
```

`src/labelwerk/render.py` – **komplett ersetzen** (vollständiger Inhalt):

```python
"""Rendert Etiketteninhalte als Bild in exakter Druckauflösung.

Der Zeilensatz verallgemeinert Pillows ``multiline_text`` auf formatierte Textstücke:
gleicher Zeilenabstand (Unterkante von „A“ + 4 Punkte), gleiche Ausrichtungsrechnung –
reiner Text sieht dadurch pixelgleich aus wie früher.
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from . import fonts
from .document import (ALIGNMENTS, MAX_MARGIN_MM, ORIENTATIONS, Document, Paragraph, Span,
                       TextObject)
from .labels import DPI, get_label, length_limits

MARGIN = 12            # Punkte, ca. 1 mm
PT = DPI / 72          # Druckpunkte pro typografischem Punkt
REF_PT = 12.0          # Bezugsgröße für automatische Skalierung von Stücken mit eigener Größe
MIN_DOTS = 8           # kleinste Schrift in Druckpunkten
_LINE_GAP = 4          # wie Pillow multiline_text
_SLANT = 0.2           # Ersatzkursive: Scherung, wenn die Schrift keine echte Kursive hat


class TextTooLarge(ValueError):
    """Text passt bei fester Schriftgröße nicht aufs Etikett."""

    def __init__(self, size_pt: float, max_pt: float, label_id: str):
        super().__init__(f"Text passt nicht auf Etikett {label_id!r} bei Schriftgröße "
                         f"{_fmt_pt(size_pt)} pt (höchstens {_fmt_pt(max_pt)} pt).")
        self.size_pt, self.max_pt = size_pt, max_pt


def _fmt_pt(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def render_text(text: str, label_id: str, size_pt: float | None = None,
                font_path: str | None = None) -> Image.Image:
    """Reinen Text rendern (Standardformatierung)."""
    obj = TextObject.plain(text, size_pt=size_pt, font_path=font_path)
    return render_document(Document(label_id, objects=[obj]))


def font_warnings(doc: Document) -> list[str]:
    """Hinweise zu ersetzten Schriften (je Familie einmal)."""
    warnings: list[str] = []
    for obj in doc.objects:
        for para in obj.paragraphs:
            for span in para.spans:
                if span.family is None or (obj.font_path and span.family is None):
                    continue
                match = fonts.resolve(span.family, span.bold, span.italic)
                text = f"Schrift „{span.family}“ nicht gefunden – ersetzt durch „{match.family}“."
                if match.family.casefold() != span.family.casefold() and text not in warnings:
                    warnings.append(text)
    return warnings


def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
    """Dokument als Druckbild in exakter Auflösung (Vorschau = Druck).

    Gerendert wird in Leserichtung; bei Ausrichtung „horizontal“ (Text längs zum Band)
    wird das Bild danach für den Drucker um 90° im Uhrzeigersinn gedreht – so kommt der
    Textanfang zuerst aus dem Drucker und das veränderliche Ende liegt in Leserichtung rechts.
    """
    if doc.orientation not in ORIENTATIONS:
        raise ValueError(f"Unbekannte Ausrichtung {doc.orientation!r} – erlaubt: horizontal, vertical")
    horizontal = doc.orientation == "horizontal"
    label = get_label(doc.label_id)
    min_len, max_len = length_limits(model)
    margin = round(min(max(doc.margin_mm, 0.0), MAX_MARGIN_MM) * DPI / 25.4)
    across = label.width                      # quer zum Band (fest)
    feed = label.height                       # in Bandlaufrichtung; None = automatisch
    if feed is None and doc.length_mm is not None:
        feed = min(max(round(doc.length_mm * DPI / 25.4), min_len), max_len)
    if feed is not None:                      # feste Länge: Rand darf nicht alles aufbrauchen
        margin = min(margin, max(0, (feed - 2 * MARGIN) // 2))
    obj = doc.objects[0] if doc.objects else TextObject("")
    for para in obj.paragraphs:
        if para.align not in ALIGNMENTS:
            raise ValueError(f"Unbekannte Textposition {para.align!r} – erlaubt: links, zentriert, "
                             "rechts, Blocksatz (left, center, right, justify)")

    across_room = across - 2 * MARGIN
    feed_room = (feed if feed else max_len) - 2 * margin
    max_w, max_h = (feed_room, across_room) if horizontal else (across_room, feed_room)
    base = _fit(obj, max(10, across // 5), max_w, max_h, doc.label_id)
    lines = _shape(obj, base)
    l, t, r, b = _block_box(lines)

    text_w, text_h = r - l, b - t
    if feed is None:
        feed = min(max((text_w if horizontal else text_h) + 2 * margin, min_len), max_len)
    width, height = (feed, across) if horizontal else (across, feed)
    img = Image.new("RGB", (width, height), "white")
    _draw(img, lines, (width - text_w) // 2 - l, (height - text_h) // 2 - t)
    return img.rotate(-90, expand=True) if horizontal else img


# --- Schriftgrößen ----------------------------------------------------------
def _span_dots(obj: TextObject, span: Span, base: int) -> int:
    """Größe eines Stücks in Druckpunkten bei Grundgröße ``base`` (gemeinsam skaliert)."""
    if span.size_pt is None:
        return base
    ref = obj.size_pt or REF_PT
    return max(1, round(base * span.size_pt / ref))


def _fit(obj: TextObject, auto_start: int, max_w: int, max_h: int, label_id: str) -> int:
    """Grundgröße in Druckpunkten: fest, oder größte passende ≤ auto_start (Halbierung)."""
    def fits(base: int) -> bool:
        l, t, r, b = _block_box(_shape(obj, base, mode="1"))
        return (r - l) <= max_w and (b - t) <= max_h

    start = auto_start if obj.auto else round(obj.size_pt * PT)
    if fits(start):
        return start
    best, lo, hi = None, MIN_DOTS, start - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if fits(mid):
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    if not obj.auto:
        max_pt = int((best if best else MIN_DOTS) / PT)
        raise TextTooLarge(obj.size_pt, max_pt, label_id)
    return best if best else MIN_DOTS          # passt nicht einmal klein – kleinste Größe zeigen


# --- Zeilensatz ---------------------------------------------------------------
@dataclass
class _Piece:
    text: str
    font: object
    dots: int
    underline: bool
    slant: bool                # Ersatzkursive
    x: float = 0.0             # links, relativ zum Block
    y: float = 0.0             # Oberkante (Ascender-Linie), relativ zum Block


def _font_for(obj: TextObject, span: Span, dots: int):
    if span.family is None and obj.font_path:
        return fonts.load(obj.font_path, dots), False
    match = fonts.resolve(span.family, span.bold, span.italic)
    return fonts.load(match.path, dots), span.italic and not match.italic


def _shape(obj: TextObject, base: int, mode: str = "L") -> list[list[_Piece]]:
    """Stücke mit Position im Block (mode „1“ zum Messen, „L“ zum Zeichnen – wie Pillow)."""
    rows = []
    for para in obj.paragraphs:
        spans = para.spans or [Span("")]
        pieces = []
        for span in spans:
            dots = _span_dots(obj, span, base)
            font, slant = _font_for(obj, span, dots)
            pieces.append(_Piece(span.text, font, dots, span.underline, slant))
        rows.append((para, pieces))

    widths = [sum(p.font.getlength(p.text, mode) for p in pieces) for _, pieces in rows]
    max_width = max(widths, default=0)
    top = 0.0
    lines = []
    for (para, pieces), width in zip(rows, widths):
        ascent = max(p.font.getmetrics()[0] for p in pieces)
        spacing = max(p.font.getbbox("A", mode)[3] for p in pieces) + _LINE_GAP
        if para.align == "justify":
            pieces = _justify(pieces, max_width, mode)
        else:
            x = {"left": 0.0, "center": (max_width - width) / 2.0,
                 "right": max_width - width}[para.align]
            for p in pieces:
                p.x = x
                x += p.font.getlength(p.text, mode)
        for p in pieces:
            p.y = top + ascent - p.font.getmetrics()[0]    # gemeinsame Grundlinie
        lines.append(pieces)
        top += spacing
    return lines


def _justify(pieces: list[_Piece], max_width: float, mode: str) -> list[_Piece]:
    """Wortabstände dehnen, bis die Zeile die Blockbreite füllt (ein Wort: linksbündig)."""
    words: list[_Piece] = []
    gaps_before: list[bool] = []
    for p in pieces:
        for i, part in enumerate(p.text.split(" ")):
            words.append(_Piece(part, p.font, p.dots, p.underline, p.slant))
            gaps_before.append(i > 0)
    gaps = sum(gaps_before[1:])
    used = sum(w.font.getlength(w.text, mode) for w in words)
    extra = (max_width - used) / gaps if gaps else 0.0
    x = 0.0
    for word, gap in zip(words, gaps_before):
        if gap and word is not words[0]:
            x += extra
        word.x = x
        x += word.font.getlength(word.text, mode)
    return words


def _block_box(lines: list[list[_Piece]]) -> tuple[int, int, int, int]:
    """Tintenbox des Blocks (wie Pillow multiline_textbbox), auf ganze Punkte gerundet."""
    boxes = []
    for pieces in lines:
        for p in pieces:
            l, t, r, b = p.font.getbbox(p.text, "1", anchor="la")
            if p.underline:
                b = max(b, p.font.getmetrics()[0] + _underline(p.dots)[0] + _underline(p.dots)[1])
            if p.slant:
                r += _SLANT * p.font.getmetrics()[0]
            boxes.append((p.x + l, p.y + t, p.x + r, p.y + b))
    if not boxes:
        return (0, 0, 0, 0)
    return tuple(round(v) for v in (min(b[0] for b in boxes), min(b[1] for b in boxes),
                                    max(b[2] for b in boxes), max(b[3] for b in boxes)))


def _underline(dots: int) -> tuple[int, int]:
    """(Abstand unter der Grundlinie, Stärke) in Druckpunkten."""
    return max(1, round(dots * 0.10)), max(1, round(dots * 0.06))


def _draw(img: Image.Image, lines: list[list[_Piece]], x0: int, y0: int) -> None:
    draw = ImageDraw.Draw(img)
    for pieces in lines:
        for p in pieces:
            x, y = x0 + p.x, y0 + p.y
            if p.slant:
                _draw_slanted(img, p, x, y)
            else:
                draw.text((x, y), p.text, fill="black", font=p.font, anchor="la")
            if p.underline and p.text:
                offset, thickness = _underline(p.dots)
                base_y = round(y + p.font.getmetrics()[0] + offset)
                length = p.font.getlength(p.text)
                draw.rectangle((round(x), base_y, round(x + length), base_y + thickness - 1),
                               fill="black")


def _draw_slanted(img: Image.Image, p: _Piece, x: float, y: float) -> None:
    """Ersatzkursive: Stück einzeln zeichnen und um die Grundlinie nach rechts scheren."""
    ascent, descent = p.font.getmetrics()
    width = int(p.font.getlength(p.text) + _SLANT * ascent) + 2
    mask = Image.new("L", (width, ascent + descent), 0)
    ImageDraw.Draw(mask).text((0, 0), p.text, fill=255, font=p.font, anchor="la")
    sheared = mask.transform(mask.size, Image.Transform.AFFINE,
                             (1, _SLANT, -_SLANT * ascent, 0, 1, 0), Image.Resampling.BICUBIC)
    img.paste((0, 0, 0), (round(x), round(y)), sheared)
```

- [ ] **Step 4: Grün prüfen** – Run: `.venv/bin/python -m pytest -q` (dreimal) – Expected: `258 passed`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/document.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/settings_dialog.py src/labelwerk/gui/theme/rawblock.qss src/labelwerk/render.py tests/gui/test_gui_papier.py tests/gui/test_gui_settings.py tests/gui/test_gui_text.py tests/gui/test_gui_window.py tests/test_rich_text.py
git commit -m "GUI: Text-Panel mit zeichenweiser Formatierung wie im P-touch Editor

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Doku

**Files:** Modify `README.md`, `CLAUDE.md`

- [ ] **Step 1: README** – im Codeblock „Benutzung“ ergänzen:

```bash
labelwerk fonts                                            # installierte Schriften
labelwerk print "Max Mustermann\nMusterstr. 5" --align left --font-family "Liberation Sans" -s 14
```

und den Absatz zur GUI ergänzen um: „Text: Schriftart, Größe (pt), fett/kursiv/unterstrichen und Textposition – zeichenweise wie im P-touch Editor. Ohne Markierung gilt die Formatierung für den ganzen Text. ‚Feste Rahmengröße‘ skaliert den Text passend aufs Etikett.“ Im Architektur-Block `fonts.py   Schriften (fontconfig)` ergänzen.

- [ ] **Step 2: CLAUDE.md**
  - „Stand“: Zeile `- Text-Formatierung zeichenweise (GUI-Editor wie P-touch, CLI --align/--font-family/--bold/--italic/--underline, labelwerk fonts), Größen in pt.` ergänzen; Testzahl `258 Tests grün`.
  - „Architektur“: `fonts.py   Schriften über fontconfig (families, resolve, load), Ersatzkursive bei fehlender Kursiv-Datei` ergänzen; `document.py`-Zeile um `Span/Paragraph/TextObject (zeichenweise Formatierung)` ergänzen; `render.py`-Zeile um `Zeilensatz mit gemeinsamer Grundlinie, font_warnings` ergänzen; `cli.py`-Zeile um `labelwerk fonts`, `--align`, `--font-family`, `--bold/--no-bold`, `--italic`, `--underline` ergänzen.
  - Roadmap Punkt 0: `3 Funktionsliste …` ersetzen durch `3a/3b Text-Formatierung (erledigt) · 3c Neu/Öffnen/Speichern + Favoriten · 3d Freies Platzieren + Bild · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen`.

- [ ] **Step 3: Prüfen und Commit** – Run: `.venv/bin/python -m pytest -q` – Expected: `258 passed`

```bash
git add README.md CLAUDE.md
git commit -m "Doku: Text-Formatierung, fonts, pt

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Abnahme (manuell, durch den Nutzer)

- [ ] GUI: Adresse eingeben, alles markieren → linksbündig; Absenderzeile markieren → 7 pt + unterstrichen; Nachname markieren → fett. Vorschau entspricht dem Editor.
- [ ] Ohne Markierung „I“ → ganzer Text kursiv (auch mit DejaVu Sans, über Ersatzkursive).
- [ ] „Feste Rahmengröße“ an → Text passt sich an, Verhältnisse bleiben.
- [ ] Einstellungen: Schriftart/Schriftgröße (pt) setzen, Neustart → neues Etikett startet damit.
- [ ] `labelwerk fonts` listet Schriften; `labelwerk print … --align left --font-family "Liberation Sans" -s 14` druckt wie erwartet.
