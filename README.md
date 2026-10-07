# StyleCore

StyleCore is a QGIS plugin for managing and distributing layer styles, project templates, and print layouts through a shared or local configuration.

Each setup is controlled by a JSON configuration file, making it suitable for both individual users and shared environments.

## Installation

1. Download the StyleCore ZIP file.
2. Open QGIS.
3. Go to **Plugins > Manage and Install Plugins**.
4. Select **Install from ZIP**.
5. Choose the StyleCore ZIP file.
6. Confirm the installation.

After installation, StyleCore is available from the QGIS plugin interface and under **Settings > Options > StyleCore**.

## Configuration

StyleCore uses a JSON configuration file to define where styles, project templates, and print layouts are stored.

For use in shared environment and organizations, its best distributed with predefined configuration file for ease of use.

Under **Settings > Options > StyleCore**, you can:

- **Load configuration...** – Select an existing StyleCore JSON configuration.
- **New configuration...** – Create and save a new StyleCore JSON configuration.

StyleCore remembers the last selected configuration and automatically loads it the next time QGIS starts.

If no configuration has been selected, StyleCore looks for:

```text
config/stylecore_config.json
```

inside the plugin folder.

This makes it possible to distribute StyleCore with a ready-to-use default configuration.

Configuration files can have any filename, as long as they are valid JSON files.

### Example resource structure

```text
StyleCore_resources/
├── layer_styles/
├── template_projects/
└── layouts/
```

### Example configuration

```json
{
  "name": "My StyleCore Configuration",
  "root_folder": "C:/QGIS/StyleCore_resources",
  "folders": {
    "styles": "layer_styles",
    "templates": "template_projects",
    "layouts": "layouts"
  },
  "geojson_suffix_styles": {},
  "restyle_on_open": [
    "template_main",
    "template_placeholder_2",
    "template_placeholder_3"
  ]
}
```

## Automatic Layer Styling

StyleCore can automatically apply QML styles when layers are added to a QGIS project.

When a new layer is added, StyleCore checks the active configuration and looks for a matching style rule. 
If a matching QML file is found, the style is applied automatically.

This allows users to add commonly used layers without manually locating and applying the correct QML file each time.

Automatic styling can be enabled or disabled from the StyleCore interface.

## Layer Style Matching

Standard style rules can be based on layer names.

QML files are stored in the configured `layer_styles` folder. 
StyleCore uses the active configuration to determine which style should be applied to each layer.

This makes it possible to maintain one shared set of styles for multiple users.

## GeoJSON Suffix Rules

StyleCore supports optional style rules for GeoJSON files based on filename suffixes.

These rules are stored in the configuration under:

```json
"geojson_suffix_styles": {}
```

This is useful when exported GeoJSON files follow a predictable naming pattern and should automatically receive different styles.

For example, separate styles can be assigned to point, observation, or control-point exports without changing the plugin code.

## Local Style Overrides

StyleCore supports local or shared style overrides.

Overrides can be used when a specific environment needs a different QML style than the default style supplied with a configuration.

If an override exists, StyleCore can use it instead of the standard style. 
If no override is available, StyleCore falls back to the normal configured style.

This allows a shared StyleCore setup to remain stable while still supporting local variations.

## Project Templates

Project templates are stored in the configured template folder.

```text
template_projects/
```

StyleCore synchronizes the configured templates with the QGIS project template location so they are available when creating or opening projects.

This allows a shared set of project templates to be distributed without manually copying them into each QGIS profile.

## Refreshing Layer Styles When Templates Open

StyleCore can refresh all existing layers in selected project templates when those templates are opened.

This is useful for templates containing predefined layers that should always use the latest available QML styles.

The templates that should be refreshed are selected under:

**Settings > Options > StyleCore > Template refresh**

StyleCore automatically lists `.qgz` and `.qgs` files found in the configured template folder.

Select the templates that should have their existing layers checked and restyled when opened.

The selected template names are stored in the active configuration under:

```json
"restyle_on_open": [
  "template_main",
  "template_placeholder_2",
  "template_placeholder_3"
]
```

Template names are stored without the `.qgz` or `.qgs` file extension.

Each configuration can define its own templates.

Templates listed in the configuration remain visible in the settings even if the corresponding project file does not currently exist. 
This makes it possible to prepare configuration entries for templates that will be added later.

## Print Layouts

QGIS print layout templates are stored in the configured `layouts` folder as `.qpt` files.

```text
layouts/
```

StyleCore automatically scans this folder and adds the available layouts to the plugin menu.

Selecting a layout opens it in the QGIS Layout Designer.

### Recommended map Item IDs

For automatic map handling, the following Item IDs are recommended:

- `main_map` – Uses the current QGIS map canvas extent.
- `mini_map` – Uses the same initial extent and can be configured as an overview map.

Layouts can contain additional items normally. Only the recognised Item IDs receive special handling from StyleCore.

## SVG Files in Print Layouts

SVG graphics used by print layouts can be stored in the same `layouts` folder.

To automatically connect an SVG file to a QGIS Picture item, use the same name for the SVG file and the Picture item's Item ID.

Example:

```text
company_logo.svg
```

should match a Picture item with:

```text
company_logo
```

This makes layouts more portable because required graphics can be distributed together with the layout files.

## Saving Layer Styles

StyleCore includes a developer workflow for saving layer styles from the current QGIS project as QML files.

When saving styles, the user can select which project layers should be included.

This is useful when maintaining or expanding a shared StyleCore configuration:

1. Style a layer normally in QGIS.
2. Open the StyleCore style-saving tool.
3. Select the layers whose styles should be saved.
4. Save the selected styles to the configured style location.

Existing QML files are protected by an overwrite confirmation before they are replaced.

## Shared Configurations

A StyleCore configuration can point to either local folders or shared network folders.

This makes it possible for several users to use the same:

- layer styles
- project templates
- print layouts
- GeoJSON rules
- template refresh settings

without modifying the StyleCore plugin itself.

For organization-specific setups, the recommended approach is to keep the generic StyleCore plugin unchanged and distribute a separate 
configuration and resource folder.

## Version

1.6.0
