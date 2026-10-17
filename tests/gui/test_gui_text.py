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
