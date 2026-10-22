import json
import os
import shutil
import tempfile
import uuid

from qgis.core import QgsProject, QgsMessageLog, Qgis
from qgis.PyQt.QtCore import QSettings, Qt, QEvent, QTimer
from qgis.PyQt.QtGui import QIcon, QPalette, QColor, QFont
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QScrollArea,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
)
from qgis.gui import QgsOptionsPageWidget, QgsOptionsWidgetFactory

from .language import tr

from .config import (
    BUNDLED_CONFIG_DIR,
    CONFIG_FILE_KEY,
    DEVELOPER_MODE_KEY,
    ENABLED_KEY,
    ROOT_FOLDER_KEY,
    get_file_suffix_styles,
    match_file_suffix_rule,
    get_file_suffix_style_path,
    get_root_folder,
    get_external_templates,
    resolve_external_template_path,
    portable_external_template_path,
    get_config_file,
    load_external_config,
    get_configuration_name,
    get_developer_code,
    get_folder_name,
    get_restyle_templates,
    get_inactive_templates,
    list_project_templates,
    get_style_rules,
    get_personal_style_rules,
    save_personal_style_rules,
    config_signature,
    resolve_style_path,
    portable_style_path,
    save_configuration_settings,
)


_TEMPLATE_KIND_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_TEMPLATE_PATH_ROLE = int(Qt.ItemDataRole.UserRole) + 2


class _TemplateNameDelegate(QStyledItemDelegate):
    """Keep the original template name readable, with a muted external tag.

    Only developer settings shows this tag; the New from Template menu
    continues to use the normal, unmodified template labels.
    """

    def paint(self, painter, option, index):
        if index.data(_TEMPLATE_KIND_ROLE) != 'external':
            super().paint(painter, option, index)
            return

        display = QStyleOptionViewItem(option)
        self.initStyleOption(display, index)
        name = display.text
        display.text = ''
        style = display.widget.style() if display.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, display, painter, display.widget)

        painter.save()
        painter.setClipRect(option.rect)
        name_font = display.font
        painter.setFont(name_font)
        name_metrics = painter.fontMetrics()
        tag_font = QFont(name_font)
        if tag_font.pointSizeF() > 0:
            tag_font.setPointSizeF(max(7.0, tag_font.pointSizeF() - 1.0))
        elif tag_font.pixelSize() > 0:
            tag_font.setPixelSize(max(9, tag_font.pixelSize() - 1))
        painter.setFont(tag_font)
        tag_metrics = painter.fontMetrics()
        tag = 'external'
        tag_width = tag_metrics.horizontalAdvance(tag)
        available = max(0, option.rect.width() - 12 - tag_width - 9)
        visible_name = name_metrics.elidedText(name, Qt.TextElideMode.ElideRight, available)
        selected = bool(display.state & QStyle.StateFlag.State_Selected)
        text_role = QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        name_color = display.palette.color(text_role)
        painter.setFont(name_font)
        painter.setPen(name_color)
        name_rect = option.rect.adjusted(5, 0, -5, 0)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, visible_name)

        name_width = name_metrics.horizontalAdvance(visible_name)
        tag_color = QColor(name_color)
        tag_color.setAlpha(125)
        painter.setFont(tag_font)
        painter.setPen(tag_color)
        tag_rect = option.rect.adjusted(5 + name_width + 9, 0, -5, 0)
        painter.drawText(tag_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tag)
        painter.restore()


class CollapsibleSection(QWidget):
    """Small arrow-header section used to keep the options page compact."""

    def __init__(self, title, parent=None, expanded=False):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self.toggle_button = QToolButton(self)
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.toggle_button.setStyleSheet("QToolButton { border: none; font-weight: 600; }")
        self.toggle_button.toggled.connect(self._set_expanded)
        outer.addWidget(self.toggle_button)

        self.content = QWidget(self)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(18, 0, 0, 6)
        self.content.setVisible(expanded)
        outer.addWidget(self.content)

    def _set_expanded(self, expanded):
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.content.setVisible(expanded)


class _StyleCoreOptionsAcceptGuard(QWidget):
    """Guard QGIS-owned OK/Apply events before native QDialog acceptance.

    This keeps the current form alive if the developer-code prompt is
    cancelled. The event filter is deliberately narrow: it only acts on
    buttons inside the QGIS Options dialog which contains this page.
    """
    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self._blocked_release = None
        self._checking = False
        self._replaying = False

    def _in_own_options(self, widget):
        parent = widget
        while parent is not None:
            if parent is self.page:
                return False  # Not the page's own internal buttons
            if isinstance(parent, QDialog):
                return parent.isAncestorOf(self.page)
            parent = parent.parentWidget() if hasattr(parent, 'parentWidget') else None
        return False

    def _preflight_save(self):
        """Persist before replaying QGIS OK/Apply; keep this method on the guard.

        The guard must not call a save method on the page; older installations
        raised AttributeError due to a class mismatch. QGIS calls apply() again
        after replay, so a one-shot flag prevents a second write.
        """
        if not self.page.isValid():
            return False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.page.apply()
            if not self.page._last_save_succeeded:
                return False
            self.page._skip_next_native_apply = True
            return True
        except Exception as exc:
            QMessageBox.warning(self.page, 'StyleCore', tr('Could not save settings: ') + str(exc))
            return False
        finally:
            QApplication.restoreOverrideCursor()

    def eventFilter(self, obj, event):
        if self._checking or self._replaying or not self.page.isVisible():
            return False
        kind = event.type()
        # Keyboard Enter can accept the QGIS dialog without clicking a button.
        if isinstance(obj, QDialog) and obj.isAncestorOf(self.page) and kind == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._checking = True
                try:
                    allowed = self._preflight_save()
                finally:
                    self._checking = False
                if not allowed:
                    return True
        if obj is self._blocked_release and kind == QEvent.Type.MouseButtonRelease:
            self._blocked_release = None
            return True
        if not isinstance(obj, QAbstractButton) or not self._in_own_options(obj):
            return False
        role = None
        parent = obj.parentWidget()
        while parent is not None and not isinstance(parent, QDialog):
            if isinstance(parent, QDialogButtonBox):
                role = parent.buttonRole(obj)
                break
            parent = parent.parentWidget()
        accept_roles = (QDialogButtonBox.ButtonRole.AcceptRole,
                        QDialogButtonBox.ButtonRole.ApplyRole,
                        QDialogButtonBox.ButtonRole.YesRole)
        label = obj.text().replace('&', '').strip().casefold()
        if role not in accept_roles and label not in ('ok', 'apply', 'anvend', 'acceptér'):
            return False
        if kind not in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
            return False
        if kind == QEvent.Type.KeyPress and event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            return False
        # Validate (including developer code) and save exactly once before
        # QGIS handles OK/Apply. Keep the event filter protected for the
        # entire modal prompt and synchronous disk write.
        self._checking = True
        try:
            allowed = self._preflight_save()
        finally:
            self._checking = False
        if not allowed:
            if kind == QEvent.Type.MouseButtonPress:
                self._blocked_release = obj
            return True
        # An intercepted modal validation/save interrupts the press/release sequence.
        # Re-issue one complete click after the prompt returns, so QGIS
        # executes the original OK or Apply action without requiring a second click.
        if kind == QEvent.Type.MouseButtonPress:
            self._blocked_release = obj
            QTimer.singleShot(0, lambda button=obj: self._finish_approved_click(button))
            return True
        return False

    def _finish_approved_click(self, button):
        if not self.page.isVisible() or not button.isEnabled():
            self.page._skip_next_native_apply = False
            return
        self._replaying = True
        try:
            button.click()
        finally:
            self._replaying = False


