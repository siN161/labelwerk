"""Dialog „Einstellungen“: Reiter „Allgemein“ (Standardwerte für neue Etiketten, Drucker,
Ansicht) und „Tastenkürzel“ (alle Aktionen aus ``shortcuts.ACTIONS``).

Neue Einstellung = Feld in settings.Settings + eine Zeile im passenden Abschnitt hier.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QFormLayout, QFrame, QGridLayout, QGroupBox,
                               QHBoxLayout, QHeaderView, QKeySequenceEdit, QLabel, QPushButton,
                               QScrollArea, QStyledItemDelegate, QTableWidget, QTableWidgetItem,
                               QTabWidget,
                               QVBoxLayout, QWidget)

from .. import favorites, fonts, i18n, shortcuts, zpl
from ..document import MAX_MARGIN_MM, MAX_PT, MIN_PT
from ..i18n import N_, _
from ..labels import get_label, labels_for_model
from ..printer import DEFAULT_MODEL
from ..printers import SUPPORTED_MODELS, capabilities
from ..settings import (HIDEABLE_TOOLS, Settings, restart_pending, save_settings,
                        start_tool_for, started_values, valid_host)
from . import file_dialog
from .tools import TOOLS
from .widgets import DoubleSpinBox, FontCombo, SpinBox

# englisch (N_), angezeigt wird _(…)
SCOPE_NAMES = {"global": N_("Global"), "canvas": N_("Canvas"), "edit": N_("Text editing")}
FIXED_TIP = N_("Fixed shortcut – cannot be changed")
CONFLICT_COLOR = QColor("#FF0000")
COL_ACTION, COL_SCOPE, COL_KEYS, COL_RESET = range(4)
DIALOG_SIZE = (760, 680)     # Wunschgröße: Kürzel-Tabelle mit ungekürzten Aktionsnamen
MIN_SIZE = (520, 420)        # kleiner geht nicht; Tabelle und Reiter rollen dann
_SCREEN_SHARE = 0.9          # höchstens so viel vom verfügbaren Bildschirm
_PORTABLE = QKeySequence.SequenceFormat.PortableText
_NATIVE = QKeySequence.SequenceFormat.NativeText


RESTART_NOTICE = N_("Changes take effect after a restart")
RESTART_STYLE = "color: #CC7A00; font-weight: 600;"     # wie Hinweise (QSS „warn“), auch ohne QSS


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, path: str | Path | None = None,
                 model: str = DEFAULT_MODEL, parent=None, started: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(_("Settings"))
        self.setMinimumSize(*MIN_SIZE)
        screen = (parent.screen() if parent is not None else self.screen())
        self.resize(initial_size(screen.availableGeometry().size()))
        self.path = path
        self.saved: Settings | None = None
        self._symbols = (settings.symbols_recent, settings.symbols_favorites)   # nur durchgereicht
        self._recent_files = settings.recent_files                             # nur durchgereicht
        self._printer, self._last_model = settings.printer, settings.last_model   # nur durchgereicht
        self._printer_options = settings.printer_options                          # nur durchgereicht
        self._last_tool = settings.last_tool                                      # nur durchgereicht
        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)
        general = QWidget()
        scroll = QScrollArea()                   # Drucker-Liste macht den Reiter hoch: rollen statt quetschen
        scroll.setWidget(general)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tabs.addTab(scroll, _("General"))
        layout = QVBoxLayout(general)

        form = self._section(layout, _("New label"))
        self.label = QComboBox()
        for lbl in labels_for_model(model):
            self.label.addItem(lbl.description, lbl.id)
        if self.label.findData(settings.label_id) < 0:    # anderer Drucker: nicht still ersetzen
            self.label.addItem(_("{label} – does not fit the {model}").format(
                label=get_label(settings.label_id).description, model=model), settings.label_id)
        self.label.setCurrentIndex(max(0, self.label.findData(settings.label_id)))
        form.addRow(_("Label"), self.label)
        self.orientation = QComboBox()
        self.orientation.addItem(_("Horizontal"), "horizontal")
        self.orientation.addItem(_("Vertical"), "vertical")
        self.orientation.setCurrentIndex(self.orientation.findData(settings.orientation))
        form.addRow(_("Orientation"), self.orientation)
        self.margin = DoubleSpinBox()
        self.margin.setSuffix(" mm")
        self.margin.setDecimals(1)
        self.margin.setSingleStep(0.5)
        self.margin.setRange(0.0, MAX_MARGIN_MM)
        self.margin.setValue(settings.margin_mm)
        form.addRow(_("Margins"), self.margin)
        row = QHBoxLayout()
        self.font_auto = QCheckBox(_("Automatic"))
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
        form.addRow(_("Font size"), row)
        self.font_family = FontCombo(fonts.families(all=settings.fonts_all))
        self.font_family.set_current_family(settings.font_family)
        # Nicht installierte Schrift nicht stillschweigend durch Ersatz überschreiben
        self._orig_family = settings.font_family
        self._family_touched = False
        self.font_family.family_chosen.connect(self._family_changed)
        form.addRow(_("Font"), self.font_family)
        self.fonts_all = QCheckBox(_("Show all fonts"))
        self.fonts_all.setToolTip(_("Also copies, symbol fonts and fonts without German characters "
                                    "– otherwise only fonts that can write German"))
        self.fonts_all.setChecked(settings.fonts_all)
        self.fonts_all.toggled.connect(
            lambda on: self.font_family.set_families(fonts.families(all=on)))
        form.addRow(self.fonts_all)
        self.start_favorite = QComboBox()
        self.start_favorite.addItem(_("Empty label"), None)
        for favorite in favorites.favorites():
            self.start_favorite.addItem(favorite.name, favorite.name)
        if settings.start_favorite and self.start_favorite.findData(settings.start_favorite) < 0:
            # gelöscht oder umbenannt: sichtbar lassen, nicht still auf „leer“ setzen
            self.start_favorite.addItem(_("{name} (missing)").format(name=settings.start_favorite),
                                        settings.start_favorite)
        self.start_favorite.setCurrentIndex(max(0, self.start_favorite.findData(settings.start_favorite)))
        self.start_favorite.setToolTip(_("Label labelwerk starts with (favorite as a template)"))
        form.addRow(_("At startup"), self.start_favorite)

        form = self._section(layout, _("Inserting images"))
        self.image_crop = QCheckBox(_("Crop automatically (without crop marks and blank space)"))
        self.image_crop.setChecked(settings.image_crop)
        form.addRow(self.image_crop)
        self.image_rotate = QCheckBox(_("Rotate if the image only fits 1:1 when rotated"))
        self.image_rotate.setToolTip(_("Off: images that are too large are reduced – saves tape"))
        self.image_rotate.setChecked(settings.image_rotate)
        form.addRow(self.image_rotate)
        self.image_mode = QComboBox()
        self.image_mode.addItem(_("Line art"), "line")
        self.image_mode.addItem(_("Photo"), "photo")
        self.image_mode.setCurrentIndex(max(0, self.image_mode.findData(settings.image_mode)))
        self.image_mode.setToolTip(_("Conversion of new images (symbols stay line art)"))
        form.addRow(_("Conversion"), self.image_mode)
        self.image_threshold = SpinBox()
        self.image_threshold.setRange(0, 255)
        self.image_threshold.setValue(settings.image_threshold)
        self.image_threshold.setToolTip(_("Threshold of new images – higher = darker"))
        form.addRow(_("Threshold"), self.image_threshold)

        form = self._section(layout, _("Printer"))
        self.check_media = QCheckBox(_("Check the roll at startup and when the printer is switched on"))
        self.check_media.setChecked(settings.check_media_on_start)
        form.addRow(self.check_media)
        self.printer_model = _model_combo(_("Automatic (detected)"))
        self.printer_model.setCurrentIndex(max(0, self.printer_model.findData(settings.printer_model)))
        self.printer_model.setToolTip(_("Only needed if labelwerk does not recognize the model "
                                        "(then applies, and without a connected printer)"))
        form.addRow(_("Printer model"), self.printer_model)
        self.zebra_dpi = QComboBox()
        self.zebra_dpi.addItem(_("Automatic (detected)"), 0)
        for dpi in zpl.RESOLUTIONS:
            self.zebra_dpi.addItem(f"{dpi} dpi", dpi)
        self.zebra_dpi.setCurrentIndex(max(0, self.zebra_dpi.findData(settings.zebra_dpi)))
        self.zebra_dpi.setToolTip(_("Resolution of Zebra printers on USB, in case labelwerk does "
                                    "not detect it correctly (otherwise 203 dpi)"))
        form.addRow(_("Zebra resolution"), self.zebra_dpi)
        self.cups_all = QCheckBox(_("Show all CUPS printers (office printers too)"))
        self.cups_all.setToolTip(_("Off: queues with office paper (A4, Letter …) do not appear in "
                                   "the printer menu"))
        self.cups_all.setChecked(settings.cups_all)
        form.addRow(self.cups_all)
        self.network = QTableWidget(0, 3)
        self.network.setHorizontalHeaderLabels([_("Name"), _("Address"), _("Model")])
        self.network.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.network.verticalHeader().hide()
        self.network.setMinimumHeight(110)
        for entry in settings.network_printers:
            self._add_network(entry["name"], entry["host"], entry["model"])
        buttons = QHBoxLayout()
        self.add_network = QPushButton(_("ADD"))
        self.add_network.clicked.connect(lambda: self._add_network("", "", "QL-720NW"))
        self.remove_network = QPushButton(_("REMOVE"))
        self.remove_network.clicked.connect(
            lambda: self.network.removeRow(self.network.currentRow())
            if self.network.currentRow() >= 0 else None)
        buttons.addWidget(self.add_network)
        buttons.addWidget(self.remove_network)
        buttons.addStretch()
        box = QVBoxLayout()
        box.addWidget(self.network)
        box.addLayout(buttons)
        form.addRow(_("Network printers"), box)

        form = self._section(layout, _("View"))
        self.zoom = SpinBox()
        self.zoom.setSuffix(" %")
        self.zoom.setRange(25, 400)
        self.zoom.setSingleStep(10)
        self.zoom.setValue(settings.start_zoom)
        form.addRow(_("Start zoom"), self.zoom)
        self.start_tool = QComboBox()
        self.start_tool.addItem(_("Last used"), "last")
        for tool in TOOLS:
            self.start_tool.addItem(_(tool.title), tool.key)
        self.start_tool.setCurrentIndex(max(0, self.start_tool.findData(settings.start_tool)))
        form.addRow(_("Tab at startup"), self.start_tool)
        # Reiter in der Leiste: DATEI und PAPIER immer (dort wird das Etikett gewählt)
        self.tool_boxes: dict[str, QCheckBox] = {}
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        for index, tool in enumerate(TOOLS):
            box = QCheckBox(_(tool.title))
            box.setChecked(tool.key not in settings.hidden_tools)
            if tool.key not in HIDEABLE_TOOLS:
                box.setChecked(True)
                box.setEnabled(False)
            self.tool_boxes[tool.key] = box
            box.toggled.connect(lambda _on=False, key=tool.key: self._tool_box_toggled(key))
            grid.addWidget(box, index // 2, index % 2)
        form.addRow(_("Tabs in the toolbar"), grid)
        self.tools_note = QLabel(_("Series still appears when the label has a series or the "
                                   "printer offers cut options."))
        self.tools_note.setObjectName("note")
        self.tools_note.setWordWrap(True)
        form.addRow(self.tools_note)
        self._enable_start_tools()
        self.theme = QComboBox()
        self.theme.addItem("RawBlock", "rawblock")
        self.theme.addItem(_("Classic"), "classic")
        self.theme.setCurrentIndex(max(0, self.theme.findData(settings.theme)))
        form.addRow(_("Theme"), self.theme)
        self.system_file_dialog = QCheckBox(_("Use the file dialog of the system"))
        self.system_file_dialog.setToolTip(_("Dialog of the desktop instead of the labelwerk dialog "
                                             "with preview (takes effect after a restart)"))
        self.system_file_dialog.setChecked(settings.system_file_dialog)
        if not file_dialog.system_dialog_available():         # Qt-Plugin fehlt: nur eigener Dialog
            self.system_file_dialog.setEnabled(False)
            self.system_file_dialog.setToolTip(_("Not available: this Qt installation has no "
                                                 "module for the file dialog of the system"))
        form.addRow(self.system_file_dialog)
        self.language = QComboBox()
        system = i18n.system_language()
        self.language.addItem(_("Automatic (system language: {language})").format(
            language=i18n.NAMES.get(system, system)), "")
        for code in i18n.available():
            self.language.addItem(i18n.NAMES.get(code, code), code)
        self.language.setCurrentIndex(max(0, self.language.findData(settings.language)))
        form.addRow(_("Language"), self.language)
        # Einstellungen, die erst nach einem Neustart wirken: farbiger Hinweis neben SPEICHERN
        # (unten im Fenster – sichtbar in jedem Reiter), sobald eine davon geändert ist
        self._started = started if started is not None else started_values(settings)
        self.restart_hint = QLabel(_(RESTART_NOTICE))
        self.restart_hint.setObjectName("restartNotice")
        self.restart_hint.setStyleSheet(RESTART_STYLE)
        self.restart_hint.setWordWrap(True)
        self.restart_hint.hide()
        self.language.currentIndexChanged.connect(self._update_restart_hint)
        self.zoom.valueChanged.connect(self._update_restart_hint)
        self.start_tool.currentIndexChanged.connect(self._update_restart_hint)
        self.system_file_dialog.toggled.connect(self._update_restart_hint)

        hint = QLabel(_("“New label” applies to new labels, start zoom, tab at startup, file dialog "
                        "and language from the next start, everything else immediately."))
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
        footer = QHBoxLayout()
        footer.addWidget(self.restart_hint, 1)
        footer.addWidget(buttons)
        outer.addLayout(footer)
        self._update_restart_hint()
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
        self.tabs.addTab(page, _("Shortcuts"))
        layout = QVBoxLayout(page)
        hint = self.shortcut_hint = QLabel(
            _("Click a row and press the new key combination. Esc cancels, ✕ in the field removes "
              "the shortcut. Esc, Enter and Tab cannot be assigned here (they operate the table)."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.key_hint = self._error_label()          # verworfene Eingabe
        layout.addWidget(self.key_hint)
        self._keys = shortcuts.effective(overrides)       # Aktions-ID → Kürzel (Qt-Format)
        self._rows = [a.id for a in shortcuts.ACTIONS]
        table = self.shortcut_table = QTableWidget(len(self._rows), 4)
        table.setHorizontalHeaderLabels([_("Action"), _("Scope"), _("Shortcut"), ""])
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
            for column, text in ((COL_ACTION, _(entry.name)),
                                 (COL_SCOPE, _(SCOPE_NAMES[entry.scope]))):
                item = QTableWidgetItem(text)
                item.setFlags(fixed)
                table.setItem(row, column, item)
            item = QTableWidgetItem()
            if entry.fixed:
                item.setFlags(fixed)
                item.setToolTip(_(FIXED_TIP))
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
        self.reset_all = QPushButton(_("Reset all"))
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
        self.key_hint.setText(_("“{keys}” is not a valid shortcut – “{action}” stays unchanged.")
                              .format(keys=_native(seq) or seq,
                                      action=_(shortcuts.action(action_id).name)))
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
        button = QPushButton(_("Default"))
        button.setObjectName("tableButton")
        button.setToolTip(_("Default: {keys}").format(keys=_native(default) or _("no shortcut")))
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
        clashing = {action_id for _seq, ids in found for action_id in ids}
        for row, action_id in enumerate(self._rows):
            color = CONFLICT_COLOR if action_id in clashing else None
            for column in (COL_ACTION, COL_SCOPE, COL_KEYS):
                self.shortcut_table.item(row, column).setData(Qt.ItemDataRole.ForegroundRole, color)
        lines = [f"{_native(seq)}: " + ", ".join(_(shortcuts.action(i).name) for i in ids)
                 for seq, ids in found]
        self.conflict_hint.setText(_("Shortcuts assigned twice – change one to save:") + "\n"
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
                self.error.setText(_("Network printer {name}: address “{host}” invalid – only an "
                                     "IP address or name, without “tcp://” and port").format(
                                         name=name or row + 1, host=host))
                self.error.show()
                return None
            entries.append({"name": name, "host": host,
                            "model": self.network.cellWidget(row, 2).currentData()})
        return entries

    def _family_changed(self, _family) -> None:
        self._family_touched = True

    def _hidden_tools(self) -> list[str]:
        return [key for key, box in self.tool_boxes.items()
                if key in HIDEABLE_TOOLS and not box.isChecked()]

    def _enable_start_tools(self) -> None:
        """„Reiter beim Start“: ausgeblendete Reiter gesperrt (gekoppelt an die Häkchen)."""
        model = self.start_tool.model()
        for key, box in self.tool_boxes.items():
            model.item(self.start_tool.findData(key)).setEnabled(box.isChecked())

    def _tool_box_toggled(self, key: str) -> None:
        """Häkchen eines Reiters: Start-Reiter mitsperren; der gewählte Start-Reiter ist gerade
        ausgeblendet worden → „Zuletzt benutzter“."""
        self._enable_start_tools()
        if not self.tool_boxes[key].isChecked() and self.start_tool.currentData() == key:
            self.start_tool.setCurrentIndex(self.start_tool.findData("last"))
        self._update_restart_hint()             # wirksamer Start-Reiter hängt an den Häkchen

    def restart_needed(self) -> bool:
        """Wirkt eine gewählte Einstellung erst nach einem Neustart anders als jetzt? (Liest nur die
        Felder der Neustart-Einstellungen – keine Prüfung anderer Felder.)"""
        return restart_pending({"language": self.language.currentData(),
                                "start_zoom": self.zoom.value(),
                                "start_tool": start_tool_for(self.start_tool.currentData(),
                                                             self._hidden_tools()),
                                "system_file_dialog": self.system_file_dialog.isChecked()},
                               self._started)

    def _update_restart_hint(self) -> None:
        self.restart_hint.setVisible(self.restart_needed())

    def values(self) -> Settings:
        return Settings(
            label_id=self.label.currentData(),
            orientation=self.orientation.currentData(),
            margin_mm=self.margin.value(),
            font_size_pt=None if self.font_auto.isChecked() else self.font_size.value(),
            font_family=(self.font_family.current_family() if self._family_touched
                         else self._orig_family),
            fonts_all=self.fonts_all.isChecked(),
            check_media_on_start=self.check_media.isChecked(),
            start_zoom=self.zoom.value(),
            start_tool=start_tool_for(self.start_tool.currentData(), self._hidden_tools()),
            last_tool=self._last_tool,
            hidden_tools=self._hidden_tools(),
            theme=self.theme.currentData(),
            system_file_dialog=self.system_file_dialog.isChecked(),
            image_crop=self.image_crop.isChecked(),
            image_rotate=self.image_rotate.isChecked(),
            image_mode=self.image_mode.currentData(),
            image_threshold=self.image_threshold.value(),
            symbols_recent=list(self._symbols[0]),
            symbols_favorites=list(self._symbols[1]),
            recent_files=list(self._recent_files),
            start_favorite=self.start_favorite.currentData(),
            printer=self._printer,
            printer_model=self.printer_model.currentData(),
            last_model=self._last_model,
            printer_options=dict(self._printer_options),
            zebra_dpi=self.zebra_dpi.currentData(),
            cups_all=self.cups_all.isChecked(),
            language=self.language.currentData(),
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
        combo.addItem(model if capabilities(model).tested
                      else _("{model} – untested").format(model=model), model)
    if zebra:
        for dpi in zpl.RESOLUTIONS:
            combo.addItem(_("Zebra (ZPL) {dpi} dpi – untested").format(dpi=dpi),
                          zpl.model_for(dpi))
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
