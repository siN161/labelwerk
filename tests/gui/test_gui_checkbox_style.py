"""RawBlock: a locked but checked tick box (FILE/PAPER under "Tabs in the toolbar") looks
checked – not like an empty box."""
from PySide6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton

from labelwerk.gui.app import load_theme


def _indicator_center(qtbot, qapp, checked: bool):
    box = QCheckBox("X")
    qtbot.addWidget(box)
    box.setStyleSheet(load_theme())
    box.setChecked(checked)
    box.setEnabled(False)
    box.resize(box.sizeHint())
    box.show()
    image = box.grab().toImage()
    opt = QStyleOptionButton()
    box.initStyleOption(opt)
    rect = box.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, opt, box)
    return image.pixelColor(rect.center()).lightness()


def test_disabled_checked_box_looks_checked(qtbot, qapp):
    assert _indicator_center(qtbot, qapp, True) < _indicator_center(qtbot, qapp, False) - 60
