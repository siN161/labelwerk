"""Rückgängig/Wiederherstellen: Dokument-Schnappschüsse (Etappe 3d-1)."""
from labelwerk.document import Document, TextObject
from labelwerk.gui.history import LIMIT, History, restore


def _doc(text="A"):
    return Document("62", objects=[TextObject(text)])


def _texts(doc):
    return [obj.text for obj in doc.objects]


def test_undo_and_redo_step_through_pushed_states():
    doc = _doc("A")
    history = History(doc)
    assert not history.can_undo() and not history.can_redo()
    doc.objects[0] = TextObject("B")
    history.push(doc)
    doc.objects[0] = TextObject("C")
    history.push(doc)
    assert history.can_undo() and not history.can_redo()
    assert _texts(history.undo(doc)) == ["B"]
    assert _texts(history.undo(_doc("B"))) == ["A"]
    assert history.undo(_doc("A")) is None
    assert history.can_redo()
    assert _texts(history.redo(_doc("A"))) == ["B"]
    assert _texts(history.redo(_doc("B"))) == ["C"]
    assert history.redo(_doc("C")) is None


def test_push_without_change_is_no_step():
    doc = _doc()
    history = History(doc)
    assert history.push(doc) is False
    assert not history.can_undo()


def test_undo_commits_pending_changes_first():
    """Noch nicht festgehaltene Änderungen (z. B. Tippen) werden selbst ein Schritt."""
    doc = _doc("A")
    history = History(doc)
    doc.objects[0] = TextObject("A getippt")
    assert history.can_undo(doc) and not history.can_undo()
    assert _texts(history.undo(doc)) == ["A"]
    assert _texts(history.redo(_doc("A"))) == ["A getippt"]


def test_new_change_after_undo_discards_redo():
    doc = _doc("A")
    history = History(doc)
    history.push(_doc("B"))
    history.undo(_doc("B"))
    history.push(_doc("C"))
    assert not history.can_redo()
    assert history.redo(_doc("C")) is None
    assert _texts(history.undo(_doc("C"))) == ["A"]


def test_pending_change_blocks_redo():
    history = History(_doc("A"))
    history.push(_doc("B"))
    history.undo(_doc("B"))
    assert history.can_redo(_doc("A"))
    assert not history.can_redo(_doc("A neu"))
    assert history.redo(_doc("A neu")) is None


def test_history_keeps_at_most_limit_steps():
    history = History(_doc("0"))
    for i in range(1, LIMIT + 11):
        history.push(_doc(str(i)))
    steps = 0
    current = _doc(str(LIMIT + 10))
    while (previous := history.undo(current)) is not None:
        current = previous
        steps += 1
    assert LIMIT == 100 and steps == LIMIT
    assert _texts(current) == ["10"]


def test_consecutive_pushes_with_same_merge_key_form_one_step():
    history = History(_doc("A"))
    history.push(_doc("B"), merge="nudge")
    history.push(_doc("C"), merge="nudge")
    history.push(_doc("D"), merge="nudge")
    assert _texts(history.undo(_doc("D"))) == ["A"]
    history.redo(_doc("A"))
    history.push(_doc("E"), merge="nudge")       # nach Rückgängig/Wiederherstellen: neuer Schritt
    assert _texts(history.undo(_doc("E"))) == ["D"]


def test_different_merge_key_starts_new_step():
    history = History(_doc("A"))
    history.push(_doc("B"), merge=("nudge", (0,)))
    history.push(_doc("C"), merge=("nudge", (1,)))
    assert _texts(history.undo(_doc("C"))) == ["B"]


def test_snapshots_are_independent_copies():
    doc = _doc("A")
    history = History(doc)
    doc.objects[0].paragraphs[0].spans[0].text = "verändert"   # Original nach dem Schnappschuss
    history.push(doc)
    restored = history.undo(doc)
    assert _texts(restored) == ["A"]
    restored.objects[0].paragraphs[0].spans[0].text = "kaputt"     # Kopie, nicht der Verlauf
    assert _texts(history.redo(_doc("A"))) == ["verändert"]
    assert _texts(history.undo(_doc("verändert"))) == ["A"]


def test_changed_signal_reports_every_change(qtbot):
    history = History(_doc("A"))
    with qtbot.waitSignal(history.changed, timeout=100):
        history.push(_doc("B"))
    with qtbot.waitSignal(history.changed, timeout=100):
        history.undo(_doc("B"))
    with qtbot.waitSignal(history.changed, timeout=100):
        history.reset(_doc("X"))
    assert not history.can_undo() and not history.can_redo()


def test_restore_keeps_the_document_object():
    """Panels halten das Dokument fest – Rückgängig ändert es an Ort und Stelle."""
    doc = Document("62", length_mm=40, objects=[TextObject("A")])
    snapshot = Document("29", orientation="horizontal", margin_mm=3,
                        objects=[TextObject("B"), TextObject("C")])
    restore(doc, snapshot)
    assert doc == snapshot and doc is not snapshot
    assert (doc.label_id, doc.length_mm, doc.orientation) == ("29", None, "horizontal")


# --- Auswahl je Stand -------------------------------------------------------------
def test_undo_and_redo_restore_selection_of_each_state():
    history = History(_doc("A"))
    history.push(_doc("A"), selection=[0])          # nur Auswahl geändert: kein Schritt
    assert not history.can_undo()
    history.push(_doc("B"), selection=[1])
    history.undo(_doc("B"), selection=[1])
    assert history.selection == [0]
    history.redo(_doc("A"), selection=[0])
    assert history.selection == [1]


def test_selection_is_a_copy():
    history = History(_doc("A"))
    chosen = [0]
    history.push(_doc("B"), selection=chosen)
    chosen.append(1)
    assert history.selection == [0]


def test_reset_clears_selection():
    history = History(_doc("A"))
    history.push(_doc("B"), selection=[0])
    history.reset(_doc("C"))
    assert history.selection == []


def test_select_updates_current_state_only_without_pending_change():
    history = History(_doc("A"))
    history.select(_doc("A"), [0])
    history.select(_doc("A geändert"), [5])         # gehört schon zum nächsten Schritt
    history.push(_doc("B"), selection=[1])
    history.undo(_doc("B"), selection=[1])
    assert history.selection == [0]


def test_merged_series_back_to_start_leaves_no_step():
    history = History(_doc("A"))
    history.push(_doc("B"))
    history.push(_doc("C"), merge="nudge")
    history.push(_doc("B"), merge="nudge", selection=[0])   # Pfeile hin und zurück
    assert history.selection == [0]
    assert _texts(history.undo(_doc("B"))) == ["A"]          # nur der Schritt davor
    assert history.undo(_doc("A")) is None


def test_after_dropped_series_same_merge_key_starts_new_step():
    history = History(_doc("A"))
    history.push(_doc("B"), merge="nudge")
    history.push(_doc("A"), merge="nudge")
    assert not history.can_undo()
    history.push(_doc("C"), merge="nudge")
    assert _texts(history.undo(_doc("C"))) == ["A"]


def test_is_current():
    history = History(_doc("A"))
    assert history.is_current(_doc("A")) and not history.is_current(_doc("B"))


def test_amend_replaces_current_state_without_step():
    history = History(_doc("A"))
    history.push(_doc("B"))
    history.amend(_doc("B2"), [0])
    assert history.is_current(_doc("B2")) and history.selection == [0]
    assert _texts(history.undo(_doc("B2"))) == ["A"]
    assert _texts(history.redo(_doc("A"))) == ["B2"]


def test_amend_back_to_previous_state_drops_the_step():
    """Leerer Textrahmen angelegt und wieder verlassen: kein Schritt bleibt übrig."""
    history = History(_doc("A"))
    history.push(_doc("X"), merge="nudge")
    history.push(_doc("A+leer"))
    history.amend(_doc("X"), [1])
    assert history.is_current(_doc("X")) and history.selection == [1]
    assert _texts(history.undo(_doc("X"))) == ["A"]
    history.redo(_doc("A"))
    history.push(_doc("Y"), merge="nudge")                  # keine Zusammenfassung über den Wegfall
    assert _texts(history.undo(_doc("Y"))) == ["X"]
