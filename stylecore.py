import os
import shutil

from qgis.core import QgsProject, QgsMessageLog, QgsApplication, Qgis
from qgis.PyQt.QtGui import QFont, QIcon
from qgis.PyQt.QtWidgets import QAction, QToolButton, QMenu
from qgis.PyQt.QtCore import QSettings

from .options import StyleCoreOptionsFactory
from .print_layouts import StyleCorePrintLayouts
from .language import tr
from .config import (
    ENABLED_KEY,
    SETTINGS_KEY,
    get_geojson_suffix_styles,
    get_style_folder,
    get_template_folder,
    get_geojson_style_path,
    get_restyle_templates,
)

class StyleCore:

    def __init__(self, iface):
        self.iface = iface
        self.options_factory = None
        self.action = None
        self.tool_button = None
        self.enabled_action = None
        self.print_manager = StyleCorePrintLayouts(iface)
        self.main_menu = None

    def initGui(self):
        self.register_fonts()
        self.sync_templates()
        self.print_manager.sync_layouts()

        QgsProject.instance().layersAdded.connect(self.layers_added)

        QgsProject.instance().readProject.connect(self.project_loaded)

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
            tr("Indstillinger..."),
            self.main_menu
        )

        settings_action.triggered.connect(
            self.open_settings
        )

        self.main_menu.addAction(settings_action)

        self.enabled_action = QAction(
            tr("Automatisk styling"),
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

        self.print_menu_actions = []
        self.main_menu.aboutToShow.connect(self.refresh_print_menu)

        self.tool_button.setMenu(self.main_menu)

        self.action = self.iface.addToolBarWidget(
            self.tool_button
        )

    def register_fonts(self):
        """Register fonts bundled with StyleCore in the current QGIS session."""
        font_dir = os.path.join(
            os.path.dirname(__file__),
            "fonts"
        )

        if not os.path.isdir(font_dir):
            QgsMessageLog.logMessage(
                f"Font folder not found: {font_dir}",
                "StyleCore",
                level=Qgis.Warning
            )
            return

        try:
            QgsApplication.fontManager().addUserFontDirectory(font_dir)

            QgsMessageLog.logMessage(
                f"StyleCore fonts registered: {font_dir}",
                "StyleCore",
                level=Qgis.Info
            )

        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Could not register StyleCore fonts: {exc}",
                "StyleCore",
                level=Qgis.Warning
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
                tr("StyleCore - automatisk styling deaktiveret")
            )

    def sync_resources(self):
        """Synchronize all resources after the configuration or root changes."""
        self.sync_templates()
        self.print_manager.sync_layouts()

    def sync_templates(self):
        template_source_folder = get_template_folder()

        if not template_source_folder:
            return

        if not os.path.isdir(template_source_folder):
            QgsMessageLog.logMessage(
                f"Template folder not found: {template_source_folder}",
                "StyleCore",
                level=Qgis.Warning
            )
            return

        profile_path = QgsApplication.qgisSettingsDirPath()

        if Qgis.QGIS_VERSION_INT >= 40000:
            profile_path = profile_path.replace(
                "QGIS3",
                "QGIS4"
            )

        local_template_folder = os.path.join(
            profile_path,
            "project_templates"
        )

        os.makedirs(
            local_template_folder,
            exist_ok=True
        )

        for filename in os.listdir(template_source_folder):

            if not filename.lower().endswith((".qgz", ".qgs")):
                continue

            source_file = os.path.join(
                template_source_folder,
                filename
            )

            local_file = os.path.join(
                local_template_folder,
                filename
            )

            should_copy = (
                not os.path.exists(local_file)
                or os.path.getmtime(source_file)
                > os.path.getmtime(local_file)
            )

            if not should_copy:
                continue

            try:
                shutil.copy2(
                    source_file,
                    local_file
                )

                QgsMessageLog.logMessage(
                    f"Skabelon opdateret: {filename}",
                    "StyleCore",
                    level=Qgis.Info
                )

            except Exception as exc:
                QgsMessageLog.logMessage(
                    f"Could not update template {filename}: {exc}",
                    "StyleCore",
                    level=Qgis.Warning
                )

    def refresh_print_menu(self):
        """Synchronize and rebuild the print section of the dropdown menu."""
        self.print_manager.sync_layouts()

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
        self.main_menu.addAction(print_header)
        self.print_menu_actions.append(print_header)

        layouts = self.print_manager.discover_layouts()

        if not layouts:
            empty_action = QAction(
                "    " + tr("Ingen print-layouts fundet"),
                self.main_menu,
            )
            empty_action.setEnabled(False)
            self.main_menu.addAction(empty_action)
            self.print_menu_actions.append(empty_action)
            return

        for layout_name, template_path in layouts:
            action = QAction(f"    {layout_name}", self.main_menu)
            action.triggered.connect(
                lambda checked=False, path=template_path:
                    self.print_manager.create_layout_from_template(path)
            )
            self.main_menu.addAction(action)
            self.print_menu_actions.append(action)

    def unload(self):
        QgsProject.instance().layersAdded.disconnect(self.layers_added)
        QgsProject.instance().readProject.disconnect(self.project_loaded)

        if self.options_factory:
            self.iface.unregisterOptionsWidgetFactory(
                self.options_factory
            )

        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None

    def layers_added(self, layers):
        settings = QSettings()

        enabled = settings.value(
            ENABLED_KEY,
            True,
            type=bool
        )

        if not enabled:
            return

        for layer in layers:
            self.process_layer(layer)

    def process_layer(self, layer):
        self.apply_style(layer)

    def project_loaded(self, *args):
        project = QgsProject.instance()

        project_path = project.fileName()
        project_name = os.path.splitext(
            os.path.basename(project_path)
        )[0]

        restyle_templates = {
            name.casefold() for name in get_restyle_templates()
        }

        if project_name.casefold() not in restyle_templates:
            return

        QgsMessageLog.logMessage(
            f"Template '{project_name}' opened - refreshing layer styles",
            "StyleCore",
            level=Qgis.Info
        )

        for layer in project.mapLayers().values():
            self.apply_style(layer)

    def apply_style(self, layer):
        settings = QSettings()
        layer_name = layer.name()

        custom_rules = settings.value(
            SETTINGS_KEY,
            [],
            type=list
        )

        for rule in custom_rules:
            if rule.get("layer", "") == layer_name:
                custom_style_path = rule.get("style", "")

                if custom_style_path and os.path.exists(
                    custom_style_path
                ):
                    message, success = layer.loadNamedStyle(
                        custom_style_path
                    )

                    if success:
                        layer.triggerRepaint()

                        QgsMessageLog.logMessage(
                            (
                                f"User rule applied to "
                                f"{layer_name}: "
                                f"{custom_style_path}"
                            ),
                            "StyleCore",
                            level=Qgis.Info
                        )

                    else:
                        QgsMessageLog.logMessage(
                            (
                                f"Could not load user rule "
                                f"for {layer_name}: {message}"
                            ),
                            "StyleCore",
                            level=Qgis.Warning
                        )

                    return

        standard_style_path = os.path.join(
            get_style_folder(),
            f"{layer_name}.qml"
        )
        geojson_style_path = None
        geojson_rule_key = None

        source_path = layer.source().split("|")[0]

        if source_path.casefold().endswith(".geojson"):
            geojson_name = os.path.splitext(
                os.path.basename(source_path)
            )[0]

            for suffix, geojson_rule in get_geojson_suffix_styles().items():
                if geojson_name.casefold().endswith(suffix.casefold()):
                    geojson_rule_key = suffix
                    geojson_style_path = get_geojson_style_path(suffix)
                    break

        if geojson_rule_key:
            for custom_rule in custom_rules:
                if custom_rule.get("layer", "") != geojson_rule_key:
                    continue

                custom_geojson_path = custom_rule.get("style", "")
                if custom_geojson_path and os.path.isfile(custom_geojson_path):
                    message, success = layer.loadNamedStyle(custom_geojson_path)

                    if success:
                        layer.triggerRepaint()
                        QgsMessageLog.logMessage(
                            (
                                f"GeoJSON user rule applied to {layer_name}: "
                                f"{custom_geojson_path}"
                            ),
                            "StyleCore",
                            level=Qgis.Info
                        )
                    else:
                        QgsMessageLog.logMessage(
                            (
                                f"Could not load GeoJSON user rule for "
                                f"{layer_name}: {message}"
                            ),
                            "StyleCore",
                            level=Qgis.Warning
                        )

                    return

                break

        style_candidates = []

        if os.path.isfile(standard_style_path):
            style_candidates.append(
                standard_style_path
            )

        if geojson_style_path and os.path.isfile(
            geojson_style_path
        ):
            style_candidates.append(
                geojson_style_path
            )

        if not style_candidates:
            return

        style_path = max(
            style_candidates,
            key=os.path.getmtime
        )

        message, success = layer.loadNamedStyle(
            style_path
        )

        if success:
            layer.triggerRepaint()

            QgsMessageLog.logMessage(
                (
                    f"Newest style applied to "
                    f"{layer_name}: {style_path}"
                ),
                "StyleCore",
                level=Qgis.Info
            )

        else:
            QgsMessageLog.logMessage(
                (
                    f"Could not load style "
                    f"for {layer_name}: {message}"
                ),
                "StyleCore",
                level=Qgis.Warning
            )
