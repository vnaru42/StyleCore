import json
import os
import ntpath
import tempfile
import hashlib

from qgis.PyQt.QtCore import QSettings

from .language import tr


SETTINGS_KEY = "StyleCore/style_rules"  # Read only for migration of pre-1.8 overrides
LEGACY_RULES_OWNER_KEY = "StyleCore/legacy_rules_owner"
PERSONAL_RULES_PREFIX = "StyleCore/personal_style_rules/"
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
    # A missing selected UNC JSON must not switch to another organization's
    # bundled settings when the server is temporarily unavailable.
    if selected:
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
    return str(config.get("organization") or config.get("name") or tr('None')).strip()


def get_root_folder():
    config = load_external_config()
    if config.get("root_mode") == "config_dir":
        config_path = get_config_file()
        return os.path.normpath(os.path.dirname(os.path.abspath(config_path))) if config_path else ""
    config_root = str(config.get("root_folder", "")).strip()
    if config_root:
        return config_root
    # If a selected JSON is missing/invalid, never reuse an old profile root.
    if get_config_file():
        return ""
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


def _template_identity(value):
    """Normalize a stored template ID without discarding its subfolder.

    Legacy flat template names (with or without .qgs/.qgz) remain valid.
    IDs for templates in subfolders are relative to template_projects and
    use '/' as separator on Windows and other platforms.
    """
    name = str(value or '').strip().replace('\\', '/')
    if name.lower().endswith(('.qgs', '.qgz')):
        name = name[:-4]
    return name.strip('/')


def _template_ids(values):
    if not isinstance(values, list):
        return []
    result, seen = [], set()
    for value in values:
        name = _template_identity(value)
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            result.append(name)
    return result


def list_project_templates(root=None, external_templates=None):
    """Find source QGIS projects directly, including nested project folders.

    No source project or data file is copied or moved. A template's identity
    is its path relative to the templates folder (without extension), rather
    than its basename, so identical names in different folders are distinct.
    Existing flat names retain their previous IDs for config compatibility.
    """
    folder = os.path.join(root, get_folder_name('templates')) if root is not None and root else (
        get_template_folder() if root is None else '')
    result = []
    if folder and os.path.isdir(folder):
        for current_dir, dirs, filenames in os.walk(folder, followlinks=False):
            dirs.sort(key=str.casefold)
            for filename in sorted(filenames, key=str.casefold):
                if not filename.lower().endswith(('.qgs', '.qgz')):
                    continue
                path = os.path.join(current_dir, filename)
                if not os.path.isfile(path):
                    continue
                rel = os.path.relpath(path, folder).replace('\\', '/')
                key = _template_identity(rel)
                result.append({'key': key, 'label': key, 'path': path,
                               'kind': 'internal', 'relative_path': rel})

    # Do not silently discard .qgs or .qgz sharing a stem in the same folder.
    # Their IDs gain an extension only when both exist. The common case of a
    # single .qgz keeps its existing, backwards-compatible name.
    counts = {}
    for entry in result:
        key = entry['key'].casefold()
        counts[key] = counts.get(key, 0) + 1
    for entry in result:
        if counts[entry['key'].casefold()] > 1:
            extension = os.path.splitext(entry['relative_path'])[1].lower().lstrip('.')
            entry['key'] = _template_identity(entry['relative_path']) + '#' + extension
            entry['label'] = entry['relative_path']

    internal_keys = {entry['key'].casefold() for entry in result}
    external = get_external_templates() if external_templates is None else external_templates
    for row in external:
        if not isinstance(row, dict):
            continue
        name = str(row.get('name', '')).strip()
        value = str(row.get('path', '')).strip()
        if not name or not value:
            continue
        # Only conflicting IDs need the namespace; normal legacy external
        # names continue to be recognized without migrating shared JSON.
        key = name if name.casefold() not in internal_keys else '@external/' + name
        result.append({'key': key, 'label': name,
                       'path': resolve_external_template_path(value, root=root),
                       'kind': 'external', 'relative_path': value})

    # Case-insensitive identity is consistent with QGIS projects on Windows.
    return sorted(result, key=lambda entry: (entry['label'].casefold(), entry['key'].casefold(), entry['path'].casefold()))


def get_external_templates():
    """External QGIS project templates from the shared configuration."""
    raw = load_external_config().get("external_templates", [])
    if not isinstance(raw, list):
        return []
    return [dict(row) for row in raw if isinstance(row, dict)
            and str(row.get("name", "")).strip() and str(row.get("path", "")).strip()]


def resolve_external_template_path(value, root=None):
    """External paths in JSON are relative to the effective StyleCore root."""
    value = str(value or "").strip()
    if not value:
        return ""
    if os.path.isabs(value) or ntpath.isabs(value):
        return os.path.normpath(value)
    if root is None:
        root = get_root_folder()
    return os.path.normpath(os.path.join(root, value.replace('/', os.sep))) if root else ""


