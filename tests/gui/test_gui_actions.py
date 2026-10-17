"""QActions aus dem Kürzel-Verzeichnis (Etappe 3d-1)."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QWidget

from labelwerk import shortcuts
from labelwerk.gui.actions import apply_shortcuts, build_actions


def test_build_actions_creates_one_action_per_entry(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    actions = build_actions(parent, shortcuts.effective({}))
    assert list(actions) == [a.id for a in shortcuts.ACTIONS]
    copy = actions["edit.copy"]
    assert copy.text() == "Kopieren" and copy.parent() is parent
    assert copy.shortcut() == QKeySequence("Ctrl+C")
    assert copy.shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut
    assert actions["file.print"].shortcutContext() == Qt.ShortcutContext.WindowShortcut
    assert actions["align.left"].shortcut().isEmpty()


def test_apply_shortcuts_changes_keys_and_tooltips(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    actions = build_actions(parent, shortcuts.effective({}))
    apply_shortcuts(actions, shortcuts.effective({"edit.copy": "Ctrl+Shift+C", "edit.cut": ""}))
    assert actions["edit.copy"].shortcut() == QKeySequence("Ctrl+Shift+C")
    assert "Ctrl+Shift+C" in actions["edit.copy"].toolTip()
    assert actions["edit.cut"].shortcut().isEmpty()
    assert actions["edit.cut"].toolTip() == "Ausschneiden"
