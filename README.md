# StyleCore

**StyleCore 1.9.0** is a QGIS plugin for managing QML layer styles, project templates, and print layouts from a local or shared configuration. It is designed for teams that want consistent QGIS styling without manually applying styles every time a layer is added.

**Requirements:** QGIS 3.44 (see `metadata.txt` for the official supported version range). Data sources, SVG files and network shares must be accessible to each user. Optional fonts can be supplied in the active resource root as described below.

**Documentation:** https://vnaru42.github.io/StyleCore-Docs/
**Report a bug:** https://github.com/vnaru42/StyleCore/issues/new

## Installation

1. Download the StyleCore plugin ZIP.
2. In QGIS, open **Plugins > Manage and Install Plugins > Install from ZIP**.
3. Select the ZIP and install it.
4. Open **Settings > Options > StyleCore** to create or load a configuration.

The toolbar dropdown also contains unobtrusive **Help & Documentation** and **Report an Issue** links.

## Configuration

StyleCore uses a JSON configuration file to locate shared or local resources. Use **New configuration** to create a configuration and resource folders, or **Load configuration** to select an existing JSON file (including one on a UNC network path). When creating a configuration, choose the **Configuration file** location directly in the dialog.

A configuration can reference:

- **QML styles** for automatic styling and shared mappings.
- **QGIS project templates** (`.qgz` / `.qgs`).
- **Print layout templates** (`.qpt`) and supporting SVG graphics.
- **File Suffix Rules** for exported datasets with predictable filenames.
- **Selected templates to restyle** when opened.
- **Fonts from root folder**

### Resource root location

By default, **Use configuration file folder as resource root** makes the folder containing the JSON file the resource root (`root_mode: "config_dir"`). Moving the JSON file together with its resource folders lets users reconnect by loading the JSON from its new location.

Uncheck this option to choose a separate root folder (`root_mode: "custom"`). Shared resource paths can be relative to the active root; external absolute paths must still be accessible. The last selected configuration is remembered.

### Shared configurations and developer settings

The **Developer** section manages the shared root folder, automatic layer style mappings, File Suffix Rules, and template refresh settings. A `...` browse control in shared automatic style mappings lets developers select QML files directly. Authorized developers can also save selected QGIS layer styles as QML files in the configured shared style location.

Shared configuration changes are written to the selected JSON file when saved. Colleagues using that JSON receive the updated configuration when they reload it. Keep shared JSON and resource folders in a location accessible to the team.

Developer codes are a user-interface guard, **not a security boundary**. Use filesystem and server permissions to control who can edit shared configuration and style files. StyleCore checks for changes made to the shared configuration by another editor and can reject a conflicting save; reload the configuration before trying again.

## Optional fonts folder

StyleCore can make additional fonts available to QGIS from an optional `fonts` directory directly inside the active configuration's **root_folder**:

```text
StyleCore_resources/
├── layer_styles/
├── template_projects/
├── layouts/
└── fonts/                  # Optional; create it only if needed
    ├── Company-Regular.ttf
    └── Company-Bold.otf
```

When StyleCore starts or the active configuration is changed, it looks for `root_folder/fonts` and registers that directory with QGIS' font manager. Both `.ttf` and `.otf` files are supported. Missing or empty `fonts` directories are silently ignored; the folder is not automatically created, and no JSON setting or Developer option is required.

Only supply fonts you are legally permitted to share. Ensure colleagues can access and locally synchronize the font files. QGIS may need its text rendering refreshed, or a restart, if fonts are changed while it is running. Previously registered fonts may remain available for the rest of the QGIS session after changing configurations.

## Automatic layer styling

When automatic styling is enabled and a new layer is added, StyleCore looks for a matching QML. This can include:

- A **personal override**, stored locally for the selected configuration.
- An **explicit shared layer-to-QML mapping**.
- A **File Suffix Rule** based on the source filename and extension.
- A **QML named after the QGIS layer**, as a fallback.

If no usable QML is found, the existing layer style is left unchanged. You can switch **Automatic Styling** on or off from the StyleCore dropdown; its status is shown in the menu. Switching it off does not restyle layers already loaded.

### File Suffix Rules

