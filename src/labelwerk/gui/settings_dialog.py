"""Dialog „Einstellungen“: Reiter „Allgemein“ (Standardwerte für neue Etiketten, Drucker,
Ansicht) und „Tastenkürzel“ (alle Aktionen aus ``shortcuts.ACTIONS``).

Neue Einstellung = Feld in settings.Settings + eine Zeile im passenden Abschnitt hier.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QFontComboBox, QFormLayout, QFrame, QGroupBox,
                               QHBoxLayout, QHeaderView, QKeySequenceEdit, QLabel, QPushButton,
                               QScrollArea, QStyledItemDelegate, QTableWidget, QTableWidgetItem,
                               QTabWidget,
                               QVBoxLayout, QWidget)

from .. import favorites, shortcuts, zpl
from ..document import MAX_MARGIN_MM, MAX_PT, MIN_PT
from ..labels import get_label, labels_for_model
from ..printer import DEFAULT_MODEL
from ..printers import SUPPORTED_MODELS, capabilities
from ..settings import Settings, save_settings, valid_host
from .widgets import DoubleSpinBox, SpinBox

SCOPE_NAMES = {"global": "Global", "canvas": "Arbeitsfläche", "edit": "Schreibmodus"}
FIXED_TIP = "Kürzel fest – nicht änderbar"
CONFLICT_COLOR = QColor("#FF0000")
COL_ACTION, COL_SCOPE, COL_KEYS, COL_RESET = range(4)
DIALOG_SIZE = (760, 680)     # Wunschgröße: Kürzel-Tabelle mit ungekürzten Aktionsnamen
MIN_SIZE = (520, 420)        # kleiner geht nicht; Tabelle und Reiter rollen dann
_SCREEN_SHARE = 0.9          # höchstens so viel vom verfügbaren Bildschirm
_PORTABLE = QKeySequence.SequenceFormat.PortableText
_NATIVE = QKeySequence.SequenceFormat.NativeText


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, path: str | Path | None = None,
                 model: str = DEFAULT_MODEL, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setMinimumSize(*MIN_SIZE)
        screen = (parent.screen() if parent is not None else self.screen())
        self.resize(initial_size(screen.availableGeometry().size()))
        self.path = path
        self.saved: Settings | None = None
        self._symbols = (settings.symbols_recent, settings.symbols_favorites)   # nur durchgereicht
        self._recent_files = settings.recent_files                             # nur durchgereicht
        self._printer, self._last_model = settings.printer, settings.last_model   # nur durchgereicht
        self._printer_options = settings.printer_options                          # nur durchgereicht
        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)
        general = QWidget()
        scroll = QScrollArea()                   # Drucker-Liste macht den Reiter hoch: rollen statt quetschen
        scroll.setWidget(general)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tabs.addTab(scroll, "Allgemein")
        layout = QVBoxLayout(general)

        form = self._section(layout, "Neues Etikett")
        self.label = QComboBox()
        for lbl in labels_for_model(model):
            self.label.addItem(lbl.description, lbl.id)
        if self.label.findData(settings.label_id) < 0:    # anderer Drucker: nicht still ersetzen
            self.label.addItem(f"{get_label(settings.label_id).description} – passt nicht zum "
                               f"{model}", settings.label_id)
        self.label.setCurrentIndex(max(0, self.label.findData(settings.label_id)))
        form.addRow("Etikett", self.label)
        self.orientation = QComboBox()
        self.orientation.addItem("Horizontal", "horizontal")
        self.orientation.addItem("Vertikal", "vertical")
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
        self.font_size = DoubleSpinBox()
        self.font_size.setDecimals(1)
        self.font_size.setSingleStep(0.5)
        self.font_size.setRange(MIN_PT, MAX_PT)
        self.font_size.setSuffix(" pt")
        self.font_size.setValue(settings.font_size_pt or 19)
        self.font_auto.setChecked(settings.font_size_pt is None)
        self.font_size.setEnabled(settings.font_size_pt is not None)
        self.font_auto.toggled.connect(lambda auto: self.font_size.setEnabled(not auto))
        row.addWidget(self.font_auto)
        row.addWidget(self.font_size)
        form.addRow("Schriftgröße", row)
        self.font_family = QFontComboBox()
        self.font_family.setCurrentFont(QFont(settings.font_family))
        # Nicht installierte Schrift nicht stillschweigend durch Ersatz überschreiben
        self._orig_family = settings.font_family
        self._family_touched = False
        self.font_family.currentFontChanged.connect(self._family_changed)
        form.addRow("Schriftart", self.font_family)
        self.start_favorite = QComboBox()
        self.start_favorite.addItem("Leeres Etikett", None)
        for favorite in favorites.favorites():
            self.start_favorite.addItem(favorite.name, favorite.name)
        if settings.start_favorite and self.start_favorite.findData(settings.start_favorite) < 0:
            # gelöscht oder umbenannt: sichtbar lassen, nicht still auf „leer“ setzen
            self.start_favorite.addItem(f"{settings.start_favorite} (fehlt)", settings.start_favorite)
        self.start_favorite.setCurrentIndex(max(0, self.start_favorite.findData(settings.start_favorite)))
        self.start_favorite.setToolTip("Etikett, mit dem labelwerk startet (Favorit als Vorlage)")
        form.addRow("Beim Start", self.start_favorite)

        form = self._section(layout, "Bilder einfügen")
        self.image_crop = QCheckBox("Automatisch zuschneiden (ohne Schnittmarken und Leerraum)")
        self.image_crop.setChecked(settings.image_crop)
        form.addRow(self.image_crop)
        self.image_rotate = QCheckBox("Drehen, wenn das Bild nur gedreht 1:1 passt")
        self.image_rotate.setToolTip("Aus: zu große Bilder werden verkleinert – spart Band")
        self.image_rotate.setChecked(settings.image_rotate)
        form.addRow(self.image_rotate)

        form = self._section(layout, "Drucker")
        self.check_media = QCheckBox("Rolle beim Start und beim Einschalten prüfen")
        self.check_media.setChecked(settings.check_media_on_start)
        form.addRow(self.check_media)
        self.printer_model = _model_combo("Automatisch (erkannt)")
        self.printer_model.setCurrentIndex(max(0, self.printer_model.findData(settings.printer_model)))
        self.printer_model.setToolTip("Nur nötig, wenn labelwerk das Modell nicht erkennt "
                                      "(gilt dann und ohne angeschlossenen Drucker)")
        form.addRow("Druckermodell", self.printer_model)
        self.zebra_dpi = QComboBox()
        self.zebra_dpi.addItem("Automatisch (erkannt)", 0)
        for dpi in zpl.RESOLUTIONS:
            self.zebra_dpi.addItem(f"{dpi} dpi", dpi)
        self.zebra_dpi.setCurrentIndex(max(0, self.zebra_dpi.findData(settings.zebra_dpi)))
        self.zebra_dpi.setToolTip("Auflösung der Zebra-Drucker am USB, falls labelwerk sie nicht "
                                  "richtig erkennt (sonst 203 dpi)")
        form.addRow("Zebra-Auflösung", self.zebra_dpi)
        self.network = QTableWidget(0, 3)
        self.network.setHorizontalHeaderLabels(["Name", "Adresse", "Modell"])
        self.network.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.network.verticalHeader().hide()
        self.network.setMinimumHeight(110)
        for entry in settings.network_printers:
            self._add_network(entry["name"], entry["host"], entry["model"])
        buttons = QHBoxLayout()
        self.add_network = QPushButton("HINZUFÜGEN")
        self.add_network.clicked.connect(lambda: self._add_network("", "", "QL-720NW"))
        self.remove_network = QPushButton("ENTFERNEN")
        self.remove_network.clicked.connect(
            lambda: self.network.removeRow(self.network.currentRow())
            if self.network.currentRow() >= 0 else None)
        buttons.addWidget(self.add_network)
        buttons.addWidget(self.remove_network)
        buttons.addStretch()
        box = QVBoxLayout()
        box.addWidget(self.network)
        box.addLayout(buttons)
        form.addRow("Netzwerkdrucker", box)

        form = self._section(layout, "Ansicht")
        self.zoom = SpinBox()
        self.zoom.setSuffix(" %")
        self.zoom.setRange(25, 400)
        self.zoom.setSingleStep(10)
        self.zoom.setValue(settings.start_zoom)
        form.addRow("Startzoom", self.zoom)
        self.theme = QComboBox()
        self.theme.addItem("RawBlock", "rawblock")
        self.theme.addItem("Klassisch", "classic")
        self.theme.setCurrentIndex(max(0, self.theme.findData(settings.theme)))
        form.addRow("Design", self.theme)

        hint = QLabel("„Neues Etikett“ gilt für neue Etiketten, der Startzoom ab dem nächsten "
                      "Start, alles andere sofort.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()

        self._build_shortcut_tab(settings.shortcuts)
        self.conflict_hint = self._error_label()     # Kürzel doppelt belegt (Speichern gesperrt)
        outer.addWidget(self.conflict_hint)
        self.error = self._error_label()             # Speichern fehlgeschlagen
        outer.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        outer.addWidget(buttons)
        self._check_conflicts()

    def _section(self, layout: QVBoxLayout, title: str) -> QFormLayout:
        box = QGroupBox(title.upper())
        form = QFormLayout(box)
        layout.addWidget(box)
        return form

    @staticmethod
    def _error_label() -> QLabel:
        label = QLabel()
        label.setObjectName("error")
        label.setWordWrap(True)
        label.hide()
        return label

    # --- Reiter „Tastenkürzel“ ------------------------------------------------------
    def _build_shortcut_tab(self, overrides: dict[str, str]) -> None:
        page = QWidget()
        self.tabs.addTab(page, "Tastenkürzel")
        layout = QVBoxLayout(page)
        hint = self.shortcut_hint = QLabel(
            "Zeile anklicken und die neue Tastenkombination drücken. Esc bricht ab, "
            "✕ im Feld entfernt das Kürzel. Esc, Enter und Tab lassen sich hier nicht "
            "belegen (sie bedienen die Tabelle).")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.key_hint = self._error_label()          # verworfene Eingabe
        layout.addWidget(self.key_hint)
        self._keys = shortcuts.effective(overrides)       # Aktions-ID → Kürzel (Qt-Format)
        self._rows = [a.id for a in shortcuts.ACTIONS]
        table = self.shortcut_table = QTableWidget(len(self._rows), 4)
        table.setHorizontalHeaderLabels(["Aktion", "Bereich", "Kürzel", ""])
        table.verticalHeader().hide()
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        table.setItemDelegateForColumn(COL_KEYS, _KeyDelegate(self))
        header = table.horizontalHeader()
        header.setSectionResizeMode(COL_ACTION, QHeaderView.ResizeMode.Stretch)
        for column in (COL_SCOPE, COL_KEYS, COL_RESET):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        fixed = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        for row, entry in enumerate(shortcuts.ACTIONS):
            for column, text in ((COL_ACTION, entry.name), (COL_SCOPE, SCOPE_NAMES[entry.scope])):
                item = QTableWidgetItem(text)
                item.setFlags(fixed)
                table.setItem(row, column, item)
            item = QTableWidgetItem()
            if entry.fixed:
                item.setFlags(fixed)
                item.setToolTip(FIXED_TIP)
            else:
                item.setFlags(fixed | Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, COL_KEYS, item)
            self._show_keys(entry.id)
        # gleiche Zeilenhöhe, ob mit Knopf „Standard“ oder ohne
        probe = self._reset_widget("")
        probe.ensurePolished()
        rows = table.verticalHeader()
        rows.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        rows.setDefaultSectionSize(max(rows.defaultSectionSize(), probe.sizeHint().height()))
        # Klick auf eine Zeile (oder Enter) bearbeitet ihr Kürzel
        table.cellClicked.connect(self._edit_row)
        table.cellActivated.connect(self._edit_row)
        layout.addWidget(table, 1)
        row = QHBoxLayout()
        self.reset_all = QPushButton("Alle zurücksetzen")
        self.reset_all.clicked.connect(self._reset_all)
        row.addWidget(self.reset_all)
        row.addStretch()
        layout.addLayout(row)

    def shortcut(self, action_id: str) -> str:
        """Kürzel einer Aktion, wie es gespeichert würde („“ = keins)."""
        return self._keys[action_id]

    def set_shortcut(self, action_id: str, seq: str) -> None:
        """Kürzel einer Aktion ändern (Tabelle, Standard-Knopf); Konflikte neu prüfen."""
        self._keys[action_id] = seq
        self.key_hint.hide()
        self._show_keys(action_id)
        self._check_conflicts()

    def reject_keys(self, action_id: str, seq: str) -> None:
        """Eingabe taugt nicht als Kürzel (z. B. nur Umschalt): melden, Kürzel bleibt."""
        self.key_hint.setText(f"„{_native(seq) or seq}“ ist kein gültiges Kürzel – "
                              f"„{shortcuts.action(action_id).name}“ bleibt unverändert.")
        self.key_hint.show()

    def _show_keys(self, action_id: str) -> None:
        row = self._rows.index(action_id)
        seq = self._keys[action_id]
        item = self.shortcut_table.item(row, COL_KEYS)
        item.setText(_native(seq))
        item.setData(Qt.ItemDataRole.UserRole, seq)
        # Knopf „Standard“ nur, wo das Kürzel abweicht – sonst wäre die Spalte voller grauer Knöpfe
        default = shortcuts.action(action_id).default
        if _same(seq, default):
            self.shortcut_table.removeCellWidget(row, COL_RESET)
        elif self.reset_button(action_id) is None:
            button = self._reset_widget(default)
            button.clicked.connect(lambda _=False: self.set_shortcut(action_id, default))
            self.shortcut_table.setCellWidget(row, COL_RESET, button)

    def _reset_widget(self, default: str) -> QPushButton:
        button = QPushButton("Standard")
        button.setObjectName("tableButton")
        button.setToolTip(f"Standard: {_native(default) or 'kein Kürzel'}")
        return button

    def reset_button(self, action_id: str) -> QPushButton | None:
        """Knopf „Standard“ einer Zeile (None, solange das Standardkürzel gilt)."""
        return self.shortcut_table.cellWidget(self._rows.index(action_id), COL_RESET)

    def _edit_row(self, row: int, _column: int = COL_KEYS) -> None:
        self.shortcut_table.editItem(self.shortcut_table.item(row, COL_KEYS))

    def _reset_all(self) -> None:
        for entry in shortcuts.ACTIONS:
            self._keys[entry.id] = entry.default
            self._show_keys(entry.id)
        self._check_conflicts()

    def _check_conflicts(self) -> None:
        """Doppelt belegte Kürzel rot markieren; solange es sie gibt, ist Speichern gesperrt."""
        found = shortcuts.conflicts(self._keys)
        clashing = {action_id for _, ids in found for action_id in ids}
        for row, action_id in enumerate(self._rows):
            color = CONFLICT_COLOR if action_id in clashing else None
            for column in (COL_ACTION, COL_SCOPE, COL_KEYS):
                self.shortcut_table.item(row, column).setData(Qt.ItemDataRole.ForegroundRole, color)
        lines = [f"{_native(seq)}: " + ", ".join(shortcuts.action(i).name for i in ids)
                 for seq, ids in found]
        self.conflict_hint.setText("Tastenkürzel doppelt belegt – zum Speichern eines ändern:\n"
                                   + "\n".join(lines))
        self.conflict_hint.setVisible(bool(found))
        self.save_button.setEnabled(not found)

    def _add_network(self, name: str, host: str, model: str) -> None:
        row = self.network.rowCount()
        self.network.insertRow(row)
        self.network.setItem(row, 0, QTableWidgetItem(name))
        self.network.setItem(row, 1, QTableWidgetItem(host))
        combo = _model_combo(None, zebra=True)
        combo.setCurrentIndex(max(0, combo.findData(model)))
        self.network.setCellWidget(row, 2, combo)

    def _network_values(self) -> list[dict] | None:
        """Netzwerkdrucker aus der Tabelle; leere Zeilen entfallen; None bei ungültiger Adresse
        (Hinweis steht dann im Dialog)."""
        entries = []
        for row in range(self.network.rowCount()):
            name = (self.network.item(row, 0) or QTableWidgetItem()).text().strip()
            host = (self.network.item(row, 1) or QTableWidgetItem()).text().strip()
            if not name and not host:
                continue
            if not valid_host(host):
                self.error.setText(f"Netzwerkdrucker {name or row + 1}: Adresse „{host}“ ungültig – "
                                   "nur IP-Adresse oder Name, ohne „tcp://“ und Port")
                self.error.show()
                return None
            entries.append({"name": name, "host": host,
                            "model": self.network.cellWidget(row, 2).currentData()})
        return entries

    def _family_changed(self, _font) -> None:
        self._family_touched = True

    def values(self) -> Settings:
        return Settings(
            label_id=self.label.currentData(),
            orientation=self.orientation.currentData(),
            margin_mm=self.margin.value(),
            font_size_pt=None if self.font_auto.isChecked() else self.font_size.value(),
            font_family=(self.font_family.currentFont().family() if self._family_touched
                         else self._orig_family),
            check_media_on_start=self.check_media.isChecked(),
            start_zoom=self.zoom.value(),
            theme=self.theme.currentData(),
            image_crop=self.image_crop.isChecked(),
            image_rotate=self.image_rotate.isChecked(),
            symbols_recent=list(self._symbols[0]),
            symbols_favorites=list(self._symbols[1]),
            recent_files=list(self._recent_files),
            start_favorite=self.start_favorite.currentData(),
            printer=self._printer,
            printer_model=self.printer_model.currentData(),
            last_model=self._last_model,
            printer_options=dict(self._printer_options),
            zebra_dpi=self.zebra_dpi.currentData(),
            network_printers=self._network_values() or [],
            shortcuts={action_id: seq for action_id, seq in self._keys.items()
                       if not _same(seq, shortcuts.action(action_id).default)},
        )

    def accept(self) -> None:
        if not self.save_button.isEnabled():
            return                                   # Kürzel doppelt belegt (Hinweis steht da)
        if self._network_values() is None:
            return                                   # Adresse ungültig (Hinweis steht da)
        settings = self.values()
        try:
            save_settings(settings, self.path)
        except OSError as e:
            self.error.setText(str(e))
            self.error.show()
            return                                   # Dialog bleibt offen
        self.saved = settings
        super().accept()


def _model_combo(automatic: str | None, zebra: bool = False) -> QComboBox:
    """Druckermodelle (ungeprüfte gekennzeichnet); ``automatic``: erster Eintrag mit Wert "";
    ``zebra``: auch Zebra (ZPL) je Auflösung (Netzwerkdrucker)."""
    combo = QComboBox()
    if automatic is not None:
        combo.addItem(automatic, "")
    for model in SUPPORTED_MODELS:
        combo.addItem(model if capabilities(model).tested else f"{model} – ungeprüft", model)
    if zebra:
        for dpi in zpl.RESOLUTIONS:
            combo.addItem(f"Zebra (ZPL) {dpi} dpi – ungeprüft", zpl.model_for(dpi))
    return combo


class _KeyDelegate(QStyledItemDelegate):
    """Spalte „Kürzel“: Bearbeiten mit ``QKeySequenceEdit`` – genau eine Tastenkombination,
    ✕ leert. Esc bricht ab (die Tabelle schließt den Editor ohne Übernahme)."""

    def __init__(self, dialog: SettingsDialog):
        super().__init__(dialog)
        self._dialog = dialog

    def createEditor(self, parent, option, index) -> QKeySequenceEdit:
        editor = QKeySequenceEdit(parent)
        editor.setMaximumSequenceLength(1)
        editor.setClearButtonEnabled(True)
        # Kombination erfasst: Fokus zurück an die Tabelle – das übernimmt und schließt den
        # Editor auf dem üblichen Weg (wie ein Klick daneben)
        editor.editingFinished.connect(self._dialog.shortcut_table.setFocus)
        return editor

    def setEditorData(self, editor: QKeySequenceEdit, index) -> None:
        editor.setKeySequence(QKeySequence(index.data(Qt.ItemDataRole.UserRole)))

    def setModelData(self, editor: QKeySequenceEdit, model, index) -> None:
        seq = editor.keySequence().toString(_PORTABLE)
        action_id = self._dialog._rows[index.row()]
        if shortcuts.is_well_formed(seq):
            self._dialog.set_shortcut(action_id, seq)
        else:
            self._dialog.reject_keys(action_id, seq)


def initial_size(available: QSize) -> QSize:
    """Startgröße: Wunschgröße, auf kleinen Bildschirmen höchstens 90 % davon – nie kleiner als
    die Mindestgröße."""
    width = min(DIALOG_SIZE[0], int(available.width() * _SCREEN_SHARE))
    height = min(DIALOG_SIZE[1], int(available.height() * _SCREEN_SHARE))
    return QSize(max(width, MIN_SIZE[0]), max(height, MIN_SIZE[1]))


def _native(seq: str) -> str:
    """Kürzel zum Anzeigen (z. B. „Strg+P“ mit deutscher Qt-Übersetzung)."""
    return QKeySequence(seq).toString(_NATIVE)


def _same(a: str, b: str) -> bool:
    """Gleiches Kürzel trotz anderer Schreibweise („ctrl+p“ = „Ctrl+P“)."""
    try:
        return shortcuts.normalize(a) == shortcuts.normalize(b)
    except ValueError:
        return a == b
