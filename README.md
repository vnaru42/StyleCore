# DMIKG Auto

QGIS-plugin til fælles styles, projektskabeloner og printlayouts.

## Fælles struktur

```text
QGIS_komplet_stytem/
├── layer_styles/
├── template_projects/
└── layouts/
```

ROOT-mappen vælges under **Indstillinger**. Undermapperne skal beholde navnene ovenfor.

## Funktioner

- Automatisk styling af lag fra `layer_styles`
- GeoJSON-regler med styles fra `layer_styles`
- Lokale style-overrides via Indstillinger
- Synkronisering af projektskabeloner fra `template_projects`
- Dynamisk printmenu med `.qpt`-filer fra `layouts`
- Udviklertilstand til at gemme valgte lagstyles

## Printlayouts

QPT-filer lægges i `ROOT\layouts`. De vises automatisk under **PRINT** i pluginmenuen.

Følgende Item ID'er bruges i layouts:

- `main_map` – sættes til det aktuelle canvas-udsnit
- `mini_map` – sættes til samme startudsnit og kan derefter justeres i Layout Designer

### SVG-filer

SVG-filer lægges også i `ROOT\layouts`. Filnavnet uden `.svg` skal være det samme som Picture-elementets Item ID i QPT-filen.

Eksempel:

```text
kds_logo.svg  ->  Item ID: kds_logo
nordpil.svg   ->  Item ID: nordpil
```

Pluginet sætter SVG-stien, når layoutet oprettes.

## Installation

1
Kopiér mappen `dmikg_auto` til QGIS plugin-mappen:

`QGIS(3/4)/profiles/default/python/plugins/`

Genstart QGIS eller reload pluginet.

2
Installér via QGIS ZIP-installation

## Version

1.0.0
