import json
import os

from qgis.PyQt.QtCore import QSettings

from .language import tr


SETTINGS_KEY = "StyleCore/style_rules"
ENABLED_KEY = "StyleCore/enabled"
ROOT_FOLDER_KEY = "StyleCore/root_folder"
DEVELOPER_MODE_KEY = "StyleCore/developer_mode"
CONFIG_FILE_KEY = "StyleCore/config_file"

BUNDLED_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")
BUNDLED_CONFIG_FILENAMES = ("stylecore_config.json", "StyleCore_config.json")

DEFAULT_FOLDER_NAMES = {
    "styles": "layer_styles",
    "templates": "template_projects",
    "layouts": "layouts",
}


def get_bundled_config_file():
    for filename in BUNDLED_CONFIG_FILENAMES:
        path = os.path.join(BUNDLED_CONFIG_DIR, filename)
        if os.path.isfile(path):
            return path

    if os.path.isdir(BUNDLED_CONFIG_DIR):
        json_files = sorted(
            filename for filename in os.listdir(BUNDLED_CONFIG_DIR)
            if filename.lower().endswith(".json")
        )
        if len(json_files) == 1:
            return os.path.join(BUNDLED_CONFIG_DIR, json_files[0])

    return ""


def get_config_file():
    """Return the last selected config, otherwise the bundled default config."""
    selected = QSettings().value(CONFIG_FILE_KEY, "", type=str).strip()
    if selected and os.path.isfile(selected):
        return selected

    return get_bundled_config_file()


def load_external_config(path=None):
    config_path = (path or get_config_file()).strip()
    if not config_path or not os.path.isfile(config_path):
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_configuration_name():
    config = load_external_config()
    return str(config.get("organization") or config.get("name") or tr("Ingen")).strip()


def get_root_folder():
    config = load_external_config()
    config_root = str(config.get("root_folder", "")).strip()
    if config_root:
        return config_root

    return QSettings().value(ROOT_FOLDER_KEY, "", type=str).strip()


def get_folder_name(key):
    config = load_external_config()
    folders = config.get("folders", {})
    if isinstance(folders, dict):
        value = str(folders.get(key, "")).strip()
        if value:
            return value
    return DEFAULT_FOLDER_NAMES[key]


def get_style_folder():
    root = get_root_folder()
    return os.path.join(root, get_folder_name("styles")) if root else ""


def get_template_folder():
    root = get_root_folder()
    return os.path.join(root, get_folder_name("templates")) if root else ""


def get_layout_folder():
    root = get_root_folder()
    return os.path.join(root, get_folder_name("layouts")) if root else ""


def get_geojson_suffix_styles():
    config = load_external_config()
    rules = config.get("geojson_suffix_styles", {})
    return rules if isinstance(rules, dict) else {}



def get_restyle_templates():
    """Return project template basenames that should be restyled when opened."""
    config = load_external_config()
    values = config.get("restyle_on_open", [])
    if not isinstance(values, list):
        return []

    result = []
    seen = set()
    for value in values:
        name = os.path.splitext(os.path.basename(str(value).strip()))[0]
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            result.append(name)
    return result


def save_restyle_templates(template_names):
    """Write the restyle-on-open template list to the active JSON configuration."""
    config_path = get_config_file()
    if not config_path or not os.path.isfile(config_path):
        raise FileNotFoundError("No active StyleCore configuration file was found.")

    config = load_external_config(config_path)
    if not config:
        raise ValueError("The active StyleCore configuration could not be read.")

    cleaned = []
    seen = set()
    for value in template_names:
        name = os.path.splitext(os.path.basename(str(value).strip()))[0]
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            cleaned.append(name)

    config["restyle_on_open"] = cleaned

    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

def get_developer_code():
    config = load_external_config()
    code = str(config.get("developer_code", "")).strip()
    return code or "StyleCore"


def get_geojson_style_path(suffix, style_folder=None):
    rule = get_geojson_suffix_styles().get(suffix, {})
    if not isinstance(rule, dict):
        return ""

    filename = str(rule.get("style_filename", "")).strip()
    if not filename:
        return ""

    folder = style_folder if style_folder is not None else get_style_folder()
    return os.path.join(folder, filename) if folder else ""