Developers configure File Suffix Rules in **Settings > Options > StyleCore > Developer**. Each row contains a **suffix**, a **file type**, and a **QML style**.

| Suffix | File type | QML style |
| --- | --- | --- |
| `-points` | `.geojson` | `Points.qml` |
| `-survey` | `.shp` | `Survey.qml` |
| `-results` | `*` | `Results.qml` |

The suffix is matched against the **filename without its extension**. File type is a **free-text field**, not a dropdown: enter `.kml`, `kml`, `.txt`, `.shp`, or another extension. Extensions are normalized and matched case-insensitively. Use `*` to match any extension.

If multiple rules match, the **longest matching suffix wins**. If suffix lengths are equal, an **explicit file type wins over `*`**. This is independent of rule order; equal-specificity ties follow configuration order.

QGIS must first load the file as a valid layer. For example, text exports may need to be imported through QGIS **Delimited Text**. GeoPackage rules identify the source file, not individual internal tables, so multiple layers from one package may match the same rule.

## Personal style overrides

Users can select an alternative QML for a layer without editing the shared JSON. Personal overrides are stored in the local QGIS profile and scoped to the active configuration.

An individual override can be removed to return to shared styling, or all personal overrides can be reset. Resetting a personal override does not rewrite other users' settings. Existing saved QGIS projects are not indiscriminately restyled just because an override changes.

## Project templates

StyleCore opens `.qgs` and `.qgz` project templates **directly from the configured templates folder**, including its subfolders, using the StyleCore **New from Template** menu. It does not copy these templates into QGIS' standard local `project_templates` directory.

Each template can be marked **Active** to appear in the template menu and **Refresh** to check its layers for updated QML styling when opened. Refresh only applies to selected templates, **not unrelated existing saved projects**. Templates should use portable data source paths where possible; the referenced files and services must be accessible to users.

## Print layouts

Place `.qpt` layout templates in the configured layouts folder. StyleCore lists them in its print-layout menu and opens the selected layout in QGIS Layout Designer.

For layout automation, assign item IDs:

- `main_map`: the map item initially follows the QGIS canvas extent; StyleCore selects it and activates **Move Item Content** when opening the layout.
- `mini_map`: an optional overview map item that receives the corresponding initial extent handling.

Picture items can use SVG assets kept with the layouts: name the SVG after the Picture item's Item ID to support automatic lookup.

## Manual Style Update

Use **Manual Style Update** from the StyleCore toolbar to apply a chosen QML to selected layers in an existing project, including Oracle-backed layers. Style suggestions can use a layer name or Oracle table/view identity.

Applying a manual style is an **explicit per-layer action**. It does not create a persistent automatic rule for that Oracle source or silently change other projects. Save the QGIS project to retain the selected styling.

## Saving shared QML styles

Developers can select layers from the current QGIS project and save their styling as QML into the configured style location. Existing destination QML files require overwrite confirmation. Shared paths and actual write permissions determine whether a save can succeed.

## Troubleshooting

- **A style was not applied:** Check that automatic styling is enabled, the active configuration is correct, the QML exists and is readable, and the source filename matches the rule.
- **A colleague does not see updates:** Reload the shared configuration and ensure the resource paths are accessible.
- **The configured JSON file cannot be found:** StyleCore warns when a previously selected configuration is missing. Open Settings and select the correct JSON file.
- **An older configuration has an absolute root path:** It remains supported. To make the configuration portable, back up the JSON and select the configuration-file folder as resource root; keep its resource folders together and review any absolute paths within the configuration.
- **A template is missing from the menu:** Check its **Active** setting and that the `.qgs`/`.qgz` file is in the configured templates folder.
- **A template uses the wrong data:** Confirm that its Oracle, file, WMS, or WFS sources are accessible from that workstation.
- **A font is missing:** Put licensed `.ttf`/`.otf` files in `root_folder/fonts`, check that the directory is accessible, then reload the configuration or restart QGIS.
- **An SVG is missing:** Check the external SVG path or the configured layouts directory.

Issues and feedback: https://github.com/vnaru42/StyleCore/issues

## License

Copyright (C) 2026 Angelo Jensen Dobbs

StyleCore is licensed under the GNU General Public License v3.0 or later.

See the [LICENSE](LICENSE) file for the full license text.