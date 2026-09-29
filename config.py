import os

from qgis.PyQt.QtCore import QSettings


SETTINGS_KEY = "DMIKG_Auto/style_rules"
ENABLED_KEY = "DMIKG_AUTO/enabled"
ROOT_FOLDER_KEY = "DMIKG_AUTO/root_folder"
DEVELOPER_MODE_KEY = "DMIKG_AUTO/developer_mode"

DEFAULT_ROOT_FOLDER = r"\\prod.sitad.dk\dfs\CU2314\F-DREV\GDL\Software\QGIS_komplet_stytem"

DEVELOPER_CODE = "DMIKG"

GEOJSON_SUFFIX_STYLES = {
    "-kon-observationer": {
        "name": "-kon-observationer.geojson",
        "style_filename": "kon_observationer.qml",
    },
    "-kon-punkter": {
        "name": "-kon-punkter.geojson",
        "style_filename": "kon_punkter.qml",
    },
    "-observationer": {
        "name": "-observationer.geojson",
        "style_filename": "observationer.qml",
    },
    "-punkter": {
        "name": "-punkter.geojson",
        "style_filename": "punkter.qml",
    },
}


def get_root_folder():
    return QSettings().value(
        ROOT_FOLDER_KEY,
        DEFAULT_ROOT_FOLDER,
        type=str,
    )


def get_style_folder():
    return os.path.join(get_root_folder(), "layer_styles")


def get_template_folder():
    return os.path.join(get_root_folder(), "template_projects")


def get_layout_folder():
    return os.path.join(get_root_folder(), "layouts")


def get_geojson_style_path(suffix, style_folder=None):
    """Returnér standard-QML-stien for en GeoJSON suffix-regel."""
    rule = GEOJSON_SUFFIX_STYLES.get(suffix, {})
    filename = rule.get("style_filename", "")
    if not filename:
        return ""

    return os.path.join(style_folder or get_style_folder(), filename)
