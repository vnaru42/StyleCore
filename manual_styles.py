"""Per-layer, opt-in application of QML styles in existing QGIS projects."""

import os

from qgis.core import QgsDataSourceUri, QgsMapLayerType, QgsMessageLog, QgsProject, Qgis
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .config import get_style_folder, get_effective_style_rules, resolve_style_path
from .language import tr


class StyleCoreManualStyles:
    """Offer QML suggestions without creating any automatic style associations."""

    def __init__(self, iface):
        self.iface = iface

    def show_dialog(self):
        project = QgsProject.instance()
        # Keep the ordering from the QGIS Layers panel, including nested groups.
        layers = []
        seen = set()
        for node in project.layerTreeRoot().findLayers():
            layer = node.layer()
            if (layer is not None and layer.isValid()
                    and layer.type() == QgsMapLayerType.VectorLayer
                    and layer.id() not in seen):
                layers.append(layer)
                seen.add(layer.id())

        if not layers:
            QMessageBox.information(
                self.iface.mainWindow(), "StyleCore",
                tr('No valid vector layers in the current project.'),
            )
            return

        dialog = QDialog(self.iface.mainWindow())
        dialog.setWindowTitle(tr('Manual Style Update'))
        dialog.resize(620, 490)
        layout = QVBoxLayout(dialog)
        help_text = QLabel(tr(
            "Select a layer, review the suggested QML or browse for another file, "
            "then click Use Style. Other projects and automatic rules are not changed."
        ))
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        layer_list = QListWidget(dialog)
        for layer in layers:
            item = QListWidgetItem(layer.name())
            item.setData(Qt.ItemDataRole.UserRole, layer.id())
            layer_list.addItem(item)
        layout.addWidget(layer_list)

        layout.addWidget(QLabel(tr('QML file:')))
        file_row = QHBoxLayout()
        path_edit = QLineEdit(dialog)
        browse = QPushButton(tr('Browse...'), dialog)
        file_row.addWidget(path_edit)
        file_row.addWidget(browse)
        layout.addLayout(file_row)

        status = QLabel("")
        status.setWordWrap(True)
        layout.addWidget(status)

        buttons = QHBoxLayout()
        use_button = QPushButton(tr('Use Style'), dialog)
        close_button = QPushButton(tr('Close'), dialog)
        use_button.setEnabled(False)
        buttons.addWidget(use_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        # Lookup is only a suggestion in this dialog, never a saved Oracle mapping.
        style_folder = get_style_folder()
        try:
            available = {
                filename[:-4].casefold(): os.path.join(style_folder, filename)
                for filename in os.listdir(style_folder)
                if filename.lower().endswith(".qml")
                and os.path.isfile(os.path.join(style_folder, filename))
            }
        except OSError:
            available = {}

        # Explicit config mappings can also be suggested for older projects;
        # the user must still click Use Style. No source-wide rule is created.
        explicit = {
            str(rule.get("layer", "")).casefold(): resolve_style_path(rule.get("style", ""))
            for rule in get_effective_style_rules()
            if rule.get("layer") and rule.get("style")
        }

        def chosen_layer():
            item = layer_list.currentItem()
            return project.mapLayer(item.data(Qt.ItemDataRole.UserRole)) if item else None

        def suggested_path(layer):
            candidates = [layer.name()]
            if layer.providerType().casefold() == "oracle":
                try:
                    # Old Oracle layer labels may differ from the underlying view name.
                    table = QgsDataSourceUri(layer.source()).table().strip('"')
                    if table:
                        candidates.append(table.split(".")[-1].strip('"'))
                except (AttributeError, ValueError):
                    pass
            for name in candidates:
                match = explicit.get(name.casefold())
                if match and os.path.isfile(match):
                    return match
                match = available.get(name.casefold())
                if match:
                    return match
            return ""

        def refresh_apply_button(*_args):
            path = path_edit.text().strip()
            use_button.setEnabled(
                chosen_layer() is not None
                and path.lower().endswith(".qml")
                and os.path.isfile(path)
            )

        def layer_changed(*_args):
            layer = chosen_layer()
            path_edit.setText(suggested_path(layer) if layer else "")
            status.setText("" if path_edit.text() else tr(
                'No matching QML suggested. Choose a QML file manually.'
            ))
            refresh_apply_button()

        def browse_style():
            current = path_edit.text().strip()
            start = os.path.dirname(current) if current else style_folder
            path, _ = QFileDialog.getOpenFileName(
                dialog, tr('Choose QML style'), start, "QGIS style (*.qml)",
            )
            if path:
                path_edit.setText(path)

        def apply_manual_style():
            layer = chosen_layer()
            path = path_edit.text().strip()
            if layer is None or not os.path.isfile(path) or not path.lower().endswith(".qml"):
                return
            try:
                message, success = layer.loadNamedStyle(path)
            except Exception as exc:
                message, success = str(exc), False
            if not success:
                QMessageBox.warning(dialog, "StyleCore", tr('Could not apply QML style:') + "\n" + str(message))
                return

            layer.triggerRepaint()
            # Style stays in the QGIS project when the user saves it; nothing
            # is written to QSettings, the JSON config, or a source-layer rule.
            project.setDirty(True)
            QgsMessageLog.logMessage(
                f"Manual style applied to {layer.name()}: {path}",
                "StyleCore", level=Qgis.MessageLevel.Info,
            )
            status.setText(tr('Style applied to this layer. Save the QGIS project to keep it.'))

        layer_list.currentItemChanged.connect(layer_changed)
        path_edit.textChanged.connect(refresh_apply_button)
        browse.clicked.connect(browse_style)
        use_button.clicked.connect(apply_manual_style)
        close_button.clicked.connect(dialog.reject)
        layer_list.setCurrentRow(0)
        dialog.exec()
