import os
import shutil
import tempfile

from qgis.core import QgsProject
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from qgis.gui import QgsOptionsPageWidget, QgsOptionsWidgetFactory

from .config import (
    DEVELOPER_CODE,
    DEVELOPER_MODE_KEY,
    ENABLED_KEY,
    ROOT_FOLDER_KEY,
    SETTINGS_KEY,
    GEOJSON_SUFFIX_STYLES,
    get_root_folder,
    get_geojson_style_path,
)


class DmikgAutoOptionsPage(QgsOptionsPageWidget):

    def __init__(
        self,
        parent=None,
        enabled_changed_callback=None,
        root_folder_changed_callback=None,
    ):
        super().__init__(parent)

        self.enabled_changed_callback = enabled_changed_callback
        self.root_folder_changed_callback = root_folder_changed_callback

        layout = QVBoxLayout()
        folder_group = QGroupBox("DMIKG fælles style")
        folder_layout = QVBoxLayout(folder_group)

        folder_info = QLabel(
            r"Sti til overordnet fælles style mappe (...\QGIS_komplet_stytem). "

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

        layout.addWidget(folder_group)
        title = QLabel("Automatiske layer styles")
        layout.addWidget(title)

        self.enabled_checkbox = QCheckBox("Automatisk styling aktiveret")
        enabled = QSettings().value(ENABLED_KEY, True, type=bool)
        self.enabled_checkbox.setChecked(enabled)
        layout.addWidget(self.enabled_checkbox)

        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            "Lagnavn",
            "Style-sti",
            "Status",
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(2, 110)

        self.table.cellDoubleClicked.connect(self.choose_style_file)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        layout.addWidget(self.table, 1)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Tilføj")
        self.remove_button = QPushButton("Fjern")
        self.reset_button = QPushButton("Nulstil valgt")

        self.add_button.clicked.connect(self.add_row)
        self.remove_button.clicked.connect(self.remove_row)
        self.reset_button.clicked.connect(self.reset_row)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        developer_group = QGroupBox("Udvikler")
        developer_layout = QVBoxLayout(developer_group)

        self.developer_checkbox = QCheckBox("Aktivér udviklertilstand")
        developer_enabled = QSettings().value(
            DEVELOPER_MODE_KEY,
            False,
            type=bool,
        )
        self.developer_checkbox.setChecked(developer_enabled)
        self.developer_checkbox.toggled.connect(self.update_developer_ui)
        developer_layout.addWidget(self.developer_checkbox)

        self.developer_info = QLabel(
            "Gemmer de aktuelle styles fra projektets lag tilbage til de "
            "tilsvarende QML-filer i den fælles layer_styles-mappe."
        )
        self.developer_info.setWordWrap(True)
        developer_layout.addWidget(self.developer_info)

        self.save_all_styles_button = QPushButton("Gem lagstyles...")
        self.save_all_styles_button.clicked.connect(self.save_selected_styles)
        developer_layout.addWidget(self.save_all_styles_button)

        layout.addWidget(developer_group)

        self.setLayout(layout)

        self.load_settings()
        self.update_buttons()
        self.update_developer_ui()

    def current_root_folder(self):
        return self.root_folder_edit.text().strip()

    def current_style_folder(self):
        return os.path.join(self.current_root_folder(), "layer_styles")

    def choose_root_folder(self):
        start_folder = self.current_root_folder()
        folder = QFileDialog.getExistingDirectory(
            self,
            "Vælg fælles DMIKG-mappe",
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

        for filename in os.listdir(style_folder):
            if not filename.lower().endswith(".qml"):
                continue

            layer_name = os.path.splitext(filename)[0]
            styles[layer_name] = os.path.join(style_folder, filename)

        return styles

    def load_settings(self):
        settings = QSettings()
        custom_rules = settings.value(SETTINGS_KEY, [], type=list)
        standard_styles = self.get_standard_styles()

        for suffix in GEOJSON_SUFFIX_STYLES:
            standard_styles[suffix] = get_geojson_style_path(
                suffix,
                self.current_style_folder(),
            )

        self.table.setRowCount(0)

        for layer_name, standard_path in sorted(standard_styles.items()):
            style_path = standard_path

            if layer_name in GEOJSON_SUFFIX_STYLES:
                status = "GeoJSON"
            else:
                status = "Standard"

            for rule in custom_rules:
                if rule.get("layer", "") == layer_name:
                    custom_path = rule.get("style", "")
                    if custom_path:
                        style_path = custom_path
                        status = "Tilpasset"
                    break

            self.add_table_row(layer_name, style_path, status)

        for rule in custom_rules:
            layer_name = rule.get("layer", "")
            style_path = rule.get("style", "")

            if not layer_name or layer_name in standard_styles:
                continue

            self.add_table_row(layer_name, style_path, "Brugerregel")

    def add_table_row(self, layer_name, style_path, status):
        row = self.table.rowCount()
        self.table.insertRow(row)

        layer_item = QTableWidgetItem(layer_name)
        style_item = QTableWidgetItem(style_path)
        status_item = QTableWidgetItem(status)

        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        if status in ("Standard", "Tilpasset", "GeoJSON"):
            layer_item.setFlags(layer_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.table.setItem(row, 0, layer_item)
        self.table.setItem(row, 1, style_item)
        self.table.setItem(row, 2, status_item)

    def choose_style_file(self, row, column):
        if column != 1:
            return

        status_item = self.table.item(row, 2)
        if not status_item:
            return

        current_status = status_item.text()
        current_item = self.table.item(row, 1)
        start_path = current_item.text() if current_item else self.current_style_folder()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vælg QGIS style",
            start_path,
            "QGIS style (*.qml)",
        )

        if not file_path:
            return

        self.table.setItem(row, 1, QTableWidgetItem(file_path))

        if current_status in ("Standard", "Tilpasset", "GeoJSON"):
            status_item.setText("Tilpasset")
        else:
            status_item.setText("Brugerregel")

        self.update_buttons()

    def add_row(self):
        self.add_table_row("", "", "Brugerregel")
        row = self.table.rowCount() - 1
        self.table.selectRow(row)
        self.update_buttons()

    def remove_row(self):
        row = self.table.currentRow()
        if row < 0:
            return

        status_item = self.table.item(row, 2)
        if not status_item or status_item.text() != "Brugerregel":
            return

        self.table.removeRow(row)
        self.update_buttons()

    def reset_row(self):
        row = self.table.currentRow()
        if row < 0:
            return

        layer_item = self.table.item(row, 0)
        status_item = self.table.item(row, 2)

        if not layer_item or not status_item or status_item.text() != "Tilpasset":
            return

        layer_name = layer_item.text()

        if layer_name in GEOJSON_SUFFIX_STYLES:
            standard_path = get_geojson_style_path(
                layer_name,
                self.current_style_folder(),
            )
            reset_status = "GeoJSON"
        else:
            standard_path = os.path.join(
                self.current_style_folder(),
                f"{layer_name}.qml",
            )
            reset_status = "Standard"

        self.table.setItem(row, 1, QTableWidgetItem(standard_path))
        status_item.setText(reset_status)
        self.update_buttons()

    def update_buttons(self):
        row = self.table.currentRow()

        if row < 0:
            self.remove_button.setEnabled(False)
            self.reset_button.setEnabled(False)
            return

        status_item = self.table.item(row, 2)
        if not status_item:
            self.remove_button.setEnabled(False)
            self.reset_button.setEnabled(False)
            return

        status = status_item.text()
        self.remove_button.setEnabled(status == "Brugerregel")
        self.reset_button.setEnabled(status == "Tilpasset")

    def update_developer_ui(self, *args):
        enabled = self.developer_checkbox.isChecked()
        self.developer_info.setVisible(enabled)
        self.save_all_styles_button.setVisible(enabled)

    def save_selected_styles(self):
        """Lad udvikleren vælge projektlag før der skrives til fællesmappen."""
        style_folder = self.current_style_folder()
        if not os.path.isdir(style_folder):
            QMessageBox.warning(
                self, "DMIKG Auto",
                f"Style-mappen blev ikke fundet:\n{style_folder}",
            )
            return

        layers = sorted(
            (layer for layer in QgsProject.instance().mapLayers().values()
             if layer.isValid()),
            key=lambda layer: layer.name().casefold(),
        )
        if not layers:
            QMessageBox.information(self, "DMIKG Auto", "Projektet har ingen gyldige lag.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Gem lagstyles")
        dialog.resize(560, 500)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(
            "Vælg de lag, hvis aktuelle QGIS-style skal gemmes i den fælles "
            "layer_styles-mappe. Ingen lag er valgt på forhånd."
        ))
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
        select_all = QPushButton("Vælg alle", dialog)
        deselect_all = QPushButton("Fravælg alle", dialog)
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
        save_button.setText("Gem valgte")
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
                self, "Samme lagnavn flere gange",
                "Flere valgte lag har samme navn og ville overskrive samme QML. "
                "Vælg kun ét lag pr. navn:\n" + "\n".join(duplicates),
            )
            return

        code, ok = QInputDialog.getText(
            self, "Bekræft udviklerhandling",
            "Indtast udviklerkoden for at fortsætte:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        if code != DEVELOPER_CODE:
            QMessageBox.warning(
                self, "Forkert kode", "Udviklerkoden er forkert. Ingen styles blev gemt."
            )
            return

        reply = QMessageBox.question(
            self,
            "Bekræft gemning af lagstyles",
            (
                f"Du er ved at gemme {len(selected)} valgte lagstyle(s) "
                "til den fælles layer_styles-mappe.\n\n"
                "Eksisterende standard-QML-filer vil blive overskrevet.\n\n"
                "Vil du fortsætte?"
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

            geojson_rule_key = None
            source_path = layer.source().split("|")[0]

            if source_path.casefold().endswith(".geojson"):
                geojson_name = os.path.splitext(
                    os.path.basename(source_path)
                )[0]

                for suffix, rule in GEOJSON_SUFFIX_STYLES.items():
                    if geojson_name.casefold().endswith(suffix.casefold()):
                        geojson_rule_key = suffix
                        break

            if geojson_rule_key:
                standard_path = get_geojson_style_path(
                    geojson_rule_key,
                    style_folder,
                )
                display_name = f"{name} ({geojson_rule_key})"
            else:
                if (
                    not name
                    or name in (".", "..")
                    or any(c in name for c in '<>:"/\\|?*')
                ):
                    failed.append(
                        f"{name}: Lagnavnet kan ikke bruges som filnavn."
                    )
                    continue

                standard_path = os.path.join(
                    style_folder,
                    f"{name}.qml"
                )
                display_name = name

            if not standard_path:
                failed.append(
                    f"{display_name}: Ingen style-sti er angivet for reglen."
                )
                continue

            destination_key = os.path.normcase(os.path.normpath(standard_path))
            if destination_key in destination_keys:
                failed.append(
                    f"{display_name}: Samme QML-destination som "
                    f"{destination_keys[destination_key]}. Vælg kun ét af dem."
                )
                continue
            destination_keys[destination_key] = display_name

            external_path = None
            settings = QSettings()
            custom_rules = settings.value(SETTINGS_KEY, [], type=list)

            rule_name = geojson_rule_key or name
            for custom_rule in custom_rules:
                if custom_rule.get("layer", "") != rule_name:
                    continue

                custom_path = custom_rule.get("style", "").strip()
                if custom_path:
                    same_path = (
                        os.path.normcase(os.path.normpath(custom_path))
                        == os.path.normcase(os.path.normpath(standard_path))
                    )
                    if not same_path:
                        external_path = custom_path
                break

            standard_exists = os.path.isfile(standard_path)
            external_exists = bool(
                external_path and os.path.isfile(external_path)
            )

            if standard_exists and external_exists:
                question = (
                    "Dette lag bruger en ekstern style-override.\n\n"
                    "Du er ved at overskrive standard-QML-filen med "
                    "lagets aktuelle style.\n\n"
                    f"Standardfil:\n{standard_path}\n\n"
                    f"Ekstern override:\n{external_path}\n\n"
                    "Den eksterne override-fil bliver ikke ændret.\n\n"
                    "Vil du fortsætte?"
                )

                reply = QMessageBox.question(
                    self,
                    "Bekræft overskrivning af standardstyle",
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
                    f"{display_name}: Mappen findes ikke: {target_folder}"
                )
                continue

            temp_path = None

            try:
                fd, temp_path = tempfile.mkstemp(
                    prefix=".dmikg_style_",
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
            f"Gemte styles: {len(saved)}",
            f"Fravalgt ved bekræftelse: {len(skipped)}",
            f"Fejl: {len(failed)}",
        ]
        if failed:
            summary.append("\nFejl:\n" + "\n".join(failed[:10]))
        QMessageBox.information(self, "DMIKG Auto – gemning færdig", "\n".join(summary))
        self.load_settings()

    @staticmethod
    def set_layer_checks(layer_list, state):
        for index in range(layer_list.count()):
            layer_list.item(index).setCheckState(state)

    def apply(self):
        rules = []

        for row in range(self.table.rowCount()):
            layer_item = self.table.item(row, 0)
            style_item = self.table.item(row, 1)
            status_item = self.table.item(row, 2)

            if not layer_item or not status_item:
                continue

            layer_name = layer_item.text().strip()
            status = status_item.text()
            style_path = style_item.text().strip() if style_item else ""

            if status in ("Standard", "GeoJSON"):
                continue

            if not layer_name or not style_path:
                continue

            rules.append({
                "layer": layer_name,
                "style": style_path,
                "status": status,
            })

        settings = QSettings()
        old_root_folder = settings.value(ROOT_FOLDER_KEY, get_root_folder(), type=str)
        new_root_folder = self.current_root_folder()

        settings.setValue(SETTINGS_KEY, rules)
        settings.setValue(ENABLED_KEY, self.enabled_checkbox.isChecked())
        settings.setValue(DEVELOPER_MODE_KEY, self.developer_checkbox.isChecked())
        settings.setValue(ROOT_FOLDER_KEY, new_root_folder)

        if self.enabled_changed_callback:
            self.enabled_changed_callback(self.enabled_checkbox.isChecked())

        if (
            self.root_folder_changed_callback
            and os.path.normcase(os.path.normpath(old_root_folder))
            != os.path.normcase(os.path.normpath(new_root_folder))
        ):
            self.root_folder_changed_callback()


class DmikgAutoOptionsFactory(QgsOptionsWidgetFactory):

    def __init__(
        self,
        enabled_changed_callback=None,
        root_folder_changed_callback=None,
    ):
        super().__init__()

        self.enabled_changed_callback = enabled_changed_callback
        self.root_folder_changed_callback = root_folder_changed_callback
        self.setTitle("DMIKG Auto")

        plugin_dir = os.path.dirname(__file__)
        self.icon_path = os.path.join(plugin_dir, "kds_logo.png")

    def icon(self):
        return QIcon(self.icon_path)

    def createWidget(self, parent):
        return DmikgAutoOptionsPage(
            parent,
            enabled_changed_callback=self.enabled_changed_callback,
            root_folder_changed_callback=self.root_folder_changed_callback,
        )
