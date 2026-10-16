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

- **New configuration...** – Create a JSON configuration and three resource folders, using only the QGIS dialog.
- **Load configuration...** – Open a shared configuration on your local/network drive.
- **Shared automatic layer styles (JSON)** – View the organization's mappings, including arbitrary layer names mapped to arbitrary `.qml` filenames.
- **Edit shared configuration (administrator)** – Explicitly enable shared editing before changing shared mappings, resource roots, or the list of templates refreshed on open. The shared JSON is written only when these settings really change.
- **Personal style overrides** – Map any layer name to a different QML **without changing the shared JSON**. They are saved in your local QGIS profile and scoped to the selected configuration.
- **Reset to shared default** – Select a personal override, remove it and click **Apply**. The next automatic styling event will use the original shared mapping or default name matching.

**Important:** The administrator checkbox is not an access-control system. Use server file permissions to give only administrators write access to the shared JSON and QML files. Other users require read access only to load and use them.

### Style priority

1. Personal layer/suffix override, when present and valid.
2. Shared explicit layer/suffix mapping from JSON.
3. Standard QML with the same name as the layer, or configured GeoJSON suffix QML (for this fallback, the newest existing candidate wins).
4. If nothing can be loaded, leave the current layer style unchanged.

A missing or invalid personal QML falls through to the shared default. Several different layers may reference the same QML. QML files inside the shared styles folder are recorded relative to that folder. Personal overrides can also refer to a file elsewhere on the user's computer.

Reset does **not** immediately restyle layers in existing saved projects: StyleCore preserves saved project styling unless the project is an opted-in template. You can explicitly update existing layers using **Manual Style Update**. Applying a manual style never creates an automatic association.

To share a new setup, distribute the JSON **and the shared resource folders**, and ensure the same UNC root path and data sources are accessible on all colleagues' PCs. Existing Oracle/WMS/WFS source permissions, local fonts and external SVG paths are not bundled in the JSON.

### Upgrading from earlier versions

Old v1.7 profile-wide `StyleCore/style_rules` are treated as personal overrides of the configuration that was active at startup. They are moved into config-specific local settings when the user saves personal overrides, not automatically to a shared JSON. If v1.8.0-beta1 had previously written a user's personal choice into `style_rules` in a shared JSON, review that JSON as an administrator: beta2 cannot reliably identify which shared mappings were intended to be personal.

Template copies are now tracked in a local manifest to prevent collisions when changing configurations. StyleCore only removes previously managed, unmodified copies. Existing template copies from pre-beta2 versions are untracked; if a same-name file conflicts, it is preserved with a warning rather than silently overwritten. Resolve these conflicts manually using QGIS' local `project_templates` folder.

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
  "style_rules": [
    {"layer": "GNSS_PUNKTER", "style": "GNSS_Diamant.qml"}
  ],
  "file_suffix_styles": [],
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

Standard style rules can be based on layer names. **You can also assign any QML
filename to any layer name through the StyleCore settings table:** click Add,
enter the layer name, double-click the style path cell, and pick a QML. Click
Apply to save the mapping to the active configuration file. The JSON stores
files located inside the configured styles folder as relative paths, so the
association travels with the configuration. A style outside the styles folder
is stored as an absolute path, with a portability warning.

Explicit configuration mappings take precedence over name matching. Switching
configuration replaces these mappings; rules from another configuration do not
carry over. An existing configuration from v1.7 without a style_rules field
continues to support ordinary name matching and can be upgraded through Apply.
Legacy profile-wide mappings from v1.7 are offered only in the configuration
active on the first v1.8 start and are migrated when you press Apply.

QML files are stored in the configured `layer_styles` folder. 
StyleCore uses the active configuration to determine which style should be applied to each layer.

This makes it possible to maintain one shared set of styles for multiple users.

## Manual Style Update

Choose **Manual Style Update...** from the StyleCore toolbar menu to update styles on layers in an existing QGIS project, including older Oracle layers.

