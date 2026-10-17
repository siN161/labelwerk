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


# --- Fix nach Review ---------------------------------------------------------
def _mixed(panel):
    """„klein gross“: klein 10 pt, gross 36 pt."""
    panel.edit.setPlainText("klein gross")
    _select(panel, 0, 5)
    panel.set_size_pt(10)
    _select(panel, 6, 11)
    panel.set_size_pt(36)


def _cursor_to(panel, pos):
    cursor = panel.edit.textCursor()
    cursor.setPosition(pos)
    panel.edit.setTextCursor(cursor)


def _sizes(window):
    return [s.size_pt for s in window.doc.objects[0].paragraphs[0].spans if s.text.strip()]


def test_size_field_focus_out_keeps_mixed_sizes(window):
    panel = window.panel("text")
    _mixed(panel)
    _cursor_to(panel, 8)                        # in „gross“, ohne Markierung
    panel.size.lineEdit().editingFinished.emit()
    spans = window.doc.objects[0].paragraphs[0].spans
    assert len({s.size_pt for s in spans if s.text.strip()}) == 2


def test_size_field_rejects_nan(window):
    panel = window.panel("text")
    panel.edit.setPlainText("abc")
    panel.size.setEditText("nan")
    panel.size.lineEdit().editingFinished.emit()
    assert panel._base["pt"] == 19.0
    assert panel.size.currentText() == "19"


def test_size_combo_does_not_append_entries(window):
    from labelwerk.gui.panels.text import SIZES_PT
    panel = window.panel("text")
    panel.edit.setPlainText("abc")
    for text in ("abc", "19"):
        panel.size.setEditText(text)
        panel.size.lineEdit().editingFinished.emit()
    assert panel.size.count() == len(SIZES_PT)
    from PySide6.QtWidgets import QComboBox
    assert panel.size.insertPolicy() == QComboBox.InsertPolicy.NoInsert


def test_refresh_keeps_format_of_empty_paragraph(window):
    from labelwerk.document import Paragraph, Span, TextObject
    panel = window.panel("text")
    window.doc.objects[0] = TextObject([Paragraph([Span("A", size_pt=10)]),
                                        Paragraph([Span("", size_pt=40)]),
                                        Paragraph([Span("B")])])
    panel.refresh()
    paragraphs = panel.to_text_object().paragraphs
    assert paragraphs[1].spans[0].size_pt == 40


def test_shortcuts_are_scoped_to_panel(window):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QShortcut
    panel = window.panel("text")
    shortcuts = panel.findChildren(QShortcut)
    assert len(shortcuts) == 3
    assert all(s.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut for s in shortcuts)


def test_format_change_is_one_undo_step(window):
    panel = window.panel("text")
    panel.edit.setPlainText("aaa bbb")
    panel.edit.document().clearUndoRedoStacks()
    _select(panel, 0, 3)
    panel.italic.click()
    document = panel.edit.document()
    steps = 0
    while document.isUndoAvailable():
        document.undo()
        steps += 1
    assert steps == 1


def test_grow_without_selection_steps_each_fragment(window):
    panel = window.panel("text")
    _mixed(panel)
    _cursor_to(panel, 0)
    panel.grow.click()
    assert _sizes(window) == [11, 48]


def test_grow_with_selection_steps_each_fragment(window):
    panel = window.panel("text")
    _mixed(panel)
    _select(panel, 0, 11)
    panel.grow.click()
    assert _sizes(window) == [11, 48]


# --- Schlussrunde --------------------------------------------------------------
def test_shift_enter_inserts_paragraph_not_line_separator(window, qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    panel = window.panel("text")
    panel.edit.setPlainText("A")
    panel.edit.moveCursor(QTextCursor.MoveOperation.End)
    panel.edit.setFocus()
    QTest.keyClick(panel.edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClicks(panel.edit, "B")
    paras = window.doc.objects[0].paragraphs
    assert ["".join(s.text for s in p.spans) for p in paras] == ["A", "B"]


def test_line_separator_in_text_becomes_paragraphs(window):
    panel = window.panel("text")
    panel.edit.setPlainText("A B")
    paras = window.doc.objects[0].paragraphs
    assert ["".join(s.text for s in p.spans) for p in paras] == ["A", "B"]
    assert all(" " not in s.text for p in paras for s in p.spans)


def test_tab_does_not_insert_tab_character(window, qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    panel = window.panel("text")
    panel.edit.setPlainText("A")
    assert panel.edit.tabChangesFocus()
    QTest.keyClick(panel.edit, Qt.Key.Key_Tab)
    assert "\t" not in panel.edit.toPlainText()
    panel.edit.setPlainText("A\tB")
    spans = window.doc.objects[0].paragraphs[0].spans
    assert "".join(s.text for s in spans) == "A B"


def test_choosing_size_on_mixed_selection_applies_to_all(window):
    panel = window.panel("text")
    panel.edit.setPlainText("ABCD")
    _select(panel, 0, 2)
    panel.set_size_pt(24)
    _select(panel, 2, 4)
    panel.set_size_pt(12)
    _select(panel, 0, 4)
    assert panel.size.currentText() == ""
    panel.size.setCurrentText("12")
    panel.size.activated.emit(panel.size.findText("12"))
    sizes = {s.size_pt for s in window.doc.objects[0].paragraphs[0].spans if s.text}
    assert len(sizes) == 1
    assert panel.size.currentText() == "12"


def test_refresh_keeps_size_ratio_with_unset_base(window):
    from labelwerk.document import Paragraph, Span, TextObject
    panel = window.panel("text")
    window.doc.objects[0] = TextObject([Paragraph([Span("a", size_pt=24), Span("b")])])
    panel.refresh()
    spans = panel.to_text_object().paragraphs[0].spans
    sizes = {s.text: (s.size_pt or panel.to_text_object().size_pt) for s in spans}
    assert sizes["a"] / sizes["b"] == 2.0


def test_align_buttons_have_line_icons(window):
    from importlib import resources
    panel = window.panel("text")
    for key, button in panel.align_buttons.items():
        assert not button.icon().isNull()
        assert button.text() == ""
        assert button.toolTip() and button.accessibleName() == button.toolTip()
        for color in ("black", "white"):
            assert (resources.files("labelwerk.gui") / "icons" / f"align-{key}-{color}.svg").is_file()


def test_style_buttons_show_their_style_without_stylesheet(qtbot):
    from labelwerk.document import Document
    from labelwerk.gui.panels.text import TextPanel
    panel = TextPanel(Document())
    qtbot.addWidget(panel)
    # klassisches Design (ohne Stylesheet): die Knopfschrift zeigt den Stil selbst
    assert panel.bold.font().bold()
    assert panel.italic.font().italic()
    assert panel.underline.font().underline()