def portable_external_template_path(value, root=None):
    """Prefer relative references; different Windows drives require absolute paths."""
    if not value:
        return ""
    absolute = value if ntpath.isabs(value) else os.path.abspath(value)
    if root is None:
        root = get_root_folder()
    if not root:
        return absolute
    try:
        return os.path.relpath(absolute, root).replace("\\", "/")
    except ValueError:
        return absolute


def get_file_suffix_styles():
    """Return general file suffix rules (extension and suffix are both required)."""
    raw = load_external_config().get("file_suffix_styles", [])
    return raw if isinstance(raw, list) else []


def get_file_suffix_style_path(rule, style_folder=None):
    filename = str(rule.get('style_filename', '')).strip()
    if not filename:
        return ''
    folder = style_folder if style_folder is not None else get_style_folder()
    return resolve_style_path(filename, folder)


def source_filename(source):
    """Extract a real source filename from OGR and delimited-text URIs.

    Never infer a filename from a non-file provider URL.
    """
    from urllib.parse import urlsplit, unquote
    import ntpath
    raw = str(source or '').split('|', 1)[0]
    if raw.lower().startswith('file://'):
        parsed = urlsplit(raw)
        path = unquote(parsed.path)
        if parsed.netloc:
            path = '//' + parsed.netloc + path
    else:
        if '://' in raw:
            return ''
        path = raw.split('?', 1)[0]
    return ntpath.basename(path.replace('\\', '/'))


def match_file_suffix_rule(source, rules=None):
    """Choose the most specific matching file suffix rule.

    Longer filename suffixes take precedence. For equally long suffixes,
    an explicit extension wins over '*'. Configuration order breaks ties.
    """
    filename = source_filename(source)
    if not filename:
        return None
    stem, ext = os.path.splitext(filename)
    best_rule = None
    best_priority = (-1, -1)
    for rule in (get_file_suffix_styles() if rules is None else rules):
        if not isinstance(rule, dict):
            continue
        suffix = str(rule.get('suffix', '')).strip()
        extension = str(rule.get('extension', '')).strip()
        if not suffix or not extension:
            continue
        if extension != '*' and not extension.startswith('.'):
            extension = '.' + extension
        if not stem.casefold().endswith(suffix.casefold()):
            continue
        if extension != '*' and ext.casefold() != extension.casefold():
            continue
        priority = (len(suffix), int(extension != '*'))
        if priority > best_priority:
            best_rule, best_priority = rule, priority
    return best_rule


def _same_configuration(path_a, path_b):
    """Compare configuration identities across Windows UNC and regular paths."""
    return bool(path_a and path_b and os.path.normcase(os.path.abspath(path_a)) ==
                os.path.normcase(os.path.abspath(path_b)))


def bind_legacy_style_rules():
    """Pin pre-v1.8 QSettings rules to the config active at plugin startup.

    Never allow these profile-wide v1.7 rules to leak into a newly created or
    subsequently selected configuration. The next explicit Apply migrates them.
    """
    settings = QSettings()
    legacy = settings.value(SETTINGS_KEY, [], type=list)
    if not isinstance(legacy, list) or not legacy:
        return
    if settings.value(LEGACY_RULES_OWNER_KEY, "", type=str):
        return
    current = get_config_file()
    if current:
        settings.setValue(LEGACY_RULES_OWNER_KEY, current)


def _clean_rules(rules):
    if not isinstance(rules, list):
        return []
    result = []
    for item in rules:
        if not isinstance(item, dict):
            continue
        layer = str(item.get("layer", "")).strip()
        style = str(item.get("style", "")).strip()
        if layer and style:
            result.append({"layer": layer, "style": style})
    return result


def get_style_rules():
    """Shared layer-to-QML rules stored only in the active JSON file."""
    return _clean_rules(load_external_config().get('style_rules', []))


def _personal_rules_key(config_path=None):
    """Profile-specific rules scoped to exactly one configuration path."""
    path = config_path or get_config_file()
    if not path:
        return ""
    # Windows paths are case insensitive; use the same stable identity across
    # forward/backslash spellings without exposing UNC server details in keys.
    path = ntpath.normcase(ntpath.normpath(os.path.abspath(path)))
    # New configs also have a generation ID: replacing a config at the same
    # path will not reactivate personal overrides from an unrelated old config.
    generation = str(load_external_config(config_path or get_config_file()).get('config_id', '')).strip()
    digest = hashlib.sha256((path + '|' + generation).encode('utf-8')).hexdigest()
    return PERSONAL_RULES_PREFIX + digest


def get_personal_style_rules():
    key = _personal_rules_key()
    if not key:
        return []
    settings = QSettings()
    stored = settings.value(key, None)
    if stored is not None:
        return _clean_rules(stored)
    # v1.7 personal rules have no config ID. Their owner was pinned on initial
    # plugin startup, so they cannot leak to other organizations.
    owner = settings.value(LEGACY_RULES_OWNER_KEY, '', type=str)
    if _same_configuration(owner, get_config_file()):
        return _clean_rules(settings.value(SETTINGS_KEY, [], type=list))
    return []