class StyleCoreOptionsPage(QgsOptionsPageWidget):

    def __init__(
        self,
        parent=None,
        enabled_changed_callback=None,
        root_folder_changed_callback=None,
    ):
        super().__init__(parent)

        self.enabled_changed_callback = enabled_changed_callback
        self.root_folder_changed_callback = root_folder_changed_callback
        self.loaded_config_signature = None
        self._loading_settings = False
        self._developer_unlocking = False
        self._approved_shared_fingerprint = None
        self._developer_data_loaded = False
        self._shared_defaults_cache = {}
        self._skip_next_native_apply = False
        self._last_save_succeeded = False

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        self.active_configuration_label = QLabel()
        self.active_configuration_label.setWordWrap(True)
        layout.addWidget(self.active_configuration_label)
        self.enabled_checkbox = QCheckBox(tr('Automatic styling enabled'))
        self.enabled_checkbox.setChecked(QSettings().value(ENABLED_KEY, True, type=bool))
        layout.addWidget(self.enabled_checkbox)
        personal_title = QLabel(tr("Personal Overrides"))
        personal_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(personal_title)
        self.personal_table = QTableWidget()
        self.personal_table.setColumnCount(3)
        self.personal_table.verticalHeader().setDefaultSectionSize(20)
        self.personal_table.verticalHeader().setMinimumSectionSize(18)
        self.personal_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.personal_table.setHorizontalHeaderLabels([
            tr('Layer name'), tr('Personal style'), tr('Shared default')
        ])
        self.personal_table.setMinimumHeight(110)
        self.personal_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive)
        self.personal_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.personal_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self.personal_table.setColumnWidth(0, 220)
        self.personal_table.cellDoubleClicked.connect(self.choose_personal_style_file)
        self.personal_table.cellChanged.connect(self.personal_cell_changed)
        self.personal_table.itemSelectionChanged.connect(self.update_buttons)
        layout.addWidget(self.personal_table)
        personal_buttons = QHBoxLayout()
        self.personal_add_button = QPushButton(tr('Add personal override'))
        self.personal_remove_button = QPushButton(tr('Reset to shared default'))
        self.personal_add_button.clicked.connect(self.add_personal_row)
        self.personal_remove_button.clicked.connect(self.reset_personal_row)
        self.personal_reset_all_button = QPushButton(tr("Reset all personal styles"))
        self.personal_reset_all_button.clicked.connect(self.reset_all_personal_rows)
        personal_buttons.addWidget(self.personal_add_button)
        personal_buttons.addWidget(self.personal_remove_button)
        personal_buttons.addWidget(self.personal_reset_all_button)
        personal_buttons.addStretch()
        layout.addLayout(personal_buttons)

        config_group = CollapsibleSection(tr('Configuration'), expanded=False)
        config_layout = config_group.content_layout

        # Both pasted UNC paths and locally browsed JSON files are supported.
        config_path_row = QHBoxLayout()
        self.config_path_edit = QLineEdit()
        self.config_path_edit.setPlaceholderText(
            'Shared JSON path (e.g. \\\\server\\GIS\\StyleCore\\config.json)')
        self.config_path_edit.setToolTip(tr('Paste a local path or UNC path to an existing configuration JSON'))
        self.config_path_load_button = QPushButton(tr("Load path"))
        self.config_path_load_button.clicked.connect(self.load_configuration_from_path)
        config_path_row.addWidget(self.config_path_edit)
        config_path_row.addWidget(self.config_path_load_button)
        config_layout.addLayout(config_path_row)

        config_buttons = QHBoxLayout()
        self.load_config_button = QPushButton(tr('Load configuration...'))
        self.new_config_button = QPushButton(tr('New configuration...'))
        self.load_config_button.clicked.connect(self.choose_configuration_file)
        self.new_config_button.clicked.connect(self.create_configuration_file)
        config_buttons.addWidget(self.load_config_button)
        config_buttons.addWidget(self.new_config_button)
        config_buttons.addStretch()
        config_layout.addLayout(config_buttons)
        layout.addWidget(config_group)

        developer_group = CollapsibleSection(tr('Developer'), expanded=False)
        developer_layout = developer_group.content_layout
        self.developer_group = developer_group
        developer_group.toggle_button.toggled.connect(self._load_developer_when_opened)

        self.developer_checkbox = QCheckBox(tr('Enable developer mode'))
        developer_enabled = QSettings().value(
            DEVELOPER_MODE_KEY,
            False,
            type=bool,
        )
        self.developer_checkbox.setChecked(False)
        self.developer_checkbox.toggled.connect(self.update_developer_ui)
        developer_layout.addWidget(self.developer_checkbox)
        folder_group = QGroupBox(tr('StyleCore resources'))
        folder_layout = QVBoxLayout(folder_group)

        folder_info = QLabel(
            tr('Root folder for StyleCore resources. The location normally comes from the active configuration.')

        )
        folder_info.setWordWrap(True)
        folder_layout.addWidget(folder_info)

        folder_row = QHBoxLayout()
        self.root_folder_edit = QLineEdit(get_root_folder())
        self.root_folder_button = QPushButton("...")
        self.root_folder_button.setFixedWidth(38)
        self.root_folder_button.clicked.connect(self.choose_root_folder)

        folder_row.addWidget(self.root_folder_edit)
        folder_row.addWidget(self.root_folder_button)
        folder_layout.addLayout(folder_row)

        developer_layout.addWidget(folder_group)

        template_group = QGroupBox('Templates')
        template_layout = QVBoxLayout(template_group)
        template_info = QLabel(
            'All templates are listed here. Active: show in StyleCore > New from Template. '
            'Refresh: reapply matching StyleCore styles ONLY when opened via that menu. '
            'Neither setting changes the source project or its data files.')
        template_info.setWordWrap(True)
        template_layout.addWidget(template_info)

        # One compact list for root, nested, and linked external templates.
        # External files are edited with the buttons or a double click on a row.
        self._external_template_entries = []
        self.template_table = QTableWidget()
        self.template_table.setColumnCount(3)
        self.template_table.setHorizontalHeaderLabels(['Active', 'Refresh', 'Template'])
        self.template_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.template_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.template_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.template_table.setColumnWidth(0, 28)
        self.template_table.setColumnWidth(1, 28)
        self.template_table.horizontalHeaderItem(0).setToolTip('Active: show in StyleCore > New from Template')
        self.template_table.horizontalHeaderItem(1).setToolTip('Refresh: reapply matching StyleCore styles when opened via that menu')
        self.template_table.verticalHeader().hide()
        self.template_table.verticalHeader().setDefaultSectionSize(20)
        self.template_table.verticalHeader().setMinimumSectionSize(18)
        self.template_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.template_table.setMaximumHeight(180)
        self.template_table.setAlternatingRowColors(False)
        self.template_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.template_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.template_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.template_table.setItemDelegateForColumn(2, _TemplateNameDelegate(self.template_table))
        self.template_table.cellDoubleClicked.connect(self.edit_external_template)
        self.template_table.itemSelectionChanged.connect(self.update_external_template_buttons)
        template_layout.addWidget(self.template_table)

        external_buttons = QHBoxLayout()
        external_buttons.setSpacing(6)
        self.external_add_button = QPushButton('Add external template...')
        self.external_edit_button = QPushButton('Edit selected...')
        self.external_remove_button = QPushButton('Remove selected')
        self.external_add_button.clicked.connect(self.add_external_template)
        self.external_edit_button.clicked.connect(self.edit_external_template)
        self.external_remove_button.clicked.connect(self.remove_external_template)
        external_buttons.addWidget(self.external_add_button)
        external_buttons.addWidget(self.external_edit_button)
        external_buttons.addWidget(self.external_remove_button)
        external_buttons.addStretch()
        template_layout.addLayout(external_buttons)
        developer_layout.addWidget(template_group)

        title = QLabel(tr('Shared automatic layer styles'))
        developer_layout.addWidget(title)
        style_info = QLabel(tr(
            'Edited or created mappings are saved to the configuration.'
        ))
        style_info.setWordWrap(True)
        developer_layout.addWidget(style_info)


        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.verticalHeader().setMinimumSectionSize(18)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            tr('Layer name'),
            tr('Style path'),
            tr("Status"),
            "...",
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 42)

        self.table.cellDoubleClicked.connect(self.choose_style_file)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        developer_layout.addWidget(self.table, 1)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton(tr('Add'))
        self.remove_button = QPushButton(tr('Remove'))
        self.reset_button = QPushButton(tr('Reset selected'))

        self.add_button.clicked.connect(self.add_row)
        self.remove_button.clicked.connect(self.remove_row)
        self.reset_button.clicked.connect(self.reset_row)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        developer_layout.addLayout(button_layout)

        suffix_label = QLabel(tr("File Suffix Rules"))
        developer_layout.addWidget(suffix_label)
        self.suffix_table = QTableWidget()
        self.suffix_table.setColumnCount(3)
        self.suffix_table.verticalHeader().setDefaultSectionSize(20)
        self.suffix_table.verticalHeader().setMinimumSectionSize(18)
        self.suffix_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.suffix_table.setHorizontalHeaderLabels([tr("Suffix"), tr("File type"), tr("QML file")])
        self.suffix_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.suffix_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.suffix_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.suffix_table.setMinimumHeight(105)
        self.suffix_table.setToolTip(tr("Enter a file extension such as .kml, kml or * for all file types."))
        self.suffix_table.cellDoubleClicked.connect(self.choose_suffix_style_file)
        developer_layout.addWidget(self.suffix_table)
        geo_buttons = QHBoxLayout()
        self.suffix_add_button = QPushButton(tr('Add suffix'))
        self.suffix_remove_button = QPushButton(tr("Remove suffix"))
        self.suffix_add_button.clicked.connect(lambda: self.add_suffix_row("", "", "*"))
        self.suffix_remove_button.clicked.connect(self.remove_suffix_row)
        geo_buttons.addWidget(self.suffix_add_button)
        geo_buttons.addWidget(self.suffix_remove_button)
        geo_buttons.addStretch()
        developer_layout.addLayout(geo_buttons)
        self.developer_info = QLabel(tr(
            "Saves the current styles from project layers to the "
            "corresponding QML files in the shared layer_styles folder."
        ))
        self.developer_info.setWordWrap(True)
        developer_layout.addWidget(self.developer_info)

        self.save_all_styles_button = QPushButton(tr('Save layer styles...'))
        self.save_all_styles_button.clicked.connect(self.save_selected_styles)
        developer_layout.addWidget(self.save_all_styles_button)

        layout.addWidget(developer_group)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

        self.developer_checkbox.setChecked(False)
        self.refresh_configuration_ui()
        self.load_settings(include_developer=False)
        self.update_buttons()
        self.update_developer_ui()
        self.update_shared_edit_mode()
        # The outer QGIS options dialog owns its OK and Apply buttons.
        # QGIS 3.44 does not always veto closing for custom Python pages
        # via isValid(), so intercept the user action before the dialog closes.
        self._accept_guard = _StyleCoreOptionsAcceptGuard(self)
        QApplication.instance().installEventFilter(self._accept_guard)
        self.destroyed.connect(self._remove_accept_guard)

    def _remove_accept_guard(self, *_):
        app = QApplication.instance()
        if app is not None and getattr(self, '_accept_guard', None):
            app.removeEventFilter(self._accept_guard)

    def current_root_folder(self):
        if load_external_config().get('root_mode') == 'config_dir':
            return get_root_folder()
        return self.root_folder_edit.text().strip()

    def _root_value_for_config(self):
        return '' if load_external_config().get('root_mode') == 'config_dir' else self.current_root_folder()

    def _selected_external_template(self):
        """Return (index, template-key) for a selected external row."""
        row = self.template_table.currentRow()
        if row < 0:
            return None
        item = self.template_table.item(row, 2)
        if not item or item.data(_TEMPLATE_KIND_ROLE) != 'external':
            return None
        name = item.text().strip()
        path = item.data(_TEMPLATE_PATH_ROLE)
        for index, entry in enumerate(self._external_template_entries):
            if entry['name'] == name and entry['path'] == path:
                return index, item.data(Qt.ItemDataRole.UserRole)
        return None

    def update_external_template_buttons(self):
        editable = bool(self.developer_checkbox.isChecked())
        selected = editable and self._selected_external_template() is not None
        self.external_add_button.setEnabled(editable)
        self.external_edit_button.setEnabled(selected)
        self.external_remove_button.setEnabled(selected)

    def _external_name_taken(self, name, exclude=None):
        return any(i != exclude and row['name'].casefold() == name.casefold()
                   for i, row in enumerate(self._external_template_entries))

    def add_external_template(self):
        if not self.developer_checkbox.isChecked():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, 'Select external QGIS project template',
            self.current_root_folder(), 'QGIS project (*.qgz *.qgs)')
        if not path:
            return
        name = os.path.splitext(os.path.basename(path))[0]
        if self._external_name_taken(name):
            QMessageBox.information(self, 'StyleCore',
                                    'This external name is already in use. Choose a different name.')
            name, accepted = QInputDialog.getText(self, 'External template', 'Template name:', text=name)
            if not accepted:
                return
            name = name.strip()
        if not name or self._external_name_taken(name):
            QMessageBox.warning(self, 'StyleCore', 'External template names must be unique and nonempty.')
            return
        portable = portable_external_template_path(path, root=self.current_root_folder())
        self._external_template_entries.append({'name': name, 'path': portable})
        self.load_restyle_templates(preserve_current=True)
        for row in range(self.template_table.rowCount()):
            item = self.template_table.item(row, 2)
            if item and item.data(_TEMPLATE_KIND_ROLE) == 'external' and item.text() == name:
                self.template_table.selectRow(row)
                break

    def edit_external_template(self, *_args):
        if not self.developer_checkbox.isChecked():
            return
        selected = self._selected_external_template()
        if selected is None:
            return
        index, old_key = selected
        current = self._external_template_entries[index]
        dialog = QDialog(self)
        dialog.setWindowTitle('Edit external template')
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name_edit = QLineEdit(current['name'], dialog)
        path_edit = QLineEdit(current['path'], dialog)
        browse_button = QPushButton('...', dialog)
        browse_button.setFixedWidth(38)
        path_line = QHBoxLayout()
        path_line.addWidget(path_edit)
        path_line.addWidget(browse_button)
        form.addRow('Template name:', name_edit)
        form.addRow('QGIS project (.qgs/.qgz):', path_line)
        layout.addLayout(form)

        def browse():
            start = resolve_external_template_path(path_edit.text().strip(),
                                                   root=self.current_root_folder())
            path, _ = QFileDialog.getOpenFileName(
                dialog, 'Select external QGIS project template',
                start if start else self.current_root_folder(), 'QGIS project (*.qgz *.qgs)')
            if path:
                path_edit.setText(portable_external_template_path(path, root=self.current_root_folder()))

        browse_button.clicked.connect(browse)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel, parent=dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = name_edit.text().strip()
        path = path_edit.text().strip()
        if not name or self._external_name_taken(name, exclude=index):
            QMessageBox.warning(self, 'StyleCore', 'External template names must be unique and nonempty.')
            return
        if not path:
            QMessageBox.warning(self, 'StyleCore', 'Choose a project file for the external template.')
            return
        old_active, old_refresh = self._template_selection()
        self._external_template_entries[index] = {'name': name, 'path': path}
        self.load_restyle_templates(preserve_current=True)
        # Renaming a template must not silently reset its Active/Refresh.
        for row in range(self.template_table.rowCount()):
            item = self.template_table.item(row, 2)
            if item and item.data(_TEMPLATE_KIND_ROLE) == 'external' and item.text() == name and item.data(_TEMPLATE_PATH_ROLE) == path:
                active_item = self.template_table.item(row, 0)
                refresh_item = self.template_table.item(row, 1)
                active_item.setCheckState(Qt.CheckState.Checked if old_key in old_active else Qt.CheckState.Unchecked)
                refresh_item.setCheckState(Qt.CheckState.Checked if old_key in old_refresh else Qt.CheckState.Unchecked)
                self.template_table.selectRow(row)
                break

    def remove_external_template(self):
        if not self.developer_checkbox.isChecked():
            return
        selected = self._selected_external_template()
        if selected is None:
            return
        index, _key = selected
        self._external_template_entries.pop(index)
        self.load_restyle_templates(preserve_current=True)

    def _external_templates_draft(self, validate=False):
        """Draft entries are stored separately, but displayed in ONE table."""
        items, names = [], set()
        for entry in self._external_template_entries:
            name = str(entry.get('name', '')).strip()
            path = str(entry.get('path', '')).strip()
            if not name or not path:
                raise ValueError('External templates need both a name and a project file.')
            if name.casefold() in names:
                raise ValueError('Duplicate external template name: ' + name)
            names.add(name.casefold())
            resolved = resolve_external_template_path(path, root=self.current_root_folder())
            if not resolved.lower().endswith(('.qgz', '.qgs')):
                raise ValueError('External templates must be .qgs or .qgz: ' + name)
            if validate and not os.path.isfile(resolved):
                raise ValueError('External project file not found: ' + resolved)
            if validate:
                internal_entries = list_project_templates(
                    root=self.current_root_folder(), external_templates=[])
                if any(internal['key'].casefold() == name.casefold() for internal in internal_entries):
                    raise ValueError('Name already used by an internal template: ' + name)
            items.append({'name': name, 'path': path})
        return items

    def current_style_folder(self):
        root = self.current_root_folder()
        return os.path.join(root, get_folder_name("styles")) if root else ""

    def refresh_configuration_ui(self):
        path = get_config_file()
        self.config_path_edit.setText(path or '')
        label = (get_configuration_name() or "None") if load_external_config() else tr("No configuration loaded")
        self.active_configuration_label.setText(tr("Active configuration: ") + label)
        path = get_config_file()

        # Display the active path in the editable field only; do not duplicate it.
        # Keep missing-server feedback accessible from the field tooltip.
        if path and not os.path.isfile(path):
            self.config_path_edit.setToolTip(tr("Configuration file unavailable: ") + path)
        else:
            self.config_path_edit.setToolTip(tr("Active configuration JSON path (local or UNC)"))

    def activate_configuration(self, path, config):
        settings = QSettings()
        settings.setValue(CONFIG_FILE_KEY, path)
        settings.remove(ROOT_FOLDER_KEY)

        self.root_folder_edit.setText(get_root_folder())
        self.refresh_configuration_ui()
        # Developer permission is never carried between organizations.
        self.developer_checkbox.setChecked(False)
        self._developer_data_loaded = False
        self.load_settings(include_developer=self.developer_group.toggle_button.isChecked())
        self.update_shared_edit_mode()

        if self.root_folder_changed_callback:
            self.root_folder_changed_callback()

    def load_configuration_from_path(self):
        path = self.config_path_edit.text().strip().strip('"')
        if not path:
            QMessageBox.warning(self, 'StyleCore', tr('Enter a configuration JSON path.'))
            return
        config = load_external_config(path)
        if not config:
            QMessageBox.warning(self, 'StyleCore',
                tr('The configuration path is unavailable or the JSON is invalid:') + '\n' + path)
            return
        self.activate_configuration(path, config)

    def choose_configuration_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr('Load StyleCore configuration'),
            BUNDLED_CONFIG_DIR,
            "StyleCore configuration (*.json);;JSON (*.json)",
        )
        if not path:
            return

        config = load_external_config(path)
        if not config:
            QMessageBox.warning(
                self,
                tr('Invalid configuration'),
                tr('The file could not be read as a valid StyleCore configuration.'),
            )
            return

        self.activate_configuration(path, config)

    def create_configuration_file(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('New StyleCore configuration'))
        dialog.resize(610, 310)
        layout = QVBoxLayout(dialog)

        form = QFormLayout()
        name_edit = QLineEdit(tr('My StyleCore configuration'))
        default_dir = self.current_root_folder() or os.path.expanduser('~')
        config_file_edit = QLineEdit(os.path.join(default_dir, 'stylecore_config.json'))
        config_file_row = QHBoxLayout()
        config_file_row.addWidget(config_file_edit)
        config_browse_button = QPushButton('...')
        config_browse_button.setFixedWidth(38)
        config_file_row.addWidget(config_browse_button)

        root_edit = QLineEdit(self.current_root_folder())
        root_row = QHBoxLayout()
        root_row.addWidget(root_edit)
        browse_button = QPushButton('...')
        browse_button.setFixedWidth(38)
        root_row.addWidget(browse_button)
        auto_root_checkbox = QCheckBox(tr('Use configuration file folder as resource root (recommended)'))
        auto_root_checkbox.setChecked(True)
        custom_root = [root_edit.text()]

        def selected_config_path():
            path = config_file_edit.text().strip().strip('"')
            if path and not path.lower().endswith('.json'):
                path += '.json'
            return os.path.abspath(os.path.expanduser(path)) if path else ''

        def update_root_preview():
            if auto_root_checkbox.isChecked():
                path = selected_config_path()
                root_edit.setText(os.path.dirname(path) if path else '')

        def update_root_mode(enabled):
            if enabled:
                custom_root[0] = root_edit.text()
                update_root_preview()
            else:
                root_edit.setText(custom_root[0])
            root_edit.setEnabled(not enabled)
            browse_button.setEnabled(not enabled)
            root_edit.setToolTip(tr('Root follows the configuration file folder.') if enabled
                                 else tr('Choose a resource folder independent of the JSON location.'))

        def browse_config_file():
            path, _ = QFileDialog.getSaveFileName(
                dialog,
                tr('Save StyleCore configuration'),
                selected_config_path() or os.path.join(os.path.expanduser('~'), 'stylecore_config.json'),
                'StyleCore configuration (*.json);;JSON (*.json)',
            )
            if path:
                config_file_edit.setText(path if path.lower().endswith('.json') else path + '.json')

        def browse_root():
            folder = QFileDialog.getExistingDirectory(
                dialog,
                tr('Select StyleCore root folder'),
                root_edit.text().strip(),
            )
            if folder:
                root_edit.setText(folder)
                custom_root[0] = folder

        config_browse_button.clicked.connect(browse_config_file)
        config_file_edit.textChanged.connect(lambda _: update_root_preview())
        browse_button.clicked.connect(browse_root)
        auto_root_checkbox.toggled.connect(update_root_mode)
        update_root_mode(True)

        styles_edit = QLineEdit('layer_styles')
        templates_edit = QLineEdit('template_projects')
        layouts_edit = QLineEdit('layouts')
        code_edit = QLineEdit()
        code_edit.setEchoMode(QLineEdit.EchoMode.Password)
        confirm_edit = QLineEdit()
        confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        show_code = QCheckBox(tr('Show code'))
        def toggle_code(checked):
            mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            code_edit.setEchoMode(mode)
            confirm_edit.setEchoMode(mode)
        show_code.toggled.connect(toggle_code)

        form.addRow(tr('Name:'), name_edit)
        form.addRow(tr('Configuration file:'), config_file_row)
        form.addRow('', auto_root_checkbox)
        form.addRow(tr('Root folder:'), root_row)
        form.addRow(tr('Styles folder:'), styles_edit)
        form.addRow(tr('Templates folder:'), templates_edit)
        form.addRow(tr('Print layouts folder:'), layouts_edit)
        form.addRow(tr('Developer code:'), code_edit)
        form.addRow(tr('Confirm developer code:'), confirm_edit)
        form.addRow('', show_code)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr('Save configuration'))
        def confirm_new_config():
            if not code_edit.text().strip() or code_edit.text() != confirm_edit.text():
                QMessageBox.warning(dialog, 'StyleCore', tr(
                    'Enter a developer code and confirm it with the same code.'))
                return
            path = selected_config_path()
            if not path or not os.path.isabs(config_file_edit.text().strip().strip('"')):
                QMessageBox.warning(dialog, 'StyleCore', tr('Choose an absolute configuration file path.'))
                return
            if not os.path.isdir(os.path.dirname(path)):
                QMessageBox.warning(dialog, 'StyleCore', tr('The configuration file folder does not exist.'))
                return
            if os.path.exists(path):
                QMessageBox.warning(dialog, 'StyleCore', tr('This configuration file already exists. Choose another name.'))
                return
            if not auto_root_checkbox.isChecked() and not root_edit.text().strip():
                QMessageBox.warning(dialog, 'StyleCore', tr('Root folder missing'))
                return
            dialog.accept()
        buttons.accepted.connect(confirm_new_config)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        path = selected_config_path()
        root = os.path.dirname(path) if auto_root_checkbox.isChecked() else root_edit.text().strip()
        folders = {
            "styles": styles_edit.text().strip() or "layer_styles",
            "templates": templates_edit.text().strip() or "template_projects",
            "layouts": layouts_edit.text().strip() or "layouts",
        }
        # A new configuration should be immediately usable, including its
        # resource directories. Prevent absolute/escaping subfolder names.
        for label, folder_name in folders.items():
            candidate = os.path.normpath(os.path.join(root, folder_name))
            try:
                contained = os.path.commonpath([
                    os.path.abspath(root), os.path.abspath(candidate)
                ]) == os.path.abspath(root)
            except ValueError:
                contained = False
            if os.path.isabs(folder_name) or not contained or candidate == os.path.normpath(root):
                QMessageBox.warning(self, "StyleCore", tr(
                    f"Invalid resource folder name ({label}): {folder_name}"
                ))
                return

        config = {
            "name": name_edit.text().strip() or "StyleCore",
            "config_id": str(uuid.uuid4()),
            "root_folder": "" if auto_root_checkbox.isChecked() else root,
            "root_mode": "config_dir" if auto_root_checkbox.isChecked() else "custom",
            "save_paths": "relative",
            "external_templates": [],
            "inactive_templates": [],
            "folders": folders,
            "file_suffix_styles": [],
            "restyle_on_open": [],
            "style_rules": [],
            "developer_code": code_edit.text(),
        }

        try:
            for subfolder in folders.values():
                os.makedirs(os.path.join(root, subfolder), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(config, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr('Could not save configuration'),
                str(exc),
            )
            return

        self.activate_configuration(path, config)

    def choose_root_folder(self):
        start_folder = self.current_root_folder()
        folder = QFileDialog.getExistingDirectory(
            self,
            tr('Select shared StyleCore folder'),
            start_folder,
        )

        if not folder:
            return

        self.root_folder_edit.setText(folder)
        self.load_settings()

    def get_standard_styles(self):
        styles = {}
        style_folder = self.current_style_folder()

        if not os.path.isdir(style_folder):
            return styles

        # Files assigned to suffix rules are managed by the suffix table.
        # Compare resolved file paths because the JSON may store a filename,
        # relative subfolder, or full path (including UNC paths on Windows).
        suffix_style_paths = set()
        for rule in get_file_suffix_styles():
            if not isinstance(rule, dict):
                continue
            resolved = resolve_style_path(rule.get("style_filename", ""), style_folder)
            if resolved:
                suffix_style_paths.add(os.path.normpath(os.path.abspath(resolved)).casefold())

        for filename in os.listdir(style_folder):
            if not filename.lower().endswith(".qml"):
                continue

            style_path = os.path.join(style_folder, filename)
            if os.path.normpath(os.path.abspath(style_path)).casefold() in suffix_style_paths:
                continue

            layer_name = os.path.splitext(filename)[0]
            styles[layer_name] = style_path

        return styles

    def _template_selection(self):
        """Capture template IDs, preserving subfolders and current edits."""
        active, refresh = [], []
        for row in range(self.template_table.rowCount()):
            name_item = self.template_table.item(row, 2)
            active_item = self.template_table.item(row, 0)
            refresh_item = self.template_table.item(row, 1)
            if not name_item:
                continue
            key = name_item.data(Qt.ItemDataRole.UserRole) or name_item.text().strip()
            if active_item and active_item.checkState() == Qt.CheckState.Checked:
                active.append(key)
            if refresh_item and refresh_item.checkState() == Qt.CheckState.Checked:
                refresh.append(key)
        return active, refresh

    def load_restyle_templates(self, preserve_current=False):
        """One list for all flat, nested, and separately linked templates."""
        existing_active, existing_refresh = self._template_selection() if preserve_current else ([], [])
        previous_ids = {
            (self.template_table.item(r, 2).data(Qt.ItemDataRole.UserRole)
             or self.template_table.item(r, 2).text().strip()).casefold()
            for r in range(self.template_table.rowCount())
            if self.template_table.item(r, 2)
        } if preserve_current else set()
        configured_refresh = {n.casefold() for n in get_restyle_templates()}
        configured_inactive = {n.casefold() for n in get_inactive_templates()}
        old_active = {n.casefold() for n in existing_active}
        old_refresh = {n.casefold() for n in existing_refresh}
        root = self.current_root_folder()
        external = self._external_templates_draft()
        entries = list_project_templates(root=root, external_templates=external)

        self.template_table.setRowCount(0)
        for entry in entries:
            key = entry['key']
            folded = key.casefold()
            row = self.template_table.rowCount()
            self.template_table.insertRow(row)
            name_item = QTableWidgetItem(entry['label'])
            name_item.setData(Qt.ItemDataRole.UserRole, key)
            name_item.setData(_TEMPLATE_KIND_ROLE, entry['kind'])
            name_item.setData(_TEMPLATE_PATH_ROLE, entry['relative_path'])
            name_item.setToolTip(entry['path'])
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.template_table.setItem(row, 2, name_item)
            for column, checked in (
                (0, folded in old_active if preserve_current and folded in previous_ids else folded not in configured_inactive),
                (1, folded in old_refresh if preserve_current and folded in previous_ids else folded in configured_refresh)
            ):
                check_item = QTableWidgetItem()
                check_item.setFlags((check_item.flags() | Qt.ItemFlag.ItemIsUserCheckable) & ~Qt.ItemFlag.ItemIsEditable)
                check_item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                self.template_table.setItem(row, column, check_item)
        self.update_shared_edit_mode()

    def selected_restyle_templates(self):
        return self._template_selection()[1]

    def inactive_templates_draft(self):
        active = {n.casefold() for n in self._template_selection()[0]}
        return [key for row in range(self.template_table.rowCount())
                if (item := self.template_table.item(row, 2))
                and (key := item.data(Qt.ItemDataRole.UserRole) or item.text().strip())
                and key.casefold() not in active]

    def add_suffix_row(self, suffix, path, extension="*"):
        row = self.suffix_table.rowCount()
        self.suffix_table.insertRow(row)
        self.suffix_table.setItem(row, 0, QTableWidgetItem(suffix))
        ext_item = QTableWidgetItem(extension)
        ext_item.setToolTip(tr("Type a file extension, e.g. .kml, kml or *."))
        self.suffix_table.setItem(row, 1, ext_item)
        self.suffix_table.setItem(row, 2, QTableWidgetItem(path))

    def remove_suffix_row(self):
        if self.developer_checkbox.isChecked() and self.suffix_table.currentRow() >= 0:
            self.suffix_table.removeRow(self.suffix_table.currentRow())

    def choose_suffix_style_file(self, row, column):
        if column != 2 or not self.developer_checkbox.isChecked():
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose QML"),
                                             self.current_style_folder(), "QGIS style (*.qml)")
        if path:
            self.suffix_table.setItem(row, 2, QTableWidgetItem(path))

    def reset_all_personal_rows(self):
        if not self.personal_table.rowCount():
            return
        answer = QMessageBox.question(self, "StyleCore", tr(
            'Remove all personal overrides for this configuration? Shared styles will not change.'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.personal_table.setRowCount(0)
            self.update_buttons()

    def _suffix_rules_draft(self, folder, validate=False):
        """Serialize only File Suffix Rules; no legacy GeoJSON special cases."""
        result = []
        seen = set()
        for row in range(self.suffix_table.rowCount()):
            suffix_item = self.suffix_table.item(row, 0)
            ext_item = self.suffix_table.item(row, 1)
            style_item = self.suffix_table.item(row, 2)
            suffix = suffix_item.text().strip() if suffix_item else ''
            ext = ext_item.text().strip().lower() if ext_item else ''
            raw = style_item.text().strip() if style_item else ''
            if not (suffix or ext or raw):
                continue
            if ext and ext != '*' and not ext.startswith('.'):
                ext = '.' + ext
            if ext_item is not None and ext_item.text() != ext:
                ext_item.setText(ext)
            if validate and (not suffix or not ext or not raw):
                raise ValueError(tr('Provide a suffix, file type and QML style.'))
            if not (suffix and ext and raw):
                continue
            key = (suffix.casefold(), ext.casefold())
            if validate and key in seen:
                raise ValueError(tr('Duplicate file suffix rule: ') + suffix + ext)
            seen.add(key)
            resolved = resolve_style_path(raw, folder)
            if validate and (not os.path.isfile(resolved) or not resolved.lower().endswith('.qml')):
                raise ValueError(tr('File suffix QML not found: ') + resolved)
            result.append({'suffix': suffix, 'extension': ext,
                           'style_filename': portable_style_path(resolved, folder)})
        return result

    def _shared_draft(self):
        """Canonical draft of shared settings, independent of personal overrides.

        This is used by QGIS Options isValid() BEFORE it accepts/closes
        the dialog. Merely expanding Developer never triggers a prompt.
        """
        if not self.developer_checkbox.isChecked():
            return None
        folder = self.current_style_folder()
        rules = []
        for row in range(self.table.rowCount()):
            layer_item = self.table.item(row, 0)
            style_item = self.table.item(row, 1)
            status_item = self.table.item(row, 2)
            if not layer_item or not status_item:
                continue
            status = status_item.data(Qt.ItemDataRole.UserRole) or status_item.text()
            if status in ("Standard",):
                continue
            combo = self.table.cellWidget(row, 0)
            name = combo.currentText().strip() if isinstance(combo, QComboBox) else layer_item.text().strip()
            style = style_item.text().strip() if style_item else ''
            if name and style:
                rules.append({'layer': name, 'style': portable_style_path(resolve_style_path(style, folder), folder)})
        file_rules = self._suffix_rules_draft(folder)
        return {'root_folder': self._root_value_for_config(), 'style_rules': rules,
                'restyle_on_open': self.selected_restyle_templates(),
                'file_suffix_styles': file_rules,
                'external_templates': self._external_templates_draft(),
                'inactive_templates': self.inactive_templates_draft()}

    def _shared_fingerprint(self):
        draft = self._shared_draft()
        if draft is None:
            return None
        return json.dumps(draft, ensure_ascii=False, sort_keys=True)

    def isValid(self):
        """QGIS calls this before accepting Options (and for Apply).

        Returning False stops QGIS closing the parent Options window and
        keeps unsaved fields intact when code verification is cancelled.
        """
        try:
            draft = self._shared_draft()
        except ValueError as exc:
            QMessageBox.warning(self, 'StyleCore', str(exc))
            return False
        if draft is None:
            return True
        stored = load_external_config()
        if not stored:
            QMessageBox.warning(self, 'StyleCore', tr('No valid shared configuration is loaded.'))
            return False
        baseline = {
            'root_folder': str(stored.get('root_folder', '')).strip(),
            'style_rules': get_style_rules(),
            'restyle_on_open': get_restyle_templates(),
            'file_suffix_styles': get_file_suffix_styles(),
            'external_templates': get_external_templates(),
            'inactive_templates': get_inactive_templates(),
        }
        if draft == baseline:
            self._approved_shared_fingerprint = None
            return True
        if not self.current_root_folder():
            QMessageBox.warning(self, 'StyleCore', tr('Root folder missing'))
            return False
        if self.loaded_config_signature != config_signature():
            QMessageBox.warning(self, 'StyleCore', tr('The shared configuration was changed by another user. Reload settings.'))
            return False
        if self._approved_shared_fingerprint == self._shared_fingerprint():
            return True
        if not self.confirm_developer_changes():
            return False
        self._approved_shared_fingerprint = self._shared_fingerprint()
        return True

    def confirm_developer_changes(self):
        """Ask only at save time. A wrong code never clears the form."""
        while True:
            code, ok = QInputDialog.getText(
                self, tr("Developer access"), tr("Developer code:"),
                QLineEdit.EchoMode.Password)
            if not ok:
                return False
            if code == get_developer_code():
                return True
            QMessageBox.warning(self, "StyleCore", tr('Incorrect developer code. Try again.'))

    def _load_developer_when_opened(self, expanded):
        if expanded and not self._developer_data_loaded:
            self.load_settings(include_developer=True)

    def load_settings(self, include_developer=True):
        self._loading_settings = True
        try:
            shared_config = load_external_config()
            shared_rules = get_style_rules() if not isinstance(shared_config.get('style_rules'), list) else shared_config.get('style_rules', [])
            self._shared_defaults_cache = {
                str(r.get('layer', '')).casefold(): resolve_style_path(r.get('style',''), self.current_style_folder())
                for r in shared_rules if isinstance(r, dict) and r.get('layer')
            }
            if include_developer:
                self._external_template_entries = [
                    {'name': str(entry.get('name', '')), 'path': str(entry.get('path', ''))}
                    for entry in get_external_templates()]
                self.load_restyle_templates()
            personal_rules = get_personal_style_rules()
            if include_developer:
                # Do not add file suffix rules to the shared layer-style list;
                # they are displayed/edited in self.suffix_table below.
                standard_styles = self.get_standard_styles()
                self.table.setRowCount(0)
                shared_map = {r['layer'].casefold(): r for r in shared_rules}
                for layer_name, standard_path in sorted(standard_styles.items()):
                    status = "Standard"
                    selected = shared_map.pop(layer_name.casefold(), None)
                    if selected:
                        standard_path = resolve_style_path(selected['style'], self.current_style_folder())
                        status = 'Custom'
                    self.add_table_row(layer_name, standard_path, status)
                for rule in shared_map.values():
                    self.add_table_row(rule['layer'], resolve_style_path(
                        rule['style'], self.current_style_folder()), 'User rule')
                self.suffix_table.setRowCount(0)
                for rule in get_file_suffix_styles():
                    self.add_suffix_row(str(rule.get('suffix', '')),
                        resolve_style_path(rule.get('style_filename', ''), self.current_style_folder()),
                        str(rule.get('extension', '')))
            self.personal_table.setRowCount(0)
            for rule in personal_rules:
                self.add_personal_table_row(rule['layer'], resolve_style_path(
                    rule['style'], self.current_style_folder()))
            if include_developer:
                self.loaded_config_signature = config_signature()
                self._developer_data_loaded = True
        finally:
            self._loading_settings = False
        self.update_shared_edit_mode()
        self.update_buttons()

    def shared_default_path(self, layer_name):
        if not layer_name:
            return ""
        cached = self._shared_defaults_cache.get(layer_name.casefold())
        if cached:
            return cached
        return os.path.join(self.current_style_folder(), f"{layer_name}.qml")

    def _display_style_item(self, path, default=False):
        """Show a short file name while retaining the original path as item data."""
        resolved = str(path or '').strip()
        label = os.path.basename(resolved.replace('\\', '/')) if resolved else tr("Standard")
        item = QTableWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, resolved)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setToolTip(resolved or tr('Shared default'))
        if default:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _personal_path(self, row):
        item = self.personal_table.item(row, 1)
        if not item:
            return ''
        return str(item.data(Qt.ItemDataRole.UserRole) or '').strip()

    def add_personal_table_row(self, layer_name, style_path):
        row = self.personal_table.rowCount()
        self.personal_table.insertRow(row)
        self.personal_table.setItem(row, 0, QTableWidgetItem(layer_name))
        self.personal_table.setItem(row, 1, self._display_style_item(style_path))
        self.personal_table.setItem(row, 2, self._display_style_item(
            self.shared_default_path(layer_name), default=True))

    def add_personal_row(self):
        selected = self.table.currentRow()
        name_item = self.table.item(selected, 0) if selected >= 0 else None
        layer_name = name_item.text().strip() if name_item else ""
        if layer_name:
            for row in range(self.personal_table.rowCount()):
                current = self.personal_table.item(row, 0)
                if current and current.text().strip().casefold() == layer_name.casefold():
                    self.personal_table.selectRow(row)
                    return
        if not layer_name:
            names = sorted({layer.name() for layer in QgsProject.instance().mapLayers().values()},
                           key=str.casefold)
            if names:
                layer_name, ok = QInputDialog.getItem(
                    self, tr('Select layer'), tr('Layer for personal style:'),
                    names, 0, True)
            else:
                layer_name, ok = QInputDialog.getText(
                    self, tr('Personal style'), tr("Enter layer name:"))
            if not ok or not layer_name.strip():
                return
            layer_name = layer_name.strip()
        for row in range(self.personal_table.rowCount()):
            existing = self.personal_table.item(row, 0)
            if existing and existing.text().strip().casefold() == layer_name.casefold():
                self.personal_table.selectRow(row)
                return
        self.add_personal_table_row(layer_name, "")
        self.personal_table.selectRow(self.personal_table.rowCount() - 1)
        self.update_buttons()

    def choose_personal_style_file(self, row, column):
        if column != 1:
            return
        current = self.personal_table.item(row, 1)
        start = self._personal_path(row)
        path, _ = QFileDialog.getOpenFileName(
            self, tr('Select QGIS style'), start or self.current_style_folder(),
            "QGIS style (*.qml)")
        if path:
            self.personal_table.setItem(row, 1, self._display_style_item(path))

    def personal_cell_changed(self, row, column):
        if self._loading_settings or column != 0:
            return
        name = self.personal_table.item(row, 0)
        default_item = self.personal_table.item(row, 2)
        if name and default_item:
            self.personal_table.setItem(row, 2, self._display_style_item(
                self.shared_default_path(name.text().strip()), default=True))

    def reset_personal_row(self):
        row = self.personal_table.currentRow()
        if row < 0:
            return
        self.personal_table.removeRow(row)
        self.update_buttons()

    def update_shared_edit_mode(self, *_args):
        editable = bool(self.developer_checkbox.isChecked())
        auto_root = load_external_config().get('root_mode') == 'config_dir'
        self.root_folder_edit.setText(self.current_root_folder()) if auto_root else None
        self.root_folder_edit.setReadOnly(not editable or auto_root)
        self.root_folder_button.setEnabled(editable and not auto_root)
        self.update_external_template_buttons()
        # Keep the list readable; only developers may toggle Active / Refresh.
        for row in range(self.template_table.rowCount()):
            for column in (0, 1):
                item = self.template_table.item(row, column)
                if item:
                    flags = item.flags()
                    item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled if editable
                                  else flags & ~Qt.ItemFlag.ItemIsEnabled)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.AllEditTriggers if editable
            else QAbstractItemView.EditTrigger.NoEditTriggers)
        self.suffix_table.setEditTriggers(
            QAbstractItemView.EditTrigger.AllEditTriggers if editable
            else QAbstractItemView.EditTrigger.NoEditTriggers)
        # Keep the table widgets enabled so scrollbars and mouse-wheel work.
        # Dim their content instead of calling setEnabled(False).
        for table in (self.table, self.suffix_table):
            if editable:
                table.setStyleSheet('')
            else:
                palette = table.palette()
                bg = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base).name()
                fg = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text).name()
                table.setStyleSheet(
                    'QTableWidget { background-color: %s; color: %s; }' % (bg, fg))
            for row in range(table.rowCount()):
                for column in range(table.columnCount()):
                    widget = table.cellWidget(row, column)
                    if widget is not None:
                        widget.setEnabled(editable)
        self.add_button.setEnabled(editable)
        self.suffix_add_button.setEnabled(editable)
        self.suffix_remove_button.setEnabled(editable)
        self.update_buttons()

    def add_table_row(self, layer_name, style_path, status):
        row = self.table.rowCount()
        self.table.insertRow(row)

        layer_item = QTableWidgetItem(layer_name)
        style_item = QTableWidgetItem(style_path)
        status_item = QTableWidgetItem(tr(status))
        status_item.setData(Qt.ItemDataRole.UserRole, status)

        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        if status in ("Standard", 'Custom'):
            layer_item.setFlags(layer_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.table.setItem(row, 0, layer_item)
        self.table.setItem(row, 1, style_item)
        self.table.setItem(row, 2, status_item)

        # StyleCore: Browse shared QML directly without entering cell edit mode.
        browse_button = QPushButton('...')
        browse_button.setToolTip(tr('Browse for QML style'))
        browse_button.setEnabled(self.developer_checkbox.isChecked())
        browse_button.clicked.connect(
            lambda _checked=False, button=browse_button: self._browse_shared_style(button))
        self.table.setCellWidget(row, 3, browse_button)

    def _browse_shared_style(self, button):
        # Resolve the current row at click time: deleting rows changes indices.
        if not self.developer_checkbox.isChecked():
            return
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 3) is button:
                self.choose_style_file(row, 1)
                return

    def choose_style_file(self, row, column):
        if not self.developer_checkbox.isChecked() or column != 1:
            return

        status_item = self.table.item(row, 2)
        if not status_item:
            return

        current_status = status_item.data(Qt.ItemDataRole.UserRole) or status_item.text()
        current_item = self.table.item(row, 1)
        start_path = current_item.text().strip() if current_item else ''
        if not start_path or not os.path.exists(start_path):
            start_path = self.current_style_folder()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr('Select QGIS style'),
            start_path,
            "QGIS style (*.qml)",
        )

        if not file_path:
            return

        self.table.setItem(row, 1, QTableWidgetItem(file_path))

        if current_status in ("Standard", 'Custom'):
            status_item.setText(tr('Custom'))
            status_item.setData(Qt.ItemDataRole.UserRole, 'Custom')
        else:
            status_item.setText(tr('User rule'))
            status_item.setData(Qt.ItemDataRole.UserRole, 'User rule')

        self.update_buttons()

    def add_row(self):
        if not self.developer_checkbox.isChecked():
            return
        self.add_table_row("", "", 'User rule')
        row = self.table.rowCount() - 1
        combo = QComboBox(self.table)
        combo.setEditable(True)
        combo.addItem("")
        root = QgsProject.instance().layerTreeRoot()
        names = list(dict.fromkeys(node.layer().name() for node in root.findLayers()
                                    if node.layer() is not None))
        combo.addItems(names)
        combo.currentTextChanged.connect(lambda value, item=self.table.item(row, 0):
            item.setText(value) if item is not None else None)
        self.table.setCellWidget(row, 0, combo)
        self.table.selectRow(row)
        self.update_buttons()

    def remove_row(self):
        if not self.developer_checkbox.isChecked():
            return
        row = self.table.currentRow()
        if row < 0:
            return

        status_item = self.table.item(row, 2)
        if not status_item or (status_item.data(Qt.ItemDataRole.UserRole) or status_item.text()) != 'User rule':
            return

        self.table.removeRow(row)
        self.update_buttons()

    def reset_row(self):
        if not self.developer_checkbox.isChecked():
            return
        row = self.table.currentRow()
        if row < 0:
            return

        layer_item = self.table.item(row, 0)
        status_item = self.table.item(row, 2)

        if not layer_item or not status_item or (status_item.data(Qt.ItemDataRole.UserRole) or status_item.text()) != 'Custom':
            return

        layer_name = layer_item.text()

        standard_path = os.path.join(self.current_style_folder(), f"{layer_name}.qml")
        reset_status = "Standard"
        self.table.setItem(row, 1, QTableWidgetItem(standard_path))
        status_item.setText(tr(reset_status))
        status_item.setData(Qt.ItemDataRole.UserRole, reset_status)
        self.update_buttons()

    def update_buttons(self):
        row = self.table.currentRow()
        status_item = self.table.item(row, 2) if row >= 0 else None
        status = (status_item.data(Qt.ItemDataRole.UserRole) or status_item.text()) if status_item else ""
        editable = self.developer_checkbox.isChecked()
        self.remove_button.setEnabled(editable and status == 'User rule')
        self.reset_button.setEnabled(editable and status == 'Custom')
        self.personal_remove_button.setEnabled(self.personal_table.currentRow() >= 0)

    def update_developer_ui(self, *args):
        if self.developer_checkbox.isChecked() and not self._developer_data_loaded:
            self.load_settings(include_developer=True)
        self.update_shared_edit_mode()
        self.save_all_styles_button.setEnabled(self.developer_checkbox.isChecked())

    def save_selected_styles(self):
        """Let the developer select project layers before writing to the shared folder."""
        if not self.developer_checkbox.isChecked():
            QMessageBox.warning(self, "StyleCore", tr("Enable Developer Mode first."))
            return
        style_folder = self.current_style_folder()
        if not os.path.isdir(style_folder):
            QMessageBox.warning(
                self, "StyleCore",
                tr("The style folder was not found:") + "\n" + style_folder,
            )
            return

        layers = []
        seen_layer_ids = set()
        for node in QgsProject.instance().layerTreeRoot().findLayers():
            layer = node.layer()
            if layer is None or not layer.isValid() or layer.id() in seen_layer_ids:
                continue
            seen_layer_ids.add(layer.id())
            layers.append(layer)
        if not layers:
            QMessageBox.information(self, "StyleCore", tr('The project has no valid layers.'))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Save layer styles'))
        dialog.resize(560, 500)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(tr(
            "Select the layers whose current QGIS style should be saved in the shared "
            "layer_styles folder. No layers are selected by default."
        )))
        layer_list = QListWidget(dialog)
        layer_list.setAlternatingRowColors(True)
        for layer in layers:
            item = QListWidgetItem(layer.name())
            item.setData(Qt.ItemDataRole.UserRole, layer.id())
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            layer_list.addItem(item)
        layout.addWidget(layer_list)

        controls = QHBoxLayout()
        select_all = QPushButton(tr('Select all'), dialog)
        deselect_all = QPushButton(tr('Deselect all'), dialog)
        select_all.clicked.connect(lambda: self.set_layer_checks(
            layer_list, Qt.CheckState.Checked
        ))
        deselect_all.clicked.connect(lambda: self.set_layer_checks(
            layer_list, Qt.CheckState.Unchecked
        ))
        controls.addWidget(select_all)
        controls.addWidget(deselect_all)
        controls.addStretch()
        layout.addLayout(controls)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setText(tr('Save selected'))
        save_button.setEnabled(False)
        layer_list.itemChanged.connect(lambda _item: save_button.setEnabled(
            any(layer_list.item(i).checkState() == Qt.CheckState.Checked
                for i in range(layer_list.count()))
        ))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = [
            QgsProject.instance().mapLayer(layer_list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(layer_list.count())
            if layer_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        selected = [layer for layer in selected if layer is not None]
        if not selected:
            return

        names = [layer.name().casefold() for layer in selected]
        duplicates = sorted({layer.name() for layer in selected
                             if names.count(layer.name().casefold()) > 1})
        if duplicates:
            QMessageBox.warning(
                self, tr('Duplicate layer name'),
                tr("Multiple selected layers have the same name and would overwrite the same QML. "
                'Select only one layer per name:\n') + "\n".join(duplicates),
            )
            return

        active_overrides = {r['layer'].casefold() for r in get_personal_style_rules()}
        affected = [layer.name() for layer in selected
                    if layer.name().casefold() in active_overrides]
        if affected:
            answer = QMessageBox.question(
                self, "StyleCore",
                tr('These layers have personal overrides: ') + ", ".join(affected)
                + tr('\nYou are about to save their current styles to SHARED QML files, '
                     "not to your personal overrides. Continue?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return

        while True:
            code, ok = QInputDialog.getText(
                self, tr('Confirm developer action'),
                tr('Enter the developer code to continue:'),
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                # Explicit Cancel closes the operation. The temporary layer
                # selection then disappears/reset with the dialog.
                return
            if code == get_developer_code():
                break

            QMessageBox.warning(
                self,
                tr('Incorrect code'),
                tr('Incorrect developer code. Try again or press Cancel.'),
            )

        reply = QMessageBox.question(
            self,
            tr('Confirm saving layer styles'),
            (
                tr("You are about to save {count} selected layer style(s) to the shared layer_styles folder.\n\nExisting standard QML files will be overwritten.\n\nDo you want to continue?").format(count=len(selected))
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return


        saved, failed, skipped = [], [], []
        destination_keys = {}

        for layer in selected:
            name = layer.name()

            file_rule = match_file_suffix_rule(layer.source())
            standard_path = (get_file_suffix_style_path(file_rule, style_folder)
                             if file_rule else os.path.join(style_folder, f"{name}.qml"))
            display_name = f"{name} ({file_rule['suffix']})" if file_rule else name

            # If the active configuration explicitly maps this layer to a QML
            # within its style folder, Save Styles updates that mapped file.
            # Do not overwrite external/third-party override files.
            rule_name = name
            external_path = None
            for mapping in get_style_rules():
                if str(mapping.get("layer", "")).casefold() != rule_name.casefold():
                    continue
                custom_path = resolve_style_path(mapping.get("style", ""))
                if not custom_path:
                    break
                portable = portable_style_path(custom_path, style_folder)
                if not os.path.isabs(portable):
                    standard_path = custom_path
                else:
                    external_path = custom_path
                break

            if not file_rule and (
                not name or name in (".", "..")
                or any(c in name for c in '<>:"/\\|?*')
            ) and not (os.path.isfile(standard_path) and
                       os.path.normcase(os.path.realpath(standard_path)).startswith(
                           os.path.normcase(os.path.realpath(style_folder)) + os.sep)):
                failed.append(f"{display_name}: The layer name cannot be used as a filename and has no explicit QML mapping.")
                continue

            if not standard_path:
                failed.append(
                    f"{display_name}: No style path is specified for this rule."
                )
                continue

            destination_key = os.path.normcase(os.path.normpath(standard_path))
            if destination_key in destination_keys:
                failed.append(
                    f"{display_name}: Same QML destination as "
                    f"{destination_keys[destination_key]}. Select only one of them."
                )
                continue
            destination_keys[destination_key] = display_name


            standard_exists = os.path.isfile(standard_path)
            external_exists = bool(
                external_path and os.path.isfile(external_path)
            )

            if standard_exists and external_exists:
                question = tr(
                    "This layer uses an external style override.\n\n"
                    "You are about to overwrite the standard QML file with "
                    "the current layer style.\n\n"
                    f"Standard file:\n{standard_path}\n\n"
                    f"External override:\n{external_path}\n\n"
                    'The external override file will not be changed.\n\n'
                    'Do you want to continue?'
                )

                reply = QMessageBox.question(
                    self,
                    tr('Confirm overwrite of standard style'),
                    question,
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply != QMessageBox.StandardButton.Yes:
                    skipped.append(display_name)
                    continue

            target_folder = os.path.dirname(standard_path)
            if not os.path.isdir(target_folder):
                failed.append(
                    f"{display_name}: The folder does not exist: {target_folder}"
                )
                continue

            temp_path = None

            try:
                fd, temp_path = tempfile.mkstemp(
                    prefix=".stylecore_style_",
                    suffix=".qml",
                    dir=target_folder
                )

                os.close(fd)

                message, success = layer.saveNamedStyle(temp_path)

                if not success:
                    raise RuntimeError(message)

                if standard_exists:
                    shutil.copy2(
                        standard_path,
                        standard_path + ".bak"
                    )

                os.replace(temp_path, standard_path)
                temp_path = None
                saved.append(display_name)

            except Exception as exc:
                failed.append(
                    f"{display_name}: {exc}"
                )

            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
        summary = [
            tr("Saved styles:") + f" {len(saved)}",
            tr("Skipped after confirmation:") + f" {len(skipped)}",
            tr("Errors:") + f" {len(failed)}",
        ]
        if failed:
            summary.append("\n" + tr("Errors:") + "\n" + "\n".join(failed[:10]))
        QMessageBox.information(self, tr('StyleCore – save complete'), "\n".join(summary))
        self.load_settings()

    @staticmethod
    def set_layer_checks(layer_list, state):
        for index in range(layer_list.count()):
            layer_list.item(index).setCheckState(state)

    def apply(self):
        if self._skip_next_native_apply:
            self._skip_next_native_apply = False
            return None
        self._last_save_succeeded = False
        # Personal changes and shared administrator changes are separate
        # transactions. Never write shared JSON for an ordinary colleague.
        folder = self.current_style_folder()
        personal = []
        seen = set()
        for row in range(self.personal_table.rowCount()):
            layer_item = self.personal_table.item(row, 0)
            style_item = self.personal_table.item(row, 1)
            layer = layer_item.text().strip() if layer_item else ""
            style = self._personal_path(row)
            if not layer and not style:
                continue
            if not layer or not style:
                QMessageBox.warning(self, "StyleCore", tr(
                    'Provide both layer name and QML file for each personal override.'))
                return None
            if layer.casefold() in seen:
                QMessageBox.warning(self, "StyleCore", tr(
                    'Duplicate personal override: ') + layer)
                return None
            seen.add(layer.casefold())
            resolved = resolve_style_path(style, folder)
            if not resolved.lower().endswith('.qml') or not os.path.isfile(resolved):
                # Existing broken references should not block other UI toggles.
                previous = {r['layer'].casefold(): r['style'] for r in get_personal_style_rules()}
                if previous.get(layer.casefold()) != portable_style_path(resolved, folder):
                    QMessageBox.warning(self, "StyleCore", tr(
                        'Personal QML file does not exist: ') + resolved)
                    return None
            personal.append({'layer': layer, 'style': portable_style_path(resolved, folder)})

        old_personal = get_personal_style_rules()
        personal_changed = personal != old_personal

        shared_changed = False
        if self.developer_checkbox.isChecked():
            rules = []
            seen = set()
            for row in range(self.table.rowCount()):
                layer_item = self.table.item(row, 0)
                style_item = self.table.item(row, 1)
                status_item = self.table.item(row, 2)
                if not layer_item or not status_item:
                    continue
                status = status_item.data(Qt.ItemDataRole.UserRole) or status_item.text()
                if status in ("Standard",):
                    continue
                combo = self.table.cellWidget(row, 0)
                layer = combo.currentText().strip() if isinstance(combo, QComboBox) else layer_item.text().strip()
                raw = style_item.text().strip() if style_item else ""
                if not layer or not raw:
                    continue
                if layer.casefold() in seen:
                    QMessageBox.warning(self, "StyleCore", tr(
                        'Duplicate shared style mapping: ') + layer)
                    return None
                seen.add(layer.casefold())
                path = resolve_style_path(raw, folder)
                rules.append({'layer': layer, 'style': portable_style_path(path, folder)})

            try:
                file_rules = self._suffix_rules_draft(folder, validate=True)
            except ValueError as exc:
                QMessageBox.warning(self, "StyleCore", str(exc))
                return None

            shared = load_external_config()
            old_rules = get_style_rules()
            shared_changed = (old_rules != rules or get_file_suffix_styles() != file_rules
                or get_restyle_templates() != self.selected_restyle_templates()
                or str(shared.get('root_folder', '')).strip() != self._root_value_for_config()
                or get_external_templates() != self._external_templates_draft()
                or get_inactive_templates() != self.inactive_templates_draft())
            if shared_changed:
                if not self.isValid():
                    # Leave UI edits untouched and never save shared JSON.
                    return None
                missing = []
                external = []
                for r in rules:
                    path = resolve_style_path(r['style'], folder)
                    if not os.path.isfile(path) or not path.lower().endswith('.qml'):
                        missing.append((r['layer'], path))
                    if os.path.isabs(r['style']) or r['style'].startswith('\\'):
                        external.append(r['layer'])
                if missing:
                    name, path = missing[0]
                    QMessageBox.warning(self, "StyleCore", tr(
                        'Shared QML file not found for ') + f"{name}: {path}")
                    return None
                if external:
                    answer = QMessageBox.question(self, "StyleCore", tr(
                        'External QML paths may be unavailable to colleagues: ')
                        + ', '.join(external) + tr('. Save anyway?'),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No)
                    if answer != QMessageBox.StandardButton.Yes:
                        return None
                try:
                    external_templates = self._external_templates_draft(validate=True)
                    save_configuration_settings(
                        rules, self.selected_restyle_templates(),
                        self._root_value_for_config(),
                        expected_signature=self.loaded_config_signature,
                        file_suffix_styles=file_rules,
                        external_templates=external_templates,
                        inactive_templates=self.inactive_templates_draft())
                except Exception as exc:
                    QMessageBox.warning(self, "StyleCore", tr(
                        "Could not save shared JSON. Reload settings "
                        "and check write permissions or concurrent changes: ") + str(exc))
                    return None
                self.loaded_config_signature = config_signature()
                self._approved_shared_fingerprint = None

        if personal_changed:
            try:
                save_personal_style_rules(personal)
            except Exception as exc:
                QMessageBox.warning(self, "StyleCore", tr(
                    'Could not save personal overrides: ') + str(exc))
                return None

        # Explicit user changes may be previewed on matching layers already
        # in the current project. No persistent Oracle/source-level rule is
        # created and no other saved QGIS project is changed.
        if personal_changed:
            before = {r['layer'].casefold(): r['style'] for r in old_personal}
            after = {r['layer'].casefold(): r['style'] for r in personal}
            touched = {name for name in set(before) | set(after)
                       if before.get(name) != after.get(name)}
            shared_by_name = {r['layer'].casefold(): r['style'] for r in get_style_rules()}
            missing_defaults = []
            for layer in QgsProject.instance().mapLayers().values():
                key = layer.name().casefold()
                if key not in touched:
                    continue
                if key in after:
                    path = resolve_style_path(after[key], folder)
                elif key in shared_by_name:
                    path = resolve_style_path(shared_by_name[key], folder)
                else:
                    path = os.path.join(folder, layer.name() + '.qml')
                if not os.path.isfile(path):
                    missing_defaults.append(layer.name())
                    continue
                message, success = layer.loadNamedStyle(path)
                if success:
                    layer.triggerRepaint()
                else:
                    missing_defaults.append(layer.name())
            if missing_defaults:
                QMessageBox.information(self, "StyleCore", tr(
                    "Personal rules saved. These loaded layers could not be "
                    "updated automatically (no valid default QML or loading failed): ")
                    + ', '.join(sorted(set(missing_defaults))))

        if shared_changed:
            # Refresh only layers affected by changed mappings, preserving personal overrides.
            old_map = {r['layer'].casefold(): r['style'] for r in old_rules}
            new_map = {r['layer'].casefold(): r['style'] for r in rules}
            changed_names = {name for name in old_map.keys() | new_map.keys()
                             if old_map.get(name) != new_map.get(name)}
            current_personal = {r['layer'].casefold() for r in get_personal_style_rules()}
            shared_now = {r['layer'].casefold(): r['style'] for r in get_style_rules()}
            for layer in QgsProject.instance().mapLayers().values():
                key = layer.name().casefold()
                if key not in changed_names or key in current_personal:
                    continue
                chosen = shared_now.get(key)
                path = resolve_style_path(chosen, folder) if chosen else os.path.join(folder, layer.name() + '.qml')
                if os.path.isfile(path):
                    try:
                        msg, success = layer.loadNamedStyle(path)
                        if success: layer.triggerRepaint()
                    except Exception as exc:
                        QgsMessageLog.logMessage(
                            f"Could not refresh shared style for {layer.name()}: {exc}",
                            "StyleCore", level=Qgis.MessageLevel.Warning,
                        )

        settings = QSettings()
        settings.setValue(ENABLED_KEY, self.enabled_checkbox.isChecked())
        settings.setValue(DEVELOPER_MODE_KEY, self.developer_checkbox.isChecked())
        if self.enabled_changed_callback:
            self.enabled_changed_callback(self.enabled_checkbox.isChecked())
        if shared_changed and self.root_folder_changed_callback:
            self.root_folder_changed_callback()


        self._last_save_succeeded = True
        return None
class StyleCoreOptionsFactory(QgsOptionsWidgetFactory):

    def __init__(
        self,
        enabled_changed_callback=None,
        root_folder_changed_callback=None,
    ):
        super().__init__()

        self.enabled_changed_callback = enabled_changed_callback
        self.root_folder_changed_callback = root_folder_changed_callback
        self.setTitle("StyleCore")

        plugin_dir = os.path.dirname(__file__)
        self.icon_path = os.path.join(plugin_dir, "stylecore_icon.png")

    def icon(self):
        return QIcon(self.icon_path)

    def createWidget(self, parent):
        return StyleCoreOptionsPage(
            parent,
            enabled_changed_callback=self.enabled_changed_callback,
            root_folder_changed_callback=self.root_folder_changed_callback,
        )
