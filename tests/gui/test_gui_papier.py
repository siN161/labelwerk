import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import MM, Canvas
from labelwerk.gui.main_window import MainWindow
from labelwerk.labels import get_label
from labelwerk.render import label_size, render_document, render_object
from labelwerk.settings import Settings


@pytest.fixture
def window(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.canvas.set_selection([0])      # Start ohne Auswahl: das Startobjekt zum Tippen wählen
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
    assert window.image.height == before + 2 * (59 - 35)   # 1 mm lag ganz im Vorschub


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
    view.set_document(get_label("62"), label_size(doc), [render_object(o, doc) for o in doc.objects],
                      "horizontal")
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
    win.canvas.set_selection([0])
    assert not win.panel("text").fit.isChecked() and win.panel("text").size.currentText() == "19"
    assert win.canvas.zoom == 150


def test_settings_warnings_appear_in_status_bar(qtbot):
    win = MainWindow(settings=Settings(warnings=["Einstellung 'start_zoom' ungültig"]))
    qtbot.addWidget(win)
    assert "start_zoom" in win.result.text()


# --- Vorschub des Druckers längs zum Endlosband ------------------------------------------
def test_margin_hint_when_margin_is_inside_the_printer_strip(window):
    paper = window.panel("paper")
    paper.margin.setValue(1.0)
    assert paper.margin_hint.isVisibleTo(paper)
    assert paper.margin_hint.text() == ("Längs zum Band lässt der Drucker 3,0 mm frei – ein kleinerer "
                                        "Rand wirkt dort nicht.")
    # dezent wie eine Erläuterung (steht beim Standardrand immer da), nicht der Hinweis-Kasten
    assert paper.margin_hint.objectName() != "hint" and "color" in paper.margin_hint.styleSheet()
    paper.margin.setValue(3.0)                          # 35 Punkte: genau der Vorschub
    assert not paper.margin_hint.isVisibleTo(paper)
    paper.margin.setValue(1.0)
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))   # gestanzt: kein Vorschub
    assert not paper.margin_hint.isVisibleTo(paper)


@pytest.mark.parametrize("label, across, along", [("62", "1,5", "3,0"), ("62x29", "1,5", "3,0"),
                                                  ("29", "1,5", "3,0"), ("d24", "2,0", "2,0")])
def test_margin_tooltip_names_the_real_printer_strips(window, label, across, along):
    paper = window.panel("paper")
    paper.combo.setCurrentIndex(paper.combo.findData(label))
    tip = paper.margin.toolTip()
    assert f"quer rund {across} mm" in tip and f"längs rund {along} mm" in tip, tip


def test_margin_tooltip_without_printer_strips(window):
    window.doc.label_id = "57x32mm@203"                 # anderer Hersteller: ganz bedruckbar
    paper = window.panel("paper")
    paper.refresh()
    assert paper.margin.toolTip() == "Abstand zur Papierkante ringsum"


def test_refresh_sets_length_range_of_the_label_before_the_value(window):
    """Etikett „18“ (Vorschub 14 Punkte) erlaubt kürzere Stücke als „62“ – der Wert der Datei
    darf beim Anzeigen nicht an der Grenze des vorigen Etiketts hängen bleiben."""
    paper = window.panel("paper")
    window.doc.label_id, window.doc.length_mm = "18", 16.0
    paper.refresh()
    assert paper.length.value() == 16.0
    paper.margin.setValue(2.0)
    assert window.doc.length_mm == 16.0


def test_length_field_means_the_cut_piece(window):
    paper = window.panel("paper")
    feed = 2 * 35 * 25.4 / 300
    assert paper.length.minimum() == pytest.approx(round(12.7 + feed, 1))
    assert paper.length.maximum() == pytest.approx(round(1000.0 + feed, 1), abs=0.1)
    paper.length_auto.setChecked(False)
    paper.length.setValue(50.0)
    window.render_now()
    assert window.doc.length_mm == 50.0
    assert window.image.height == round(50 * MM) - 2 * 35


@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_canvas_shows_printer_strip_before_and_after_the_print_image(window, orientation):
    paper = window.panel("paper")
    (paper.horizontal if orientation == "horizontal" else paper.vertical).setChecked(True)
    window.render_now()
    canvas = window.canvas
    outline = canvas.outline.sceneBoundingRect()
    sheet = canvas.sheet.mapRectToScene(canvas.sheet.rect())
    assert sheet.top() - outline.top() == pytest.approx(35)        # Szene-y = Bandrichtung
    assert outline.bottom() - sheet.bottom() == pytest.approx(35)