def save_personal_style_rules(rules):
    """Save only in this user's QGIS profile, never write shared JSON."""
    key = _personal_rules_key()
    if not key:
        raise ValueError('Select a valid StyleCore configuration first.')
    clean = _validate_rules(rules)
    settings = QSettings()
    # An empty, explicitly stored list masks any old legacy rules.
    settings.setValue(key, clean)
    owner = settings.value(LEGACY_RULES_OWNER_KEY, '', type=str)
    if _same_configuration(owner, get_config_file()):
        settings.remove(SETTINGS_KEY)
        settings.remove(LEGACY_RULES_OWNER_KEY)
    settings.sync()


def _validate_rules(rules):
    clean = _clean_rules(rules)
    seen = set()
    for r in clean:
        name = r['layer'].casefold()
        if name in seen:
            raise ValueError(f'Duplicate layer style rule: {r["layer"]}')
        seen.add(name)
    return clean


def config_signature(config_path=None):
    path = config_path or get_config_file()
    if not path or not os.path.isfile(path):
        return None
    with open(path, 'rb') as file:
        return hashlib.sha256(file.read()).hexdigest()


def get_effective_style_rules():
    """Personal mappings override shared mappings, case-insensitively."""
    personal = get_personal_style_rules()
    shared = get_style_rules()
    matched = {r['layer'].casefold() for r in personal}
    return personal + [r for r in shared if r['layer'].casefold() not in matched]


def resolve_style_path(value, style_folder=None):
    """Resolve a QML filename relative to the active styles folder."""
    value = str(value or '').strip()
    if not value:
        return ''
    if os.path.isabs(value) or ntpath.isabs(value):
        return value
    folder = style_folder if style_folder is not None else get_style_folder()
    return os.path.normpath(os.path.join(folder, value.replace('\\', os.sep))) if folder else ''


def portable_style_path(path, style_folder):
    """Store styles under the shared style root by relative filename/path."""
    path = os.path.normpath(str(path or '').strip())
    if not path:
        return ''
    if not os.path.isabs(path) and not ntpath.isabs(path):
        return path.replace('\\', '/')
    if not style_folder:
        return path
    try:
        base = os.path.normcase(os.path.realpath(style_folder))
        candidate = os.path.normcase(os.path.realpath(path))
        if os.path.commonpath([base, candidate]) == base:
            return os.path.relpath(path, style_folder).replace(os.sep, '/')
    except (ValueError, OSError):
        pass
    return path


def save_configuration_settings(style_rules, restyle_templates, root_folder, expected_signature=None, file_suffix_styles=None, external_templates=None, inactive_templates=None):
    """Atomically update only the active config; preserve all other JSON keys."""
    config_path = get_config_file()
    if not config_path or not os.path.isfile(config_path):
        raise FileNotFoundError('No active StyleCore configuration file was found.')
    config = load_external_config(config_path)
    if not config:
        raise ValueError('The active StyleCore configuration could not be read.')

    if config.get('root_mode') != 'config_dir' and not str(root_folder or '').strip():
        raise ValueError('A StyleCore resource root folder must be selected.')
    cleaned = _validate_rules(style_rules)

    templates = _template_ids(restyle_templates)

    if expected_signature is not None and config_signature(config_path) != expected_signature:
        raise RuntimeError("Shared configuration was changed by another user. Reload StyleCore settings before saving.")

    config['root_folder'] = '' if config.get('root_mode') == 'config_dir' else str(root_folder).strip()
    config['style_rules'] = cleaned
    config['restyle_on_open'] = templates
    if external_templates is not None:
        config['external_templates'] = external_templates
    if inactive_templates is not None:
        config['inactive_templates'] = _template_ids(inactive_templates)
    # Discard configuration keys from the retired template-sync and GeoJSON rules.
    config.pop('templates_menu_only', None)
    if file_suffix_styles is not None:
        config['file_suffix_styles'] = file_suffix_styles
    config.pop('geojson_suffix_styles', None)

    # Create a temporary file beside the JSON for safe replacement, including
    # network shares; never partially truncate a production configuration.
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix='.stylecore_config_', suffix='.tmp',
                                   dir=os.path.dirname(os.path.abspath(config_path)))
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(tmp, config_path)
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)

    return config


def get_inactive_templates():
    """Templates hidden from the StyleCore menu (default: all templates active)."""
    return _template_ids(load_external_config().get('inactive_templates', []))


def get_restyle_templates():
    """Return selected template IDs, retaining their relative folder paths."""
    return _template_ids(load_external_config().get('restyle_on_open', []))


def get_developer_code():
    config = load_external_config()
    code = str(config.get("developer_code", "")).strip()
    return code or "StyleCore"


