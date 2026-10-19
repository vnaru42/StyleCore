# StyleCore

**StyleCore 1.8.1** is a QGIS plugin for managing QML layer styles, project templates, and print layouts from a local or shared configuration. It is designed for teams that want consistent QGIS styling without manually applying styles every time a layer is added.

**Requirements:** QGIS 3.44 or later (see `metadata.txt` for supported versions). Data sources, external fonts, SVG files, and network shares must be accessible to each user; StyleCore does not install or distribute them automatically.

**Documentation:** https://vnaru42.github.io/StyleCore-Docs/  
**Report a bug:** https://github.com/vnaru42/StyleCore/issues/new

## Installation

1. Download the StyleCore plugin ZIP.
2. In QGIS, open **Plugins > Manage and Install Plugins > Install from ZIP**.
3. Select the ZIP and install it.
4. Open **Settings > Options > StyleCore** to create or load a configuration.

The toolbar dropdown also contains unobtrusive **Help & Documentation** and **Report an Issue** links.

## Configuration

StyleCore uses a JSON configuration file to locate shared or local resources. Use **New configuration** to create a configuration and resource folders, or **Load configuration** to select an existing JSON file (including one on a UNC network path).

A configuration can reference:

- **QML styles** for automatic styling and shared mappings.
- **QGIS project templates** (`.qgz` / `.qgs`).
- **Print layout templates** (`.qpt`) and supporting SVG graphics.
- **File Suffix Rules** for exported datasets with predictable filenames.
- **Selected templates to restyle** when opened.

The last selected configuration is remembered. Shared resource paths can be relative to the configured root folder; external absolute paths must remain accessible to the users who need them.

### Shared configurations and developer settings

The **Developer** section manages the shared root folder, automatic layer style mappings, File Suffix Rules, and template refresh settings. Authorized developers can also save selected QGIS layer styles as QML files in the configured shared style location.

Shared configuration changes are written to the selected JSON file when saved. Colleagues using that JSON receive the updated configuration when they reload it. Keep shared JSON and resource folders in a location accessible to the team.

Developer codes are a user-interface guard, **not a security boundary**. Use filesystem and server permissions to control who can edit shared configuration and style files. Coordinate concurrent developer edits to avoid overwriting someone else's changes.

## Automatic layer styling

When automatic styling is enabled and a new layer is added, StyleCore looks for a matching QML. This can include:

- A **personal override**, stored locally for the selected configuration.
- An **explicit shared layer-to-QML mapping**.
- A **File Suffix Rule** based on the source filename and extension.
- A **QML named after the QGIS layer**, as a fallback.

If no usable QML is found, the existing layer style is left unchanged. You can disable automatic styling in StyleCore settings.

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

StyleCore synchronizes configured project templates into QGIS' standard template location so they can be used from the QGIS new-project/template workflow.

Developers can select which templates have their existing layers checked for updated QML styles when those templates are opened. The refresh is intended for recognized templates, **not unrelated existing saved projects**.

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
- **A template uses the wrong data:** Confirm that its Oracle, file, WMS, or WFS sources are accessible from that workstation.
- **A font or SVG is missing:** Install or provide the referenced asset separately; it is not automatically delivered by StyleCore.

Issues and feedback: https://github.com/vnaru42/StyleCore/issues
