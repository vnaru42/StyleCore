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

from .config import get_style_folder
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
                tr("Ingen gyldige vektorlag i dette projekt."),
            )
            return

        dialog = QDialog(self.iface.mainWindow())
        dialog.setWindowTitle(tr("Manuel styleopdatering"))
        dialog.resize(620, 490)
        layout = QVBoxLayout(dialog)
        help_text = QLabel(tr(
            "Vælg et lag, kontrollér den foreslåede QML eller vælg en anden fil, "
            "og tryk Brug style. Andre projekter og automatiske regler ændres ikke."
        ))
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        layer_list = QListWidget(dialog)
        for layer in layers:
            item = QListWidgetItem(layer.name())
            item.setData(Qt.ItemDataRole.UserRole, layer.id())
            layer_list.addItem(item)
        layout.addWidget(layer_list)

        layout.addWidget(QLabel(tr("QML-fil:")))
        file_row = QHBoxLayout()
        path_edit = QLineEdit(dialog)
        browse = QPushButton(tr("Gennemse..."), dialog)
        file_row.addWidget(path_edit)
        file_row.addWidget(browse)
        layout.addLayout(file_row)

        status = QLabel("")
        status.setWordWrap(True)
        layout.addWidget(status)

        buttons = QHBoxLayout()
        use_button = QPushButton(tr("Brug style"), dialog)
        close_button = QPushButton(tr("Luk"), dialog)
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
                "Ingen QML foreslået. Vælg en QML-fil manuelt."
            ))
            refresh_apply_button()

        def browse_style():
            current = path_edit.text().strip()
            start = os.path.dirname(current) if current else style_folder
            path, _ = QFileDialog.getOpenFileName(
                dialog, tr("Vælg QML-style"), start, "QGIS style (*.qml)",
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
                QMessageBox.warning(dialog, "StyleCore", tr("Kunne ikke anvende QML-style:") + "\n" + str(message))
                return

            layer.triggerRepaint()
            # Style stays in the QGIS project when the user saves it; nothing
            # is written to QSettings, the JSON config, or a source-layer rule.
            project.setDirty(True)
            QgsMessageLog.logMessage(
                f"Manual style applied to {layer.name()}: {path}",
                "StyleCore", level=Qgis.Info,
            )
            status.setText(tr("Style anvendt på dette lag. Gem QGIS-projektet for at beholde ændringen."))

        layer_list.currentItemChanged.connect(layer_changed)
        path_edit.textChanged.connect(refresh_apply_button)
        browse.clicked.connect(browse_style)
        use_button.clicked.connect(apply_manual_style)
        close_button.clicked.connect(dialog.reject)
        layer_list.setCurrentRow(0)
        dialog.exec()