Select a layer and review the suggested QML style, or browse for a different `.qml` file. Click **Use Style** to apply the style only to that selected layer. Save the QGIS project to keep the change.

Suggestions can match the QGIS layer name or the underlying Oracle table/view name. **No automatic styling rule or permanent Oracle source association is created**, and other existing projects are not changed.

## GeoJSON Suffix Rules

StyleCore supports optional style rules for GeoJSON files based on filename suffixes.

These rules are stored in the configuration under:

```json
"file_suffix_styles": []
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

Only a genuine template project from the configured template directory or QGIS' local template directory (or an unsaved project identified as a template) is eligible for automatic restyling. A separately saved project with the same title is not eligible. Test **New from Template** on your specific QGIS version before wide rollout.

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

If the layout contains a map item with the Item ID `main_map`, StyleCore selects that map and activates **Move Item Content** automatically. You can immediately drag the map contents without selecting the tool yourself.

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
- explicit layer-to-QML associations

without modifying the StyleCore plugin itself.

For organization-specific setups, the recommended approach is to keep the generic StyleCore plugin unchanged and distribute a separate 
configuration and resource folder.

## Version

1.7.0

## Notes for Shared Network Configurations (v1.8 beta)

- Place the JSON and the three resource folders on a UNC network share readable
  by all users. Each colleague installs the same public StyleCore plugin and
  selects that configuration from **Load Configuration**.
- The JSON must be writable by the person editing settings; other users only
  need read access. Coordinate changes to a shared config to avoid overwrites.
- Data sources in QGIS project templates (Oracle, WFS, files, etc.) must also
  be accessible to each colleague; StyleCore does not distribute those sources.
- Developer **Save Layer Styles** respects explicit QML mappings when their
  destination lies inside the configured shared styles folder. External styles
  are not overwritten automatically.
- The local automatic-styling enabled toggle remains a personal QGIS setting.


## v1.8.0-beta3 – Settings organization

The ordinary colleague workflow is at the top of Settings: automatic styling, personal QML overrides, per-layer reset, and Reset All. Personal edits are stored in the local QGIS profile, scoped to the active configuration, not in its shared JSON. Apply previews changed personal styles on matching layers in the currently open QGIS project when a QML is available; it does not modify saved projects elsewhere.

Configuration and Developer are collapsed sections. Creating a new configuration prompts for a developer code (entered twice). Unlocking Developer requires that configuration's code. Shared mappings, template refresh, root directory, GeoJSON filename suffix rules, and shared QML saving are under Developer. Shared JSON is modified only after the additional Edit Shared Configuration choice and Apply.

Note: The developer code is stored in plain text in the configuration JSON and is an interface guard, not secure access control. Shared server file permissions must enforce actual write restrictions. Existing configs without a developer_code continue to use the legacy default code. If no shared QML can be found for a removed personal override, existing project styling remains and a warning appears.


## File Suffix Rules (v1.8.0)

Developers can configure filename suffix rules with an explicit file extension and a QML file in **Settings → StyleCore → Developer → File Suffix Rules**. A match requires both the filename stem to end with the configured suffix and the source file extension to equal the configured extension (case-insensitive). Examples: `-observations` with `.geojson` or `-result` with `.shp`. Delimited text layers must be loaded through QGIS first. GeoPackage rules match the source file as a whole, not individual internal layers. Old `geojson_suffix_styles` entries are no longer read. Remove or convert them to `file_suffix_styles` manually (or recreate them through QGIS Developer settings); the old entries are not imported automatically. Personal overrides and exact layer mappings retain higher priority.


### File type wildcard

The **File type** column is a free-text field (no dropdown). Enter `kml` or `.kml`; StyleCore normalizes both to `.kml` when saving. Use `*` in the **File type** column to apply a suffix rule to any file extension. Rules are evaluated in table order, and only the first matching File Suffix Rule is used.
