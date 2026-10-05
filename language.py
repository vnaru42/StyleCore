from qgis.PyQt.QtCore import QLocale, QSettings

# English is the fallback language. Danish is used only when QGIS itself uses Danish.
_DA_TO_EN = {
    "Ingen": "None",
    "Indstillinger...": "Settings...",
    "Automatisk styling": "Automatic styling",
    "StyleCore - automatisk styling deaktiveret": "StyleCore - automatic styling disabled",
    "Ingen print-layouts fundet": "No print layouts found",
    "Konfiguration": "Configuration",
    "Indlæs konfiguration...": "Load configuration...",
    "Ny konfiguration...": "New configuration...",
    "StyleCore ressourcer": "StyleCore resources",
    "Template-opdatering": "Template refresh",
    "Vælg hvilke projektskabeloner der skal have eksisterende lag kontrolleret og restylet, når skabelonen åbnes.": "Select which project templates should have existing layers checked and restyled when the template is opened.",
    "Kunne ikke gemme template-valg": "Could not save template selection",
    "Valget af templates kunne ikke gemmes i den aktive konfiguration:": "The template selection could not be saved to the active configuration:",
    "Rodmappe til StyleCore-ressourcer. Placeringen kommer normalt fra den aktive konfiguration.": "Root folder for StyleCore resources. The location normally comes from the active configuration.",
    "Automatiske layer styles": "Automatic layer styles",
    "Automatisk styling aktiveret": "Automatic styling enabled",
    "Lagnavn": "Layer name",
    "Style-sti": "Style path",
    "Status": "Status",
    "Tilføj": "Add",
    "Fjern": "Remove",
    "Nulstil valgt": "Reset selected",
    "Udvikler": "Developer",
    "Aktivér udviklertilstand": "Enable developer mode",
    "Gemmer de aktuelle styles fra projektets lag tilbage til de tilsvarende QML-filer i den fælles layer_styles-mappe.": "Saves the current styles from project layers back to the corresponding QML files in the shared layer_styles folder.",
    "Gem lagstyles...": "Save layer styles...",
    "Ingen konfiguration er indlæst. Opret en ny eller indlæs en eksisterende konfiguration.": "No configuration is loaded. Create a new one or load an existing configuration.",
    "Indlæs StyleCore-konfiguration": "Load StyleCore configuration",
    "Ugyldig konfiguration": "Invalid configuration",
    "Filen kunne ikke læses som en gyldig StyleCore-konfiguration.": "The file could not be read as a valid StyleCore configuration.",
    "Ny StyleCore-konfiguration": "New StyleCore configuration",
    "Min StyleCore-konfiguration": "My StyleCore configuration",
    "Vælg StyleCore-rodmappe": "Select StyleCore root folder",
    "Navn:": "Name:",
    "Rodmappe:": "Root folder:",
    "Styles-mappe:": "Styles folder:",
    "Templates-mappe:": "Templates folder:",
    "Layouts-mappe:": "Layouts folder:",
    "Gem konfiguration": "Save configuration",
    "Rodmappe mangler": "Root folder missing",
    "Vælg en rodmappe til StyleCore-ressourcerne.": "Select a root folder for the StyleCore resources.",
    "Gem StyleCore-konfiguration": "Save StyleCore configuration",
    "Kunne ikke gemme konfiguration": "Could not save configuration",
    "Vælg fælles StyleCore-mappe": "Select shared StyleCore folder",
    "Standard": "Standard",
    "Tilpasset": "Custom",
    "Brugerregel": "User rule",
    "Vælg QGIS style": "Select QGIS style",
    "Projektet har ingen gyldige lag.": "The project has no valid layers.",
    "Gem lagstyles": "Save layer styles",
    "Vælg de lag, hvis aktuelle QGIS-style skal gemmes i den fælles layer_styles-mappe. Ingen lag er valgt på forhånd.": "Select the layers whose current QGIS style should be saved to the shared layer_styles folder. No layers are selected by default.",
    "Vælg alle": "Select all",
    "Fravælg alle": "Deselect all",
    "Gem valgte": "Save selected",
    "Samme lagnavn flere gange": "Duplicate layer name",
    "Bekræft udviklerhandling": "Confirm developer action",
    "Indtast udviklerkoden for at fortsætte:": "Enter the developer code to continue:",
    "Forkert kode": "Incorrect code",
    "Udviklerkoden er forkert. Ingen styles blev gemt.": "The developer code is incorrect. No styles were saved.",
    "Bekræft gemning af lagstyles": "Confirm saving layer styles",
    "Bekræft overskrivning af standardstyle": "Confirm overwrite of standard style",
    "StyleCore – gemning færdig": "StyleCore – save complete",
    "Style-mappen blev ikke fundet:": "The style folder was not found:",
    "Aktiv konfiguration:": "Active configuration:",
    "Gemte styles:": "Saved styles:",
    "Fravalgt ved bekræftelse:": "Skipped after confirmation:",
    "Fejl:": "Errors:",
    "Vælg kun ét lag pr. navn:": "Select only one layer per name:",
    "Flere valgte lag har samme navn og ville overskrive samme QML.": "Multiple selected layers have the same name and would overwrite the same QML.",
    "Du er ved at gemme": "You are about to save",
    "valgte lagstyle(s)": "selected layer style(s)",
    "til den fælles layer_styles-mappe.": "to the shared layer_styles folder.",
    "Eksisterende standard-QML-filer vil blive overskrevet.": "Existing standard QML files will be overwritten.",
    "Vil du fortsætte?": "Do you want to continue?",
    "Dette lag bruger en ekstern style-override.": "This layer uses an external style override.",
    "Du er ved at overskrive standard-QML-filen med lagets aktuelle style.": "You are about to overwrite the standard QML file with the layer's current style.",
    "Standardfil:": "Standard file:",
    "Ekstern override:": "External override:",
    "Den eksterne override-fil bliver ikke ændret.": "The external override file will not be changed.",
    "Mappen findes ikke:": "The folder does not exist:",
    "Lagnavnet kan ikke bruges som filnavn.": "The layer name cannot be used as a file name.",
    "Ingen style-sti er angivet for reglen.": "No style path is specified for the rule.",
    "Samme QML-destination som": "Same QML destination as",
    "Vælg kun ét af dem.": "Select only one of them.",
    "Layoutskabelonen blev ikke fundet:": "The layout template was not found:",
    "Kunne ikke åbne layoutskabelonen:": "Could not open the layout template:",
    "Kunne ikke læse layoutskabelonen:": "Could not read the layout template:",
    "blev tilføjet, men kunne ikke findes igen.": "was added, but could not be found again.",
    "Kunne ikke tilføje printlayoutet": "Could not add the print layout",
}

def qgis_language():
    value = QSettings().value("locale/userLocale", "", type=str).strip()
    if not value:
        value = QLocale.system().name()
    return value.replace("-", "_").lower()

def is_danish():
    return qgis_language().startswith("da")

def tr(text):
    if is_danish():
        return text
    if text in _DA_TO_EN:
        return _DA_TO_EN[text]
    translated = text
    # Replace longer phrases first so dynamic messages and f-strings are also translated.
    for da, en in sorted(_DA_TO_EN.items(), key=lambda item: len(item[0]), reverse=True):
        translated = translated.replace(da, en)
    return translated
