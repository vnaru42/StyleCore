"""StyleCore translations. English source strings; Danish translations live only here."""
from qgis.PyQt.QtCore import QLocale, QSettings

_DANISH = {
    '\nYou are about to save their current styles to SHARED QML files, not to your personal overrides. Continue?': (
        '\nDu er ved at gemme deres aktuelle styles til FÆLLES QML-filer, ikke til dine '
        'personlige overrides. Fortsæt?'
    ),
    '. Save anyway?': '. Gem alligevel?',
    'Active configuration JSON path (local or UNC)': 'Aktiv konfigurationssti (lokal eller UNC)',
    'Active configuration:': 'Aktiv konfiguration:',
    'Active configuration: ': 'Aktiv konfiguration: ',
    'Add': 'Tilføj',
    'Add a layer name and choose any QML file. The mapping is saved in the active configuration and can be shared with colleagues. Name matching still works automatically.': (
        'Tilføj et lagnavn og vælg en vilkårlig QML-fil. Koblingen gemmes i den aktive '
        'konfiguration og kan deles med kolleger. Navnematching fungerer stadig automatisk.'
    ),
    'Add personal override': 'Tilføj personlig override',
    'Add suffix': 'Tilføj suffiks',
    'Apply': 'Anvend',
    'Automatic layer styles': 'Automatiske layer styles',
    'Automatic styling': 'Automatisk styling',
    'Automatic styling enabled': 'Automatisk styling aktiveret',
    'Browse...': 'Gennemse...',
    'Cancel': 'Annuller',
    'Changes could not be written to the active JSON configuration. You need write permission to this file.': (
        'Ændringerne kunne ikke gemmes i den aktive JSON-konfiguration. Du skal have '
        'skriverettigheder til filen.'
    ),
    'Choose QML': 'Vælg QML',
    'Choose QML style': 'Vælg QML-style',
    'Close': 'Luk',
    'Configuration': 'Konfiguration',
    'Configuration file unavailable: ': 'Konfigurationsfil ikke tilgængelig: ',
    'Confirm developer action': 'Bekræft udviklerhandling',
    'Confirm developer code:': 'Bekræft udviklerkode:',
    'Confirm overwrite of standard style': 'Bekræft overskrivning af standardstyle',
    'Confirm saving layer styles': 'Bekræft gemning af lagstyles',
    'Could not add print layout {name} to the project.': 'Kunne ikke tilføje printlayoutet {name} til projektet.',
    'Could not add the print layout': 'Kunne ikke tilføje printlayoutet',
    'Could not apply QML style:': 'Kunne ikke anvende QML-style:',
    'Could not open the layout template:': 'Kunne ikke åbne layoutskabelonen:',
    'Could not open the print layout template:': 'Kunne ikke åbne printlayoutskabelonen:',
    'Could not read the layout template:': 'Kunne ikke læse layoutskabelonen:',
    'Could not read the print layout template:': 'Kunne ikke læse printlayoutskabelonen:',
    'Could not save StyleCore configuration': 'Kunne ikke gemme StyleCore-konfiguration',
    'Could not save configuration': 'Kunne ikke gemme konfiguration',
    'Could not save personal overrides: ': 'Personlige overrides kunne ikke gemmes: ',
    'Could not save settings: ': 'Kunne ikke gemme indstillinger: ',
    'Could not save shared JSON. Reload settings and check permissions/concurrent edits: ': (
        'Fælles JSON kunne ikke gemmes. Genindlæs indstillingerne og kontrollér '
        'skriverettigheder/ændringer fra andre: '
    ),
    'Could not save shared JSON. Reload settings and check write permissions or concurrent changes: ': (
        'Kunne ikke gemme fælles JSON. Genindlæs indstillingerne og kontrollér skriverettigheder '
        'eller samtidige ændringer: '
    ),
    'Could not save template selection': 'Kunne ikke gemme template-valg',
    'Custom': 'Tilpasset',
    'Deselect all': 'Fravælg alle',
    'Developer': 'Udvikler',
    'Developer access': 'Udvikleradgang',
    'Developer code': 'Udviklerkode',
    'Developer code:': 'Udviklerkode:',
    'Do you want to continue?': 'Vil du fortsætte?',
    'Duplicate file suffix rule: ': 'Dubleret filsuffiksregel: ',
    'Duplicate layer name': 'Samme lagnavn flere gange',
    'Duplicate personal override: ': 'Duplikeret personlig override: ',
    'Duplicate shared style mapping: ': 'Duplikeret fælles stylekobling: ',
    'Duplicate style mapping for layer': 'Duplikeret stylekobling for laget',
    'Duplicate suffix: ': 'Duplikeret suffiks: ',
    'Edit shared configuration (administrator)': 'Redigér fælles konfiguration (administrator)',
    'Edited or created mappings are saved to the configuration.': (
        'Redigerede eller oprettede koblinger gemmes i konfigurationen.'
    ),
    'Enable Developer Mode first.': 'Aktivér udviklertilstand først.',
    'Enable developer mode': 'Aktivér udviklertilstand',
    'Enter a configuration JSON path.': 'Angiv en sti til en konfigurations-JSON.',
    'Enter a developer code and confirm it with the same code.': (
        'Indtast en udviklerkode, og bekræft med samme kode.'
    ),
    'Enter layer name:': 'Indtast lagnavn:',
    'Enter the developer code to continue:': 'Indtast udviklerkoden for at fortsætte:',
    'Errors:': 'Fejl:',
    'Existing standard QML files will be overwritten.': 'Eksisterende standard-QML-filer vil blive overskrevet.',
    'External QML paths may be unavailable to colleagues: ': (
        'Eksterne QML-stier kan være utilgængelige for kolleger: '
    ),
    'External override:': 'Ekstern override:',
    'Help & Documentation': 'Hjælp og dokumentation',
    'Report an Issue': 'Rapportér en fejl',
    'File Suffix Rules': 'Filsuffiksregler',
    'File suffix QML not found: ': 'QML-fil til filsuffiks blev ikke fundet: ',
    'File type': 'Filtype',
    'Enter a file extension such as .kml, kml or * for all file types.': (
        'Angiv en filendelse som .kml, kml eller * for alle filtyper.'
    ),
    'Type a file extension, e.g. .kml, kml or *.': 'Skriv en filendelse, f.eks. .kml, kml eller *.',
    'GeoJSON QML file not found: ': 'GeoJSON-QML-filen blev ikke fundet: ',
    'GeoJSON suffix rules – filename ends with ...': 'GeoJSON-suffiksregler – filnavn slutter med ...',
    'Incorrect code': 'Forkert kode',
    'Incorrect developer code. Try again or press Cancel.': (
        'Forkert udviklerkode. Prøv igen, eller tryk Annuller.'
    ),
    'Incorrect developer code. Try again.': 'Forkert developer code. Prøv igen.',
    'Invalid configuration': 'Ugyldig konfiguration',
    'Invalid resource folder name': 'Ugyldigt navn på ressourcemappe',
    'Layer for personal style:': 'Lag til personlig style:',
    'Layer name': 'Lagnavn',
    'Layouts folder:': 'Layouts-mappe:',
    'Load StyleCore configuration': 'Indlæs StyleCore-konfiguration',
    'Load configuration...': 'Indlæs konfiguration...',
    'Load path': 'Indlæs sti',
    'Manual Style Update': 'Manuel styleopdatering',
    'Manual Style Update...': 'Manuel styleopdatering...',
    'Multiple selected layers have the same name and would overwrite the same QML.': (
        'Flere valgte lag har samme navn og ville overskrive samme QML.'
    ),
    'Multiple selected layers have the same name and would overwrite the same QML. Select only one layer per name:\n': (
        'Flere valgte lag har samme navn og ville overskrive samme QML. Vælg kun ét lag pr. '
        'navn:\n'
    ),
    'My StyleCore configuration': 'Min StyleCore-konfiguration',
    'Name:': 'Navn:',
    'New StyleCore configuration': 'Ny StyleCore-konfiguration',
    'New configuration...': 'Ny konfiguration...',
    'No configuration is loaded. Create a new one or load an existing configuration.': (
        'Ingen konfiguration er indlæst. Opret en ny eller indlæs en eksisterende konfiguration.'
    ),
    'No configuration loaded': 'Ingen konfiguration indlæst',
    'No matching QML suggested. Choose a QML file manually.': 'Ingen QML foreslået. Vælg en QML-fil manuelt.',
    'No print layouts found': 'Ingen print-layouts fundet',
    'No style path is specified for the rule.': 'Ingen style-sti er angivet for reglen.',
    'No style path is specified for this rule.': 'Ingen style-sti er angivet for reglen.',
    'No valid shared configuration is loaded.': 'Ingen gyldig fælles konfiguration er indlæst.',
    'No valid vector layers in the current project.': 'Ingen gyldige vektorlag i dette projekt.',
    'None': 'Ingen',
    'Paste a local path or UNC path to an existing configuration JSON': (
        'Indsæt en lokal sti eller UNC-sti til en eksisterende konfigurations-JSON'
    ),
    'Personal Overrides': 'Personlige overrides',
    'Personal QML file does not exist: ': 'Personlig QML-fil findes ikke: ',
    'Personal QML path': 'Personlig QML-sti',
    'Personal rules saved. These loaded layers could not be updated automatically (no matching default QML or loading failed): ': (
        'Personlige regler er gemt. Disse indlæste lag kunne ikke opdateres automatisk (ingen '
        'gyldig standard-QML eller fejl ved indlæsning): '
    ),
    'Personal rules saved. These loaded layers could not be updated automatically (no valid default QML or loading failed): ': (
        'Personlige regler gemt. Disse indlæste lag kunne ikke opdateres automatisk (ingen '
        'gyldig standard-QML eller indlæsningsfejl): '
    ),
    'Personal selections are never written to JSON. Reset selected removes only your override; the shared default applies at the next automatic styling event.': (
        'Personlige valg gemmes aldrig i JSON. Nulstil valgt fjerner kun din egen override og '
        'vender tilbage til fælles standard ved næste automatiske styling.'
    ),
    'Personal style': 'Personlig style',
    'Personal style overrides': 'Personlige overrides',
    'Personal style overrides (this QGIS profile only)': 'Personlige style-overrides (kun denne QGIS-profil)',
    'Print Layouts folder:': 'Printlayouts-mappe:',
    'Print layout {name} was added but could not be found again.': (
        'Printlayoutet {name} blev tilføjet, men kunne ikke findes igen.'
    ),
    'Print layouts folder:': 'Printlayouts-mappe:',
    'Provide a suffix, file type and QML style.': 'Angiv suffiks, filtype og QML-style.',
    'Provide both a suffix and a QML file for GeoJSON rules.': 'Angiv både suffiks og QML-fil for GeoJSON-regler.',
    'Provide both layer name and QML file for each personal override.': (
        'Angiv både lagnavn og QML-fil for hver personlig override.'
    ),
    'QML file': 'QML-fil',
    'QML file:': 'QML-fil:',
    'QML style file not found for': 'QML-filen blev ikke fundet for',
    'Remove': 'Fjern',
    'Remove all personal overrides for this configuration? Shared styles will not change.': (
        'Fjern alle personlige overrides for denne konfiguration? Fælles styles ændres ikke.'
    ),
    'Remove suffix': 'Fjern suffiks',
    'Reset all personal styles': 'Nulstil alle personlige styles',
    'Reset selected': 'Nulstil valgt',
    'Reset to shared default': 'Nulstil til fælles standard',
    'Root folder': 'Rodmappe',
    'Root folder for StyleCore resources. The location normally comes from the active configuration.': (
        'Rodmappe til StyleCore-ressourcer. Placeringen kommer normalt fra den aktive '
        'konfiguration.'
    ),
    'Root folder missing': 'Rodmappe mangler',
    'Root folder:': 'Rodmappe:',
    'Same QML destination as': 'Samme QML-destination som',
    'Save StyleCore configuration': 'Gem StyleCore-konfiguration',
    'Save anyway?': 'Gem alligevel?',
    'Save configuration': 'Gem konfiguration',
    'Save layer styles': 'Gem lagstyles',
    'Save layer styles...': 'Gem lagstyles...',
    'Save selected': 'Gem valgte',
    'Saved styles:': 'Gemte styles:',
    'Saves the current styles from project layers back to the corresponding QML files in the shared layer_styles folder.': (
        'Gemmer de aktuelle styles fra projektets lag tilbage til de tilsvarende QML-filer i den '
        'fælles layer_styles-mappe.'
    ),
    'Saves the current styles from project layers to the corresponding QML files in the shared layer_styles folder.': (
        'Gemmer de aktuelle styles fra projektets lag tilbage til de tilsvarende QML-filer i den '
        'fælles layer_styles-mappe.'
    ),
    'Select QGIS style': 'Vælg QGIS style',
    'Select StyleCore root folder': 'Vælg StyleCore-rodmappe',
    'Select a layer, review the suggested QML or browse for another file, then click Use Style. Other projects and automatic rules are not changed.': (
        'Vælg et lag, kontrollér den foreslåede QML eller vælg en anden fil, og tryk Brug style. '
        'Andre projekter og automatiske regler ændres ikke.'
    ),
    'Select a root folder for the StyleCore resources.': 'Vælg en rodmappe til StyleCore-ressourcerne.',
    'Select all': 'Vælg alle',
    'Select layer': 'Vælg lag',
    'Select only one layer per name:': 'Vælg kun ét lag pr. navn:',
    'Select only one of them.': 'Vælg kun ét af dem.',
    'Select shared StyleCore folder': 'Vælg fælles StyleCore-mappe',
    'Select the layers whose current QGIS style should be saved in the shared layer_styles folder. No layers are selected by default.': (
        'Vælg de lag, hvis nuværende QGIS-style skal gemmes i den fælles layer_styles-mappe. '
        'Ingen lag er valgt på forhånd.'
    ),
    'Select the layers whose current QGIS style should be saved to the shared layer_styles folder. No layers are selected by default.': (
        'Vælg de lag, hvis aktuelle QGIS-style skal gemmes i den fælles layer_styles-mappe. '
        'Ingen lag er valgt på forhånd.'
    ),
    'Select which project templates should have existing layers checked and restyled when the template is opened.': (
        'Vælg hvilke projektskabeloner der skal have eksisterende lag kontrolleret og restylet, '
        'når skabelonen åbnes.'
    ),
    'Settings...': 'Indstillinger...',
    'Shared JSON path (e.g. \\server\\GIS\\StyleCore\\config.json)': (
        'Delt JSON-sti (f.eks. \\server\\GIS\\StyleCore\\config.json)'
    ),
    'Shared QML file not found for ': 'Fælles QML-fil findes ikke for ',
    'Shared automatic layer styles': 'Fælles automatiske lagstyles',
    'Shared automatic layer styles (JSON)': 'Fælles automatiske lagstyles (JSON)',
    'Shared default': 'Fælles standard',
    "Shared mappings affect all colleagues. Select 'Edit shared configuration' to modify them. Personal overrides are managed below.": (
        "Fælles koblinger deles med alle. Aktivér 'Redigér fælles konfiguration' for at ændre "
        'disse. Personlige overrides oprettes nedenfor.'
    ),
    'Shared mappings are saved to the configuration after developer code confirmation.': (
        'Fælles koblinger gemmes i konfigurationen efter bekræftelse med developer-kode.'
    ),
    'Show code': 'Vis kode',
    'Skipped after confirmation:': 'Fravalgt ved bekræftelse:',
    'Standard': 'Standard',
    'Standard file:': 'Standardfil:',
    'Status': 'Status',
    'Style applied to this layer. Save the QGIS project to keep it.': (
        'Style anvendt på dette lag. Gem QGIS-projektet for at beholde ændringen.'
    ),
    'Style path': 'Style-sti',
    'StyleCore - automatic styling disabled': 'StyleCore - automatisk styling deaktiveret',
    'StyleCore resources': 'StyleCore ressourcer',
    'StyleCore – save complete': 'StyleCore – gemning færdig',
    'Styles folder:': 'Styles-mappe:',
    'Suffix': 'Suffiks',
    'Template refresh': 'Template-opdatering',
    'Templates folder:': 'Templates-mappe:',
    'The configuration path is unavailable or the JSON is invalid:': (
        'Konfigurationsstien er utilgængelig, eller JSON-filen er ugyldig:'
    ),
    'The developer code is incorrect. No styles were saved.': 'Udviklerkoden er forkert. Ingen styles blev gemt.',
    'The external override file will not be changed.': 'Den eksterne override-fil bliver ikke ændret.',
    'The file could not be read as a valid StyleCore configuration.': (
        'Filen kunne ikke læses som en gyldig StyleCore-konfiguration.'
    ),
    'The folder does not exist:': 'Mappen findes ikke:',
    'The layer name cannot be used as a file name.': 'Lagnavnet kan ikke bruges som filnavn.',
    'The layer name cannot be used as a filename and has no explicit QML mapping.': (
        'Lagnavnet kan ikke bruges som filnavn og mangler en eksplicit QML-kobling.'
    ),
    'The layout template was not found:': 'Layoutskabelonen blev ikke fundet:',
    'The print layout template was not found:': 'Printlayoutskabelonen blev ikke fundet:',
    'The project has no valid layers.': 'Projektet har ingen gyldige lag.',
    'The shared configuration was changed by another user. Reload settings.': (
        'Den fælles konfiguration er ændret af en anden bruger. Genindlæs indstillingerne.'
    ),
    'The style folder was not found:': 'Style-mappen blev ikke fundet:',
    'The template selection could not be saved to the active configuration:': (
        'Valget af templates kunne ikke gemmes i den aktive konfiguration:'
    ),
    'These QML files are outside the shared styles folder and may not work for colleagues:': (
        'Disse QML-filer ligger uden for den fælles styles-mappe og kan muligvis ikke bruges af '
        'kolleger:'
    ),
    'These layers have personal overrides: ': 'Disse lag har personlige overrides: ',
    'This layer uses an external style override.': 'Dette lag bruger en ekstern style-override.',
    'Use Style': 'Brug style',
    'User rule': 'Brugerregel',
    "You are about to overwrite the standard QML file with the layer's current style.": (
        'Du er ved at overskrive standard-QML-filen med lagets aktuelle style.'
    ),
    'You are about to save': 'Du er ved at gemme',
    'You are about to save {count} selected layer style(s) to the shared layer_styles folder.\n\nExisting standard QML files will be overwritten.\n\nDo you want to continue?': (
        'Du er ved at gemme {count} valgte lagstyles til den fælles '
        'layer_styles-mappe.\n\nEksisterende standard-QML-filer bliver overskrevet.\n\nVil du '
        'fortsætte?'
    ),
    'You are saving their current styles into SHARED QML files, not your personal overrides. Continue?': (
        'Du er ved at gemme deres aktuelle styles til FÆLLES QML-filer, ikke til dine personlige '
        'overrides. Fortsæt?'
    ),
    'selected layer style(s)': 'valgte lagstyle(s)',
    'to the shared layer_styles folder.': 'til den fælles layer_styles-mappe.',
    'was added, but could not be found again.': 'blev tilføjet, men kunne ikke findes igen.',
}
def qgis_language():
    """Use the configured QGIS UI locale, falling back to the system locale."""
    settings = QSettings()
    override = settings.value("locale/overrideFlag", False, type=bool)
    locale = settings.value("locale/userLocale", "", type=str).strip() if override else ""
    if not locale:
        locale = QLocale.system().name()
    return locale.replace("-", "_").lower()


def is_danish():
    return qgis_language().startswith("da")


def tr(text):
    """Translate an English UI string to Danish when the QGIS locale is Danish."""
    if not is_danish():
        return text
    return _DANISH.get(text, text)
