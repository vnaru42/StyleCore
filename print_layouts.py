import os
import shutil

from qgis.core import (
    QgsApplication,
    QgsLayoutItemMap,
    QgsLayoutItemPicture,
    QgsMessageLog,
    QgsPrintLayout,
    QgsProject,
    QgsReadWriteContext,
    QgsRectangle,
    Qgis,
)
from qgis.PyQt.QtCore import QFile, QIODevice
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt.QtWidgets import QMessageBox

from .config import get_layout_folder


class DmikgPrintLayouts:
    """Synkroniserer, finder og åbner fælles QPT-printlayouts."""

    def __init__(self, iface):
        self.iface = iface


    def local_layout_folder(self):
        """Returnér brugerens lokale mappe til synkroniserede .qpt-filer."""
        profile_path = QgsApplication.qgisSettingsDirPath()

        if Qgis.QGIS_VERSION_INT >= 40000:
            profile_path = profile_path.replace("QGIS3", "QGIS4")

        return os.path.join(
            profile_path,
            "dmikg_auto",
            "layouts",
        )

    def sync_layouts(self):
        """Kopiér nyere fælles .qpt-filer til den lokale QGIS-profil."""
        source_folder = get_layout_folder()
        local_folder = self.local_layout_folder()

        if not os.path.isdir(source_folder):
            QgsMessageLog.logMessage(
                f"Print-layoutmappe ikke fundet: {source_folder}",
                "DMIKG Auto",
                level=Qgis.Warning,
            )
            return

        os.makedirs(local_folder, exist_ok=True)

        for filename in os.listdir(source_folder):
            if not filename.lower().endswith(".qpt"):
                continue

            source_file = os.path.join(source_folder, filename)
            local_file = os.path.join(local_folder, filename)

            should_copy = (
                not os.path.exists(local_file)
                or os.path.getmtime(source_file) > os.path.getmtime(local_file)
            )

            if not should_copy:
                continue

            try:
                shutil.copy2(source_file, local_file)
                QgsMessageLog.logMessage(
                    f"Print-layout opdateret: {filename}",
                    "DMIKG Auto",
                    level=Qgis.Info,
                )
            except Exception as exc:
                QgsMessageLog.logMessage(
                    f"Kunne ikke synkronisere print-layout {filename}: {exc}",
                    "DMIKG Auto",
                    level=Qgis.Warning,
                )

    def discover_layouts(self):
        """Find alle synkroniserede layouts dynamisk."""
        folder = self.local_layout_folder()
        if not os.path.isdir(folder):
            return []

        layouts = []
        for filename in sorted(os.listdir(folder), key=str.casefold):
            if filename.lower().endswith(".qpt"):
                layouts.append(
                    (
                        os.path.splitext(filename)[0],
                        os.path.join(folder, filename),
                    )
                )

        return layouts

    def create_layout_from_template(self, template_path):
        """Indlæs en .qpt, tilpas den til kortet og åbn Layout Designer."""
        if not os.path.isfile(template_path):
            QMessageBox.warning(
                self.iface.mainWindow(),
                "DMIKG Print",
                f"Layoutskabelonen blev ikke fundet:\n{template_path}",
            )
            return

        project = QgsProject.instance()
        document = QDomDocument()
        template_file = QFile(template_path)

        read_only = (
            QIODevice.OpenModeFlag.ReadOnly
            if hasattr(QIODevice, "OpenModeFlag")
            else QIODevice.ReadOnly
        )

        if not template_file.open(read_only):
            QMessageBox.warning(
                self.iface.mainWindow(),
                "DMIKG Print",
                f"Kunne ikke åbne layoutskabelonen:\n{template_path}",
            )
            return

        try:
            xml_result = document.setContent(template_file)

            xml_ok = xml_result[0] if isinstance(xml_result, tuple) else xml_result
            if not xml_ok:
                raise RuntimeError("QPT-filen kunne ikke læses som XML.")
        except Exception as exc:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "DMIKG Print",
                f"Kunne ikke læse layoutskabelonen:\n{exc}",
            )
            template_file.close()
            return
        finally:
            if template_file.isOpen():
                template_file.close()

        layout = QgsPrintLayout(project)
        layout.initializeDefaults()

        context = QgsReadWriteContext()
        result = layout.loadFromTemplate(document, context)

        layout_name = self.unique_layout_name(
            os.path.splitext(os.path.basename(template_path))[0]
        )
        layout.setName(layout_name)

        QgsMessageLog.logMessage(
            f"QPT indlæst: {template_path} ({result})",
            "DMIKG Auto",
            level=Qgis.Info,
        )

        self.fit_main_map_to_canvas(layout)
        self.apply_layout_svgs(layout)

        manager = project.layoutManager()
        if not manager.addLayout(layout):
            QMessageBox.warning(
                self.iface.mainWindow(),
                "DMIKG Print",
                f"Kunne ikke tilføje printlayoutet '{layout_name}' til projektet.",
            )
            return

        managed_layout = manager.layoutByName(layout_name)
        if managed_layout is None:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "DMIKG Print",
                f"Printlayoutet '{layout_name}' blev tilføjet, men kunne ikke findes igen.",
            )
            return

        self.iface.openLayoutDesigner(managed_layout)

    def unique_layout_name(self, base_name):
        """Undgå navnekollisioner hvis samme layout åbnes flere gange."""
        manager = QgsProject.instance().layoutManager()
        existing = {layout.name() for layout in manager.printLayouts()}

        if base_name not in existing:
            return base_name

        number = 2
        while f"{base_name}_{number}" in existing:
            number += 1

        return f"{base_name}_{number}"

    def fit_main_map_to_canvas(self, layout):
        """Sæt main_map og mini_map til canvas-udsnittet."""
        self.fit_map_item_to_canvas(layout, "main_map", warn_if_missing=True)
        self.fit_map_item_to_canvas(layout, "mini_map", warn_if_missing=False)

    def fit_map_item_to_canvas(self, layout, item_id, warn_if_missing=False):
        """Tilpas et map-item til QGIS-canvas uden at ændre dets proportioner."""
        map_item = layout.itemById(item_id)
        if not isinstance(map_item, QgsLayoutItemMap):
            if warn_if_missing:
                QgsMessageLog.logMessage(
                    f"Layoutet har ikke et map-item med id '{item_id}'.",
                    "DMIKG Auto",
                    level=Qgis.Warning,
                )
            return

        canvas_extent = self.iface.mapCanvas().extent()
        if canvas_extent.isEmpty():
            return

        item_size = map_item.sizeWithUnits()
        item_width = item_size.width()
        item_height = item_size.height()

        if item_width <= 0 or item_height <= 0:
            map_item.setExtent(canvas_extent)
            map_item.refresh()
            return

        target_ratio = item_width / item_height
        canvas_width = canvas_extent.width()
        canvas_height = canvas_extent.height()

        if canvas_width <= 0 or canvas_height <= 0:
            return

        canvas_ratio = canvas_width / canvas_height
        center = canvas_extent.center()

        if canvas_ratio > target_ratio:
            new_width = canvas_width
            new_height = new_width / target_ratio
        else:
            new_height = canvas_height
            new_width = new_height * target_ratio

        new_extent = QgsRectangle(
            center.x() - new_width / 2,
            center.y() - new_height / 2,
            center.x() + new_width / 2,
            center.y() + new_height / 2,
        )

        map_item.setExtent(new_extent)
        map_item.refresh()

    def apply_layout_svgs(self, layout):
        """Kobl SVG-filer til Picture-items med samme Item ID."""
        svg_folder = get_layout_folder()
        if not os.path.isdir(svg_folder):
            return

        for filename in os.listdir(svg_folder):
            if not filename.lower().endswith(".svg"):
                continue

            item_id = os.path.splitext(filename)[0]
            picture_item = layout.itemById(item_id)
            if not isinstance(picture_item, QgsLayoutItemPicture):
                continue

            svg_path = os.path.join(svg_folder, filename)
            picture_item.setPicturePath(svg_path)
            picture_item.refresh()

            QgsMessageLog.logMessage(
                f"Layout-SVG sat: {item_id} -> {svg_path}",
                "DMIKG Auto",
                level=Qgis.Info,
            )
