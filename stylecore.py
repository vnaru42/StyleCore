import os
import shutil
import json
import hashlib
import tempfile

from qgis.core import QgsProject, QgsMessageLog, QgsApplication, Qgis
from qgis.PyQt.QtGui import QFont, QIcon, QDesktopServices
from qgis.PyQt.QtWidgets import QAction, QToolButton, QMenu, QListView, QApplication, QWidgetAction, QPushButton
from qgis.PyQt.QtCore import QSettings, QTimer, Qt, QUrl, QSize

from .options import StyleCoreOptionsFactory
from .print_layouts import StyleCorePrintLayouts
from .manual_styles import StyleCoreManualStyles
from .language import tr
from .config import (
    ENABLED_KEY,
    match_file_suffix_rule,
    get_file_suffix_style_path,
    get_style_folder,
    get_root_folder,
    get_template_folder,
    get_restyle_templates,
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
        self._pending_project_identity = []
        self._pending_project_raw_identity = []
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

    def initGui(self):
        self.migrate_legacy_template_path()
        bind_legacy_style_rules()

        # Defer the first resource sync until QGIS has finished building its GUI.
        # This avoids project templates being discovered twice during startup and
        # also makes resources available after a first-time plugin installation
        # without requiring a QGIS restart.
        QTimer.singleShot(250, self.sync_resources)

        project = QgsProject.instance()
        project.layersAdded.connect(self.layers_added)
        project.loadingLayer.connect(self.project_loading_started)
        project.layerLoaded.connect(self.project_layer_loaded)
        project.readProject.connect(self.capture_project_identity)
        self.iface.projectRead.connect(self.project_read_complete)

        self.options_factory = StyleCoreOptionsFactory(
            enabled_changed_callback=self.set_auto_enabled,
            root_folder_changed_callback=self.sync_resources,
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

        settings_action = QAction(
            tr('Settings...'),
            self.main_menu
        )

        settings_action.triggered.connect(
            self.open_settings
        )

        self.main_menu.addAction(settings_action)

        self.enabled_action = QAction(
            tr('Automatic styling'),
            self.main_menu
        )

        self.enabled_action.setCheckable(True)

        enabled = QSettings().value(
            ENABLED_KEY,
            True,
            type=bool
        )

        self.enabled_action.setChecked(enabled)

        self.enabled_action.toggled.connect(
            self.set_auto_enabled
        )

        self.main_menu.addAction(self.enabled_action)

        # Manual styling is an explicit, per-layer action for older projects.
        manual_action = QAction(tr('Manual Style Update...'), self.main_menu)
        manual_action.triggered.connect(self.manual_styles.show_dialog)
        self.main_menu.addAction(manual_action)

        # Two unobtrusive external links below the dynamic print layout list.
        # QWidgetAction is used only here to give the links a muted text color;
        # ordinary QMenu/QAction does not support per-action foreground colors.
        self.help_separator = self.main_menu.addSeparator()
        self.help_action = self._add_external_link(
            tr('Help & Documentation'),
            'https://vnaru42.github.io/StyleCore-Docs/',
        )
        self.issue_action = self._add_external_link(
            tr('Report an Issue'),
            'https://github.com/vnaru42/StyleCore/issues/new',
        )

        self.print_menu_actions = []
        self.main_menu.aboutToShow.connect(self.refresh_print_menu)

        self.tool_button.setMenu(self.main_menu)

        self.action = self.iface.addToolBarWidget(
            self.tool_button
        )


    def migrate_legacy_template_path(self):
        """Undo the temporary StyleCore template-path experiment from pre-1.5.1 tests."""
        settings = QSettings()
        configured = settings.value("qgis/projectTemplateDir", "", type=str) or ""

        if not configured:
            return

        normalized = os.path.normpath(configured)
        if os.path.basename(normalized).casefold() != "stylecore_project_templates":
            return

        profile_path = QgsApplication.qgisSettingsDirPath()
        default_template_folder = os.path.normpath(
            os.path.join(profile_path, "project_templates")
        )

        settings.setValue("qgis/projectTemplateDir", default_template_folder)
        settings.sync()

        # Remove only the obsolete empty folder created by the old test build.
        try:
            if os.path.isdir(normalized) and not os.listdir(normalized):
                os.rmdir(normalized)
        except OSError:
            pass

        QgsMessageLog.logMessage(
            f"Restored QGIS project template directory: {default_template_folder}",
            "StyleCore",
            level=Qgis.MessageLevel.Info
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

    def open_settings(self):
        self.iface.showOptionsDialog(
            self.iface.mainWindow(),
            currentPage="StyleCore"
        )

    def set_auto_enabled(self, enabled):
        settings = QSettings()

        settings.setValue(
            ENABLED_KEY,
            enabled
        )


        if self.enabled_action:
            self.enabled_action.blockSignals(True)
            self.enabled_action.setChecked(enabled)
            self.enabled_action.blockSignals(False)


        if enabled:
            self.tool_button.setToolTip(
                "StyleCore"
            )
        else:
            self.tool_button.setToolTip(
                tr('StyleCore - automatic styling disabled')
            )

    def sync_resources(self):
        """Synchronize resources that require local QGIS copies."""
        self.register_fonts()
        self.sync_templates()

        # QGIS' Welcome page maintains its own live template model. On some
        # installations the same physical template can temporarily be inserted
        # more than once when the watched project_templates directory changes.
        # Clean only duplicate rows belonging to templates managed by StyleCore.
        QTimer.singleShot(300, self.cleanup_welcome_template_duplicates)
        QTimer.singleShot(1200, self.cleanup_welcome_template_duplicates)

    def cleanup_welcome_template_duplicates(self):
        """Remove duplicate StyleCore template rows from QGIS' Welcome model."""
        template_source_folder = get_template_folder()
        if not template_source_folder or not os.path.isdir(template_source_folder):
            return

        managed_names = {
            os.path.splitext(filename)[0].casefold()
            for filename in os.listdir(template_source_folder)
            if filename.lower().endswith((".qgz", ".qgs"))
        }

        if not managed_names:
            return

        main_window = self.iface.mainWindow()

        for view in main_window.findChildren(QListView):
            model = view.model()
            if model is None:
                continue

            try:
                class_name = model.metaObject().className()
            except Exception as exc:
                QgsMessageLog.logMessage(
                    f"Could not inspect template model: {exc}",
                    "StyleCore", level=Qgis.MessageLevel.Warning,
                )
                continue

            if "TemplateProjectsModel" not in class_name:
                continue

            seen = set()
            duplicate_rows = []

            for row in range(model.rowCount()):
                index = model.index(row, 0)

                # The delegate title is stored in a custom role, while the
                # QStandardItem display value normally contains the filename.
                # Read a small range of roles so this remains tolerant across
                # supported QGIS versions.
                values = []
                for role in range(int(Qt.ItemDataRole.DisplayRole), int(Qt.ItemDataRole.UserRole) + 32):
                    value = index.data(role)
                    if value is not None and value != "":
                        values.append(str(value))

                managed_name = None
                for value in values:
                    base = os.path.splitext(os.path.basename(value))[0].casefold()
                    if base in managed_names:
                        managed_name = base
                        break

                if managed_name is None:
                    continue

                if managed_name in seen:
                    duplicate_rows.append(row)
                else:
                    seen.add(managed_name)

            for row in reversed(duplicate_rows):
                model.removeRow(row)

            if duplicate_rows:
                QgsMessageLog.logMessage(
                    f"Removed {len(duplicate_rows)} duplicate Welcome template entrie(s).",
                    "StyleCore",
                    level=Qgis.MessageLevel.Info
                )

    @staticmethod
    def _file_sha256(path):
        digest = hashlib.sha256()
        with open(path, 'rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    def sync_templates(self):
        """Sync only StyleCore-owned templates, preserving unrelated local files.

        A manifest stores the hash of the last file WE copied. We can safely
        remove obsolete copies only when the content has not been modified by
        the user. Config switches replace StyleCore-owned files even if the
        new config's source file is older (mtime must not determine ownership).
        """
        source_folder = get_template_folder()
        if not source_folder or not os.path.isdir(source_folder):
            QgsMessageLog.logMessage(
                f"Template folder unavailable: {source_folder}",
                "StyleCore", level=Qgis.MessageLevel.Warning)
            return

        profile_path = QgsApplication.qgisSettingsDirPath()
        local_folder = os.path.join(profile_path, "project_templates")
        os.makedirs(local_folder, exist_ok=True)
        settings = QSettings()
        manifest_key = "StyleCore/managed_template_hashes"
        try:
            manifest = json.loads(settings.value(manifest_key, "{}", type=str))
            if not isinstance(manifest, dict):
                manifest = {}
        except (ValueError, TypeError):
            manifest = {}

        sources = {
            filename: os.path.join(source_folder, filename)
            for filename in os.listdir(source_folder)
            if filename.lower().endswith((".qgz", ".qgs"))
            and os.path.isfile(os.path.join(source_folder, filename))
        }
        next_manifest = {}

        # Remove only previously synchronized and unchanged copies, never a
        # local template or a template edited by the QGIS user.
        for filename, recorded_hash in manifest.items():
            if (filename in sources or filename != os.path.basename(filename)
                    or not filename.lower().endswith((".qgz", ".qgs"))):
                continue
            target = os.path.join(local_folder, filename)
            if os.path.isfile(target):
                try:
                    if self._file_sha256(target) == recorded_hash:
                        os.remove(target)
                        QgsMessageLog.logMessage(
                            f"Removed obsolete StyleCore template: {filename}",
                            "StyleCore", level=Qgis.MessageLevel.Info)
                    else:
                        QgsMessageLog.logMessage(
                            f"Preserved locally modified old template: {filename}",
                            "StyleCore", level=Qgis.MessageLevel.Warning)
                except OSError as exc:
                    QgsMessageLog.logMessage(
                        f"Could not remove managed template {filename}: {exc}",
                        "StyleCore", level=Qgis.MessageLevel.Warning)

        for filename, source in sources.items():
            target = os.path.join(local_folder, filename)
            try:
                source_hash = self._file_sha256(source)
                current_hash = self._file_sha256(target) if os.path.isfile(target) else None
                if current_hash == source_hash:
                    next_manifest[filename] = source_hash
                    continue
                previous_hash = manifest.get(filename)
                if current_hash is not None and (not previous_hash or
                        current_hash != previous_hash):
                    QgsMessageLog.logMessage(
                        f"Template name collision (kept existing local file): {filename}. "
                        "Move/rename it if StyleCore should manage this filename.",
                        "StyleCore", level=Qgis.MessageLevel.Warning)
                    continue
                temp_path = None
                try:
                    fd, temp_path = tempfile.mkstemp(
                        prefix='.stylecore_template_', suffix='.tmp', dir=local_folder)
                    os.close(fd)
                    shutil.copy2(source, temp_path)
                    os.replace(temp_path, target)
                    temp_path = None
                finally:
                    if temp_path and os.path.exists(temp_path):
                        os.remove(temp_path)
                next_manifest[filename] = source_hash
                QgsMessageLog.logMessage(
                    f"Template synchronized: {filename}",
                    "StyleCore", level=Qgis.MessageLevel.Info)
            except Exception as exc:
                QgsMessageLog.logMessage(
                    f"Could not synchronize template {filename}: {exc}",
                    "StyleCore", level=Qgis.MessageLevel.Warning)
                if filename in manifest:
                    next_manifest[filename] = manifest[filename]

        settings.setValue(manifest_key, json.dumps(next_manifest))
        settings.sync()

    def refresh_print_menu(self):
        """Rebuild the print section directly from the configured layout folder."""

        if not self.main_menu:
            return

        for action in self.print_menu_actions:
            self.main_menu.removeAction(action)
            action.deleteLater()

        self.print_menu_actions = []

        print_header = QAction("PRINT", self.main_menu)
        print_header.setEnabled(False)
        header_font = QFont(print_header.font())
        header_font.setBold(True)
        print_header.setFont(header_font)
        self.main_menu.insertAction(self.help_separator, print_header)
        self.print_menu_actions.append(print_header)

        layouts = self.print_manager.discover_layouts()

        if not layouts:
            empty_action = QAction(
                "    " + tr('No print layouts found'),
                self.main_menu,
            )
            empty_action.setEnabled(False)
            self.main_menu.insertAction(self.help_separator, empty_action)
            self.print_menu_actions.append(empty_action)
            return

        for layout_name, template_path in layouts:
            action = QAction(f"    {layout_name}", self.main_menu)
            action.triggered.connect(
                lambda checked=False, path=template_path:
                    self.print_manager.create_layout_from_template(path)
            )
            self.main_menu.insertAction(self.help_separator, action)
            self.print_menu_actions.append(action)

    def unload(self):
        project = QgsProject.instance()
        project.layersAdded.disconnect(self.layers_added)
        project.loadingLayer.disconnect(self.project_loading_started)
        project.layerLoaded.disconnect(self.project_layer_loaded)
        project.readProject.disconnect(self.capture_project_identity)
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
            self._pending_project_identity = []
            self._pending_project_raw_identity = []
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

    def capture_project_identity(self, document):
        """Capture template identity from the project XML while it is being read."""
        candidates = []
        raw_values = []
        seen = set()

        def add_candidate(source, value):
            value = str(value or "").strip()
            if not value:
                return
            raw_values.append((source, value))
            if source in ("fileName", "originalPath"):
                name = os.path.splitext(os.path.basename(value))[0].strip()
            else:
                name = value
            key = name.casefold()
            if name and key not in seen:
                seen.add(key)
                candidates.append((source, name))

        project = QgsProject.instance()
        for getter_name in ("fileName", "originalPath", "title"):
            try:
                add_candidate(getter_name, getattr(project, getter_name)())
            except Exception as exc:
                QgsMessageLog.logMessage(
                    f"Could not read project identity field {getter_name}: {exc}",
                    "StyleCore", level=Qgis.MessageLevel.Warning,
                )

        try:
            root = document.documentElement()
            for attr_name in ("projectname", "name", "title"):
                add_candidate(f"xml:{attr_name}", root.attribute(attr_name))

            title_element = root.firstChildElement("title")
            if not title_element.isNull():
                add_candidate("xml:title", title_element.text())
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Could not inspect project XML identity: {exc}",
                "StyleCore",
                level=Qgis.MessageLevel.Warning
            )

        self._pending_project_identity = candidates
        self._pending_project_raw_identity = raw_values

        captured = ", ".join(
            f"{source}='{value}'" for source, value in raw_values
        ) or "no project identity found in project/XML yet"
        QgsMessageLog.logMessage(
            f"Project read event - captured identity: {captured}.",
            "StyleCore",
            level=Qgis.MessageLevel.Info
        )

    def _current_project_identity(self):
        """Return identity candidates available after QGIS has completed reading."""
        project = QgsProject.instance()
        candidates = []
        raw_values = []
        seen = set()

        for getter_name in ("fileName", "originalPath", "title"):
            try:
                value = getattr(project, getter_name)()
            except Exception:
                value = ""
            value = str(value or "").strip()
            if not value:
                continue
            raw_values.append((getter_name, value))
            if getter_name in ("fileName", "originalPath"):
                name = os.path.splitext(os.path.basename(value))[0].strip()
            else:
                name = value
            key = name.casefold()
            if name and key not in seen:
                seen.add(key)
                candidates.append((getter_name, name))

        return candidates, raw_values

    def project_read_complete(self):
        """Handle successful project reads without arbitrary time delays."""
        self._project_loading = False

        if self._project_load_skipped_count:
            QgsMessageLog.logMessage(
                f"Project load finished - preserved saved styles on {self._project_load_skipped_count} loaded layer(s).",
                "StyleCore",
                level=Qgis.MessageLevel.Info
            )

        current_candidates, current_raw = self._current_project_identity()

        # Merge identities captured from the XML/read phase with identities which
        # QGIS exposes only after the project has been successfully read.
        combined = []
        seen = set()
        for source, name in self._pending_project_identity + current_candidates:
            key = name.casefold()
            if key not in seen:
                seen.add(key)
                combined.append((source, name))

        raw_values = self._pending_project_raw_identity + [
            pair for pair in current_raw if pair not in self._pending_project_raw_identity
        ]

        self.restyle_selected_template(combined, raw_values)

        self._pending_project_identity = []
        self._pending_project_raw_identity = []
        self._project_load_skipped_count = 0

    def restyle_selected_template(self, candidates, raw_values):
        project = QgsProject.instance()

        configured = get_restyle_templates()
        configured_by_key = {name.casefold(): name for name in configured}

        identity_text = ", ".join(
            f"{source}='{value}'" for source, value in raw_values
        ) or "no filename/title/XML identity available"

        QgsMessageLog.logMessage(
            f"Project opened - identity check: {identity_text}. Configured restyle templates: {configured or 'none'}.",
            "StyleCore",
            level=Qgis.MessageLevel.Info
        )

        # The XML title can stay 'DK_VIS' after a user saves a separate old
        # project. Only the actual template file (or an unsaved new project)
        # is eligible for template restyling, never a saved project elsewhere.
        current_file = str(project.fileName() or '').strip()
        if current_file:
            allowed_folders = [get_template_folder(), os.path.join(
                QgsApplication.qgisSettingsDirPath(), 'project_templates')]
            eligible = any(folder and os.path.normcase(os.path.abspath(
                os.path.dirname(current_file))) == os.path.normcase(
                os.path.abspath(folder)) for folder in allowed_folders)
            if not eligible:
                QgsMessageLog.logMessage(
                    'Saved project outside the configured template folders - '
                    'preserved its styles, regardless of title.',
                    'StyleCore', level=Qgis.MessageLevel.Info)
                return

        matched_name = None
        matched_source = None
        for source, candidate in candidates:
            configured_name = configured_by_key.get(candidate.casefold())
            if configured_name:
                matched_name = configured_name
                matched_source = source
                break

        if not matched_name:
            QgsMessageLog.logMessage(
                "No configured template matched - saved project styles are preserved.",
                "StyleCore",
                level=Qgis.MessageLevel.Info
            )
            return

        QgsMessageLog.logMessage(
            f"Recognized configured template '{matched_name}' via {matched_source} - template restyling will run.",
            "StyleCore",
            level=Qgis.MessageLevel.Info
        )

        settings = QSettings()
        enabled = settings.value(
            ENABLED_KEY,
            True,
            type=bool
        )
        if not enabled:
            QgsMessageLog.logMessage(
                f"Template '{matched_name}' recognized, but automatic styling is disabled - no layers restyled.",
                "StyleCore",
                level=Qgis.MessageLevel.Info
            )
            return

        layers = list(project.mapLayers().values())
        QgsMessageLog.logMessage(
            f"Template '{matched_name}' - checking {len(layers)} layer(s) for matching styles.",
            "StyleCore",
            level=Qgis.MessageLevel.Info
        )

        applied = 0
        for layer in layers:
            if self.apply_style(layer):
                applied += 1

        QgsMessageLog.logMessage(
            f"Template '{matched_name}' restyle finished - {applied} of {len(layers)} layer(s) styled.",
            "StyleCore",
            level=Qgis.MessageLevel.Info
        )

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
