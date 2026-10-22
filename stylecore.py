import os
import json
import hashlib

from qgis.core import QgsProject, QgsMessageLog, QgsApplication, Qgis
from qgis.PyQt.QtGui import QIcon, QDesktopServices, QPalette
from qgis.PyQt.QtWidgets import QAction, QToolButton, QMenu, QWidgetAction, QPushButton
from qgis.PyQt.QtCore import QSettings, QTimer, Qt, QUrl, QSize

from .options import StyleCoreOptionsFactory
from .print_layouts import StyleCorePrintLayouts
from .manual_styles import StyleCoreManualStyles
from .language import tr
from .config import (
    ENABLED_KEY,
    CONFIG_FILE_KEY,
    match_file_suffix_rule,
    get_file_suffix_style_path,
    get_style_folder,
    get_root_folder,
    list_project_templates,
    get_restyle_templates,
    get_inactive_templates,
    get_style_rules,
    load_external_config,
    get_personal_style_rules,
    resolve_style_path,
    bind_legacy_style_rules,
)

class StyleCore:

    def __init__(self, iface):
        self.iface = iface
        self.options_factory = None
        self.action = None
        self.tool_button = None
        self.enabled_action = None
        self.print_manager = StyleCorePrintLayouts(iface)
        self.manual_styles = StyleCoreManualStyles(iface)
        self.main_menu = None
        self._project_loading = False
        self._project_load_skipped_count = 0
        self._registered_font_directories = set()

    def _add_external_link(self, label, url):
        """Add a subtle, keyboard-focusable menu item opening a browser link."""
        action = QWidgetAction(self.main_menu)
        button = QPushButton(label.replace('&', '&&'), self.main_menu)
        button.setFlat(True)
        # Keep link buttons from retaining keyboard focus after the menu closes.
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(QIcon(os.path.join(os.path.dirname(__file__), 'external_link.svg')))
        button.setIconSize(QSize(12, 12))
        button.setStyleSheet(
            'QPushButton { text-align: left; color: #707070; border: 0; '
            'background: transparent; padding: 3px 8px; }'
            'QPushButton:hover { background: palette(highlight); '
            'color: palette(highlighted-text); }'
        )
        def open_link():
            button.clearFocus()
            self.main_menu.hide()
            QDesktopServices.openUrl(QUrl(url))
        button.clicked.connect(open_link)
        self.main_menu.aboutToHide.connect(button.clearFocus)
        action.setDefaultWidget(button)
        self.main_menu.addAction(action)
        return action

    def _update_menu_icons(self):
        """Use a readable monochrome icon set in light and dark QGIS themes."""
        if not self.main_menu:
            return
        menu_color = self.main_menu.palette().color(QPalette.ColorRole.Window)
        variant = 'dark' if menu_color.lightness() < 128 else 'light'
        icon_folder = os.path.join(os.path.dirname(__file__), 'menu_icons')
        for action, icon_name in (
            (self.settings_action, 'settings'),
            (self.enabled_action, 'automatic'),
            (self.manual_action, 'manual'),
            (self.templates_menu.menuAction(), 'template'),
            (self.print_menu.menuAction(), 'print'),
        ):
            action.setIcon(QIcon(os.path.join(icon_folder, f'{icon_name}_{variant}.svg')))

    def initGui(self):
        bind_legacy_style_rules()

        # Register configured fonts after QGIS initializes; do not synchronize templates.
        QTimer.singleShot(250, self.register_fonts)
        QTimer.singleShot(500, self.cleanup_legacy_template_copies)
        QTimer.singleShot(900, self.warn_missing_configuration)

        project = QgsProject.instance()
        project.layersAdded.connect(self.layers_added)
        project.loadingLayer.connect(self.project_loading_started)
        project.layerLoaded.connect(self.project_layer_loaded)
        self.iface.projectRead.connect(self.project_read_complete)

        self.options_factory = StyleCoreOptionsFactory(
            enabled_changed_callback=self.set_auto_enabled,
            root_folder_changed_callback=self.register_fonts,
        )

        self.iface.registerOptionsWidgetFactory(self.options_factory)

        plugin_dir = os.path.dirname(__file__)
        icon_path = os.path.join(plugin_dir, "stylecore_icon.png")

        self.tool_button = QToolButton()
        self.tool_button.setIcon(QIcon(icon_path))
        self.tool_button.setToolTip("StyleCore")

        self.tool_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.main_menu = QMenu(self.tool_button)
        self.main_menu.setMinimumWidth(290)
        # Slightly roomier sections, without a fixed light/dark menu background.
        # Native Qt selection, text and disabled colors follow the QGIS theme.
        self.main_menu.setStyleSheet(
            'QMenu { padding: 4px 0; }'
            'QMenu::item { padding: 4px 26px 4px 12px; }'
            # Move action icons away from the left edge and towards labels;
            # keep item text, separators, and submenus in their existing positions.
            'QMenu::icon { margin-left: 9px; }'
            'QMenu::item:selected { background: palette(highlight); '
            'color: palette(highlighted-text); }'
            'QMenu::separator { height: 1px; '
            'background: rgba(128, 128, 128, 65); margin: 5px 12px; }'
        )

        self.settings_action = QAction(tr('Settings...'), self.main_menu)
        self.settings_action.triggered.connect(self.open_settings)
        self.main_menu.addAction(self.settings_action)
        self.main_menu.addSeparator()

        enabled = QSettings().value(ENABLED_KEY, True, type=bool)
        self.enabled_action = QAction(self._auto_action_text(enabled), self.main_menu)
        self.enabled_action.setCheckable(True)
        self.enabled_action.setChecked(enabled)
        self.enabled_action.toggled.connect(self.set_auto_enabled)
        self.main_menu.addAction(self.enabled_action)

        self.manual_action = QAction(tr('Manual Style Update...'), self.main_menu)
        self.manual_action.triggered.connect(self.manual_styles.show_dialog)
        self.main_menu.addAction(self.manual_action)
        self.main_menu.addSeparator()

        # Build resource lists only when the submenu opens.
        self.templates_menu = QMenu(tr('New from Template'), self.main_menu)
        self.templates_menu.aboutToShow.connect(self.refresh_templates_menu)
        self.main_menu.addMenu(self.templates_menu)

        self.print_menu = QMenu(tr('Print Layouts'), self.main_menu)
        self.print_menu.aboutToShow.connect(self.refresh_print_menu)
        self.main_menu.addMenu(self.print_menu)

        self.help_separator = self.main_menu.addSeparator()
        self.help_action = self._add_external_link(
            tr('Help & Documentation'),
            'https://vnaru42.github.io/StyleCore-Docs/',
        )
        self.issue_action = self._add_external_link(
            tr('Report an Issue'),
            'https://github.com/vnaru42/StyleCore/issues/new',
        )

        # Refresh icon contrast when the QGIS theme changes.
        self.main_menu.aboutToShow.connect(self._update_menu_icons)
        self._update_menu_icons()

        self.tool_button.setMenu(self.main_menu)
        self.tool_button.setToolTip(
            'StyleCore' if enabled else tr('StyleCore - automatic styling disabled')
        )

        self.action = self.iface.addToolBarWidget(
            self.tool_button
        )


    def register_fonts(self):
        """Register optional fonts from the active configuration's resource root.

        Font directories are QGIS-session resources: switching configurations
        does not unregister fonts already loaded from a previous root.
        """
        root = get_root_folder()
        if not root:
            return

        font_dir = os.path.abspath(os.path.join(root, "fonts"))
        if not os.path.isdir(font_dir):
            # The optional fonts directory is not required for StyleCore.
            return

        # Skip empty directories and directories without supported font files.
        try:
            filenames = os.listdir(font_dir)
        except OSError as exc:
            QgsMessageLog.logMessage(
                f"Cannot inspect StyleCore font directory {font_dir}: {exc}",
                "StyleCore", level=Qgis.MessageLevel.Warning
            )
            return
        if not any(name.lower().endswith((".ttf", ".otf")) and
                   os.path.isfile(os.path.join(font_dir, name))
                   for name in filenames):
            return

        normalized_dir = os.path.normcase(os.path.realpath(font_dir))
        if normalized_dir in self._registered_font_directories:
            return

        try:
            QgsApplication.fontManager().addUserFontDirectory(font_dir)
            self._registered_font_directories.add(normalized_dir)
            QgsMessageLog.logMessage(
                f"StyleCore font directory registered: {font_dir}",
                "StyleCore", level=Qgis.MessageLevel.Info
            )
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Could not register StyleCore fonts from {font_dir}: {exc}",
                "StyleCore", level=Qgis.MessageLevel.Warning
            )

    def warn_missing_configuration(self):
        """Warn only for a previously selected JSON that is no longer accessible."""
        selected = QSettings().value(CONFIG_FILE_KEY, '', type=str).strip()
        if selected and not os.path.isfile(selected):
            self.iface.messageBar().pushWarning(
                'StyleCore',
                tr('Configuration file not found. Open Settings to select another configuration: ') + selected,
            )

    def open_settings(self):
        self.iface.showOptionsDialog(
            self.iface.mainWindow(),
            currentPage="StyleCore"
        )

    def _auto_action_text(self, enabled):
        return f"{tr('Automatic styling')}\t{'✔' if enabled else '✕'}"

    def set_auto_enabled(self, enabled):
        settings = QSettings()

        settings.setValue(
            ENABLED_KEY,
            enabled
        )


        if self.enabled_action:
            self.enabled_action.blockSignals(True)
            self.enabled_action.setChecked(enabled)
            self.enabled_action.setText(self._auto_action_text(enabled))
            self.enabled_action.blockSignals(False)


        if enabled:
            self.tool_button.setToolTip(
                "StyleCore"
            )
        else:
            self.tool_button.setToolTip(
                tr('StyleCore - automatic styling disabled')
            )

    @staticmethod
    def _file_sha256(path):
        """Used only for one-time, safe migration of old synchronized copies."""
        digest = hashlib.sha256()
        with open(path, 'rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    def cleanup_legacy_template_copies(self):
        """One-time migration; never remove arbitrary QGIS user templates.

        Only copies recorded as managed by the old StyleCore sync, with an
        unchanged matching hash, are removed. Modified copies are retained.
        After migration, no project template is ever copied locally again.
        """
        settings = QSettings()
        key = 'StyleCore/managed_template_hashes'
        try:
            manifest = json.loads(settings.value(key, '{}', type=str))
        except (TypeError, ValueError):
            manifest = {}
        if not isinstance(manifest, dict):
            manifest = {}
        folder = os.path.join(QgsApplication.qgisSettingsDirPath(), 'project_templates')
        remaining = {}
        removed = 0
        for filename, expected_hash in manifest.items():
            if (filename != os.path.basename(filename)
                    or not filename.lower().endswith(('.qgz', '.qgs'))
                    or not isinstance(expected_hash, str)):
                continue
            target = os.path.join(folder, filename)
            try:
                if os.path.isfile(target):
                    if self._file_sha256(target) == expected_hash:
                        os.remove(target)
                        removed += 1
                    else:
                        remaining[filename] = expected_hash
            except OSError:
                remaining[filename] = expected_hash
        if removed:
            QgsMessageLog.logMessage(
                f"Removed {removed} unchanged legacy template copies. "
                "QGIS may need a restart to refresh its Welcome screen.",
                'StyleCore', level=Qgis.MessageLevel.Info)
        if manifest:
            settings.setValue(key, json.dumps(remaining))

        # Undo only StyleCore's historical QGIS template-folder override,
        # without modifying any other user-chosen QGIS template directory.
        old = settings.value('qgis/projectTemplateDir', '', type=str) or ''
        if os.path.basename(os.path.normpath(old)).casefold() == 'stylecore_project_templates':
            original = os.path.normpath(os.path.join(
                QgsApplication.qgisSettingsDirPath(), 'project_templates'))
            settings.setValue('qgis/projectTemplateDir', original)
        settings.sync()

    def refresh_templates_menu(self):
        """Re-read templates recursively from their original sources on open."""
        self.templates_menu.clear()
        inactive = {name.casefold() for name in get_inactive_templates()}
        entries = [entry for entry in list_project_templates()
                   if entry['key'].casefold() not in inactive]
        if not entries:
            placeholder = self.templates_menu.addAction('No active project templates')
            placeholder.setEnabled(False)
            return
        # Two sources may have the same visible name; show their relative
        # location instead of an ambiguous duplicate menu action.
        label_counts = {}
        for entry in entries:
            label_counts[entry['label'].casefold()] = label_counts.get(entry['label'].casefold(), 0) + 1
        for entry in entries:
            path, key = entry['path'], entry['key']
            label = entry['label']
            if label_counts[label.casefold()] > 1:
                # Never show internal config namespaces such as @external in
                # the user-facing menu; use the source folder for clarity.
                label += ' [' + os.path.basename(os.path.dirname(path)) + ']'
            action = self.templates_menu.addAction(label)
            action.setToolTip(path)
            if not os.path.isfile(path):
                action.setEnabled(False)
                action.setToolTip('File not found: ' + path)
            else:
                action.triggered.connect(
                    lambda checked=False, p=path, n=key: self.open_project_template(p, n))

    def open_project_template(self, path, template_name):
        """Read from the original path and force Save As for the new project."""
        if not os.path.isfile(path):
            self.iface.messageBar().pushWarning('StyleCore', 'Template not found: ' + path)
            return
        if not self.iface.newProject(True):
            return
        try:
            if not self.iface.addProject(path):
                self.iface.messageBar().pushWarning('StyleCore', 'Could not load template: ' + path)
                return
            project = QgsProject.instance()
            # Styles from a saved working project are never overwritten.
            # Only this explicit menu action can trigger template refresh.
            if (template_name.casefold() in {n.casefold() for n in get_restyle_templates()}
                    and QSettings().value(ENABLED_KEY, True, type=bool)):
                applied = sum(bool(self.apply_style(layer)) for layer in project.mapLayers().values())
                QgsMessageLog.logMessage(
                    f"Template '{template_name}': refreshed {applied} layer styles.",
                    'StyleCore', level=Qgis.MessageLevel.Info)
            # Do not accidentally overwrite the shared original template.
            project.setFileName('')
            mode = str(load_external_config().get('save_paths', 'relative')).lower()
            project.setFilePathStorage(
                Qgis.FilePathType.Absolute if mode == 'absolute'
                else Qgis.FilePathType.Relative
            )
            project.setDirty(True)
            QgsMessageLog.logMessage(
                f"Opened original template (unsaved copy): {path}",
                'StyleCore', level=Qgis.MessageLevel.Info)
        except Exception as exc:
            self.iface.messageBar().pushWarning('StyleCore', 'Template open failed: ' + str(exc))

    def refresh_print_menu(self):
        """Populate the Print Layouts submenu directly from shared QPT files."""
        if not self.print_menu:
            return
        self.print_menu.clear()
        layouts = self.print_manager.discover_layouts()
        if not layouts:
            empty = self.print_menu.addAction(tr('No print layouts found'))
            empty.setEnabled(False)
            return

        for layout_name, template_path in layouts:
            action = self.print_menu.addAction(layout_name)
            action.setToolTip(template_path)
            action.triggered.connect(
                lambda checked=False, path=template_path:
                    self.print_manager.create_layout_from_template(path)
            )

    def unload(self):
        project = QgsProject.instance()
        project.layersAdded.disconnect(self.layers_added)
        project.loadingLayer.disconnect(self.project_loading_started)
        project.layerLoaded.disconnect(self.project_layer_loaded)
        self.iface.projectRead.disconnect(self.project_read_complete)

        if self.options_factory:
            self.iface.unregisterOptionsWidgetFactory(
                self.options_factory
            )

        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None

    def project_loading_started(self, *args):
        """Mark layers emitted while a saved project/template is being read."""
        if not self._project_loading:
            self._project_load_skipped_count = 0
            QgsMessageLog.logMessage(
                "Project loading started - existing project layers will keep their saved styles during load.",
                "StyleCore",
                level=Qgis.MessageLevel.Info
            )
        self._project_loading = True

    def project_layer_loaded(self, index, total):
        """Keep the load guard active until QgisInterface.projectRead is emitted."""
        self._project_loading = True

    def layers_added(self, layers):
        # QGIS also emits layersAdded for layers restored from a saved project.
        # Keep these untouched. Explicitly selected templates are refreshed only
        # after QGIS emits iface.projectRead (successful project read).
        if self._project_loading:
            self._project_load_skipped_count += len(layers)
            return

        settings = QSettings()

        enabled = settings.value(
            ENABLED_KEY,
            True,
            type=bool
        )

        if not enabled:
            QgsMessageLog.logMessage(
                f"Automatic styling disabled - {len(layers)} newly added layer(s) left unchanged.",
                "StyleCore",
                level=Qgis.MessageLevel.Info
            )
            return

        if not load_external_config():
            QgsMessageLog.logMessage(
                "Automatic styling skipped: active StyleCore configuration is unavailable.",
                "StyleCore", level=Qgis.MessageLevel.Warning)
            return

        # One summary per batch; unmatched layers do not fill the message log.
        applied = sum(bool(self.apply_style(layer)) for layer in layers)
        QgsMessageLog.logMessage(
            f"Automatic styling - {applied} of {len(layers)} new layer(s) styled.",
            "StyleCore",
            level=Qgis.MessageLevel.Info,
        )

    def project_read_complete(self):
        """Normal saved projects keep their own styles and are never refreshed."""
        self._project_loading = False
        if self._project_load_skipped_count:
            QgsMessageLog.logMessage(
                f"Preserved saved styles on {self._project_load_skipped_count} loaded layer(s).",
                'StyleCore', level=Qgis.MessageLevel.Info)
        self._project_load_skipped_count = 0

    def apply_style(self, layer):
        """Apply local override first, then shared config, then naming fallback.

        A failed/missing personal QML does not disable the shared default.
        This method is only called for new layers or opted-in templates; it
        must NOT override saved styles when regular old projects are opened.
        """
        if not load_external_config():
            # The caller logs a single unavailable-config warning per batch.
            return False
        layer_name = layer.name()
        style_folder = get_style_folder()

        file_rule = match_file_suffix_rule(layer.source())
        file_rule_path = get_file_suffix_style_path(file_rule) if file_rule else None

        # All personal rules take precedence over shared rules. Within each
        # scope, an exact layer match wins over a file suffix match;
        # the order never depends on modified
        # file timestamps. A failing QML falls back to the next choice.
        candidates = []
        for scope, rules in (("personal", get_personal_style_rules()),
                             ("shared", get_style_rules())):
            for key in (layer_name,):
                if not key:
                    continue
                for rule in rules:
                    if rule['layer'].casefold() == key.casefold():
                        candidates.append((scope, resolve_style_path(rule['style'])))
                        break

        if file_rule_path:
            candidates.append(("file suffix", file_rule_path))

        # Last resort: QML file matching the visible QGIS layer name.
        fallbacks = []
        named = os.path.join(style_folder, f"{layer_name}.qml") if style_folder else ""
        for path in (named,):
            if path and os.path.isfile(path):
                fallbacks.append(path)
        for path in sorted(set(fallbacks), key=os.path.getmtime, reverse=True):
            candidates.append(("automatic", path))

        tried = set()
        for scope, path in candidates:
            key = os.path.normcase(os.path.normpath(path)) if path else ''
            if not key or key in tried:
                continue
            tried.add(key)
            if not os.path.isfile(path):
                if scope != "automatic":
                    QgsMessageLog.logMessage(
                        f"{scope.title()} style for {layer_name} not found: {path}",
                        "StyleCore", level=Qgis.MessageLevel.Warning)
                continue
            try:
                message, success = layer.loadNamedStyle(path)
            except Exception as exc:
                message, success = str(exc), False
            if success:
                layer.triggerRepaint()
                QgsMessageLog.logMessage(
                    f"{scope.title()} style applied to {layer_name}: {path}",
                    "StyleCore", level=Qgis.MessageLevel.Info)
                return True
            QgsMessageLog.logMessage(
                f"Could not load {scope} style for {layer_name}: {message}",
                "StyleCore", level=Qgis.MessageLevel.Warning)
        return False
