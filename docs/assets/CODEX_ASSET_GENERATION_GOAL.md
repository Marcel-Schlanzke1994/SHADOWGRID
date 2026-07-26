# CODEX MASTER GOAL

## SHADOWGRID – vollständige sequenzielle Grafikproduktion

Du übernimmst die vollständige visuelle Produktion für SHADOWGRID.

Deine Aufgabe ist es, **jedes benötigte Grafik-Asset einzeln, in einer festen Reihenfolge, reproduzierbar und qualitätsgeprüft zu erstellen**.

Du darfst die Aufgabe nicht mit Platzhaltern, einfachen Farbflächen oder nicht geprüften Bildern abschließen.

Das Ergebnis muss für folgende Plattformen geeignet sein:

* Desktop-Web
* Mobile-Web
* Android
* iOS
* App Store
* Google Play
* Social Media
* Community- und Marketingmaterial

---

# 1. Hauptziel

Erstelle die komplette visuelle Asset-Bibliothek von SHADOWGRID.

Das Design muss durchgehend wirken wie:

> Eine ultra-realistische, moderne deutsche Wirtschafts-, Macht- und Multiplayer-Strategiesimulation im Stil eines hochwertigen urbanen Thrillers und strategischen Kontrollzentrums.

Die Bilder müssen:

* fotorealistisch oder hochwertig prozedural sein,
* visuell zusammengehören,
* moderne deutsche Städte glaubwürdig darstellen,
* für UI-Overlays genügend freie Bildbereiche besitzen,
* Desktop und Mobile unterstützen,
* keine fremden Marken oder Bildrechte verletzen,
* keine realen kriminellen Organisationen darstellen,
* keine konkreten Anleitungen für reale Kriminalität enthalten.

---

# 2. Ausführungsmodus

Arbeite vollständig selbstständig.

Erzeuge nicht alle Bilder unkontrolliert gleichzeitig.

Verarbeite immer nur ein Asset oder einen kleinen technisch zusammengehörenden Variantensatz.

Der Ablauf pro Asset lautet:

```text
1. Manifest-Eintrag laden
2. Prompt erzeugen
3. Asset generieren
4. Datei validieren
5. visuelle Qualität prüfen
6. Sicherheitsprüfung durchführen
7. Metadaten schreiben
8. responsive Formate erstellen
9. Asset im Spiel testen
10. Status speichern
11. erst danach mit dem nächsten Asset fortfahren
```

Wenn ein Asset die Prüfung nicht besteht:

```text
1. Fehler dokumentieren
2. Prompt gezielt korrigieren
3. Asset erneut generieren
4. maximal drei automatische Versuche
5. danach sicheren Premium-Fallback erstellen
6. Asset als review_required markieren
7. Verarbeitung fortsetzen
```

Stoppe nicht die gesamte Pipeline wegen eines einzelnen fehlerhaften Assets.

---

# 3. Fortschritt und Wiederaufnahme

Erstelle:

```text
.project/
├── asset-generation-state.json
├── asset-generation-errors.json
├── asset-generation-costs.json
├── asset-generation-summary.md
└── visual-style-lock.json
```

Beispiel für `asset-generation-state.json`:

```json
{
  "project": "shadowgrid",
  "manifest_version": "1.0.0",
  "total_assets": 0,
  "completed_assets": 0,
  "approved_assets": 0,
  "review_required_assets": 0,
  "failed_assets": 0,
  "current_batch": null,
  "current_asset_id": null,
  "last_completed_asset_id": null,
  "updated_at": null
}
```

Nach jedem fertigen Asset muss der Zustand atomar gespeichert werden.

Wenn die Ausführung unterbrochen wird:

* beginne nicht erneut von vorn,
* prüfe bereits vorhandene Assets,
* setze beim ersten nicht freigegebenen Manifest-Eintrag fort.

Ein vorhandenes Asset darf nur neu erstellt werden, wenn:

* es fehlt,
* beschädigt ist,
* nicht dem Manifest entspricht,
* die Qualitätsprüfung fehlschlägt,
* sich die Prompt- oder Style-Version verändert hat.

---

# 4. Provider

Unterstütze folgende Konfiguration:

```env
IMAGE_GENERATION_PROVIDER=disabled
IMAGE_GENERATION_PROVIDER=openai
IMAGE_GENERATION_PROVIDER=local_comfyui
IMAGE_GENERATION_PROVIDER=custom_http
```

Erstelle eine gemeinsame Provider-Schnittstelle:

```text
generate_image(prompt, negative_prompt, width, height, seed, metadata)
```

Kein Provider darf direkt in der Spiellogik fest verdrahtet werden.

Zugangsdaten dürfen nicht:

* im Repository,
* im Frontend,
* in Logs,
* in Manifestdateien,
* in Metadatendateien

gespeichert werden.

Wenn kein Bildprovider aktiv ist:

* erzeuge hochwertige prozedurale Premium-Fallbacks,
* markiere sie nicht als fotorealistisch generiert,
* lasse die Anwendung vollständig funktionieren.

---

# 5. Verzeichnisstruktur

Erstelle:

```text
assets/
├── source/
│   ├── branding/
│   ├── global/
│   ├── cities/
│   ├── districts/
│   ├── businesses/
│   ├── facilities/
│   ├── characters/
│   ├── pvp/
│   ├── cartels/
│   ├── events/
│   ├── tutorial/
│   ├── maps/
│   ├── icons/
│   ├── effects/
│   ├── rewards/
│   └── marketing/
├── production/
│   ├── avif/
│   ├── webp/
│   ├── png/
│   └── svg/
├── metadata/
├── prompts/
├── previews/
├── rejected/
└── reports/
```

Masterdateien gehören nach:

```text
assets/source/
```

Optimierte Produktionsdateien gehören nach:

```text
assets/production/
```

---

# 6. Asset-Manifest

Erstelle vor der ersten Generierung:

```text
assets/asset-manifest.json
```

Jeder Eintrag benötigt:

```json
{
  "order": 1,
  "asset_id": "branding-shadowgrid-logo-horizontal-dark-v1",
  "batch": "branding",
  "category": "logo",
  "title": "SHADOWGRID horizontal logo on dark background",
  "source_type": "generated",
  "required": true,
  "priority": 1,
  "width": 3200,
  "height": 1000,
  "aspect_ratio": "16:5",
  "transparent_background": false,
  "prompt_template": "branding-logo",
  "prompt_version": "1.0.0",
  "style_version": "1.0.0",
  "seed": 100001,
  "variants": [],
  "status": "pending"
}
```

Manifestregeln:

* `order` ist eindeutig.
* `asset_id` ist eindeutig.
* Seeds sind fest und reproduzierbar.
* Kein Asset wird außerhalb des Manifests erzeugt.
* Neue Assets werden nur über eine Manifestversion ergänzt.
* Entfernte Assets werden archiviert und nicht still gelöscht.

---

# 7. Globaler visueller Style Lock

Erstelle vor dem ersten Bild:

```text
.project/visual-style-lock.json
```

Inhalt:

```json
{
  "project": "SHADOWGRID",
  "visual_identity": [
    "ultra-realistic contemporary German urban environments",
    "premium economic strategy interface",
    "cinematic urban thriller atmosphere",
    "subtle cyber-noir",
    "dark glass and brushed metal",
    "restrained gold accents",
    "warning red only for danger",
    "physically plausible materials",
    "natural cinematic lighting",
    "high readability under UI overlays"
  ],
  "forbidden_styles": [
    "cartoon",
    "anime",
    "comic",
    "mobile game plastic look",
    "fantasy city",
    "excessive neon",
    "steampunk",
    "retro 1930s mafia",
    "copied movie aesthetic",
    "copied game aesthetic"
  ],
  "color_intent": {
    "base": "black and anthracite",
    "primary_accent": "restrained warm gold",
    "danger": "dark warning red",
    "information": "cool neutral blue-gray",
    "success": "muted green"
  },
  "lighting": [
    "natural daylight",
    "warm dusk",
    "realistic urban night",
    "subtle volumetric atmosphere"
  ],
  "camera": [
    "cinematic establishing shots",
    "architectural photography",
    "controlled depth",
    "no extreme fisheye",
    "no impossible drone angles"
  ]
}
```

Alle Asset-Prompts müssen auf diesen Style Lock verweisen.

---

# 8. Globaler positiver Prompt

Verwende als Grundlage für alle fotorealistischen Bilder:

```text
Create a premium ultra-realistic visual asset for the multiplayer strategy game SHADOWGRID.

Visual identity:
contemporary Germany,
high-end urban economic strategy simulation,
cinematic political and corporate thriller atmosphere,
subtle cyber-noir design language,
realistic architecture,
physically plausible glass, concrete, steel, stone and asphalt materials,
natural cinematic lighting,
restrained warm gold accents,
dark anthracite visual framing,
high dynamic range,
realistic reflections,
realistic scale,
clean professional composition,
space reserved for user-interface overlays,
no embedded captions or interface text.

The image must be original and must not copy a known photograph, film frame, game screenshot or branded design.

Asset-specific description:
{ASSET_DESCRIPTION}

Location characteristics:
{LOCATION_CHARACTERISTICS}

Time of day:
{TIME_OF_DAY}

Weather:
{WEATHER}

Gameplay state:
{GAMEPLAY_STATE}

Camera and composition:
{CAMERA_DESCRIPTION}

Output requirements:
{OUTPUT_REQUIREMENTS}
```

---

# 9. Globaler negativer Prompt

Ergänze bei allen Rasterbildern:

```text
Do not include:
written words,
captions,
watermarks,
signatures,
existing game logos,
real company logos,
real police insignia,
real government insignia,
readable private license plates,
readable private addresses,
recognizable private individuals,
celebrities,
politicians,
real criminal organizations,
real gang symbols,
extremist symbols,
Nazi symbols,
graphic violence,
visible illegal instructions,
firearms as the central subject,
drug production,
crime tutorials,
copied photography,
copied landmarks from an identical photo angle,
fantasy skyscrapers,
impossible architecture,
distorted buildings,
duplicate people,
deformed hands,
unrealistic vehicles,
floating objects,
overexposed neon,
cartoon style,
anime style,
comic style,
plastic mobile-game appearance,
blurry image,
low resolution,
compression artifacts,
unreadable fake text.
```

---

# 10. Reihenfolge der Produktion

Die Reihenfolge ist verbindlich.

---

## BATCH 01 – Style-Proof

Erzeuge zuerst fünf Stilreferenzen:

1. SHADOWGRID urbanes Kontrollzentrum, Tag
2. SHADOWGRID urbanes Kontrollzentrum, Nacht
3. deutsche Metropole, Tag
4. deutsche Metropole, Nacht
5. ultra-realistische Unternehmenszentrale

Diese fünf Bilder dienen ausschließlich zur Stilvalidierung.

Prüfe:

* Materialqualität
* Licht
* Kontrast
* Cyber-Noir-Anteil
* Goldakzente
* deutsche Architektur
* UI-Freiraum
* mobile Nutzbarkeit

Erzeuge aus dem besten Ergebnis:

```text
assets/reports/style-reference-contact-sheet.png
```

Danach friere den Style Lock ein.

**Gate:** Kein weiteres Asset wird generiert, bevor der Style-Proof freigegeben oder intern als konsistent validiert wurde.

---

## BATCH 02 – Branding

Erzeuge in dieser Reihenfolge:

1. Hauptlogo horizontal, dunkler Hintergrund
2. Hauptlogo horizontal, heller Hintergrund
3. Hauptlogo vertikal, dunkler Hintergrund
4. Hauptlogo vertikal, heller Hintergrund
5. Symbol Gold, transparent
6. Symbol Weiß, transparent
7. Symbol Schwarz, transparent
8. Symbol monochrom vereinfacht
9. Wortmarke horizontal
10. Wortmarke kompakt
11. App-Icon-Master
12. Android Adaptive Icon Vordergrund
13. Android Adaptive Icon Hintergrund
14. Favicon-Symbol

Für Logos:

* keine fotorealistischen Bilder verwenden,
* bevorzugt SVG erzeugen,
* klare geometrische Formen,
* technisch, hochwertig und zeitlos,
* auch in 16 × 16 Pixel erkennbar,
* kein Totenkopf,
* keine Schusswaffen,
* keine offensichtlichen Mafia-Klischees.

---

## BATCH 03 – Globale Hintergründe

Erzeuge:

1. Landingpage Desktop, Tag, 21:9
2. Landingpage Desktop, Nacht, 21:9
3. Landingpage Mobile, Tag, 9:16
4. Landingpage Mobile, Nacht, 9:16
5. Login Desktop
6. Login Mobile
7. Registrierung Desktop
8. Registrierung Mobile
9. Spielweltenauswahl Desktop
10. Spielweltenauswahl Mobile
11. globales Kommandozentrum Tag
12. globales Kommandozentrum Nacht
13. Deutschlandkarte atmosphärischer Hintergrund
14. Saisonabschluss
15. Wartungsmodus
16. Offline-Modus

Für Auth-Bilder:

* ruhige Komposition,
* keine ablenkenden Gesichter,
* dunkler Bereich für Formular,
* klare Safe Area.

---

## BATCH 04 – Deutschlandkarte

Erzeuge beziehungsweise verarbeite:

1. Deutschlandumriss als SVG
2. Bundeslandgrenzen als SVG
3. Küsten- und Gewässerebene
4. vereinfachte größere Flüsse
5. Kartenhintergrund Tag
6. Kartenhintergrund Nacht
7. neutrale Kartenebene
8. Wirtschafts-Heatmap-Legende
9. Informations-Heatmap-Legende
10. Behördenaktivitäts-Legende
11. Organisationspräsenz-Legende
12. Ereignis-Legende

Geografische Formen dürfen nicht durch Bild-KI erfunden werden.

Nutze ausschließlich lizenzierte geografische Daten.

---

## BATCH 05 – Kartenmarker und Kontrollpunkte

Erzeuge als SVG:

### Stadtmarker

1. Metropole
2. Großstadt
3. Mittelstadt
4. Kleinstadt
5. Heimatstadt
6. Kartellhauptsitz
7. umkämpfte Stadt
8. saisonales Ereignis

### Einflussmarker

9. Wirtschaft
10. Straße
11. Information
12. Gesellschaft
13. Digital

### Kontrollpunkte

14. Wirtschaftsnetzwerk
15. Informationszentrum
16. Logistikknoten
17. gesellschaftlicher Zugang
18. digitaler Knoten
19. Koordinationszentrum

---

## BATCH 06 – Premium-Stadtpakete

Verarbeite die Städte exakt in dieser Reihenfolge:

1. Köln
2. Hamburg
3. Berlin
4. München
5. Frankfurt am Main
6. Düsseldorf
7. Stuttgart
8. Leipzig
9. Dortmund
10. Essen
11. Bremen
12. Dresden
13. Hannover
14. Nürnberg
15. Duisburg
16. Bochum
17. Wuppertal
18. Bielefeld
19. Bonn
20. Münster
21. Aachen
22. Mannheim
23. Karlsruhe
24. Augsburg
25. Wiesbaden
26. Mönchengladbach
27. Gelsenkirchen
28. Braunschweig
29. Kiel
30. Chemnitz

### Pro Stadt werden erzeugt

1. Ultra-Wide-Hero Tag, 21:9
2. Ultra-Wide-Hero Nacht, 21:9
3. Desktop-Hero Tag, 16:9
4. Desktop-Hero Nacht, 16:9
5. Mobile-Hero Tag, 9:16
6. Mobile-Hero Nacht, 9:16
7. quadratische Stadtkarte, 1:1
8. stilisierte Stadt-Silhouette als SVG

### Stadt-Hero-Prompt

```text
Create an ultra-realistic cinematic establishing view representing
{CITY_NAME}, {FEDERAL_STATE}, Germany.

The scene must feel geographically, architecturally and economically plausible for the city, but must not recreate one existing photograph.

City characteristics:
{CITY_PROFILE}

Recognizable general traits:
{GENERAL_CITY_TRAITS}

Time:
{TIME_OF_DAY}

Weather:
{WEATHER}

Visual direction:
premium contemporary German urban environment,
realistic city scale,
architecturally plausible buildings,
subtle local geographic characteristics,
cinematic but natural lighting,
restrained cyber-noir strategic atmosphere,
high dynamic range,
realistic depth,
physically plausible reflections,
reserved negative space for UI overlays.

The result must represent the identity of the city without relying on an exact copied landmark photograph.
```

### Köln-Profil

```text
Major Rhine metropolis in North Rhine-Westphalia,
large river crossing the city,
multiple bridge structures,
dense mixed modern and historic urban development,
major media, trade, cultural and logistics presence,
warm Rhineland urban atmosphere,
plausible church-dominated historic silhouette in the distance,
modern office, residential and transport architecture,
no exact recreation of a known Cologne Cathedral photograph.
```

### Hamburg-Profil

```text
Large northern German port metropolis,
broad waterways,
harbor and logistics structures,
brick warehouse architecture,
modern waterfront offices,
maritime weather,
large urban scale,
no real shipping company logos,
no security-sensitive port layout.
```

### Berlin-Profil

```text
Large diverse German capital,
broad streets,
mixed historic, postwar and modern architecture,
administrative and technology presence,
dense urban neighborhoods,
large metropolitan scale,
no exact recreation of a famous tourism photograph,
no government logos.
```

### München-Profil

```text
Prosperous southern German metropolis,
high-quality public spaces,
historic southern German architectural influences,
modern corporate and technology districts,
clean streets,
high property-value atmosphere,
distant Alpine environmental influence only when compositionally plausible.
```

Für alle weiteren Städte:

* erzeuge das Stadtprofil datengetrieben,
* dokumentiere das verwendete Profil,
* verwende keine kriminalitätsbezogenen realen Daten.

---

## BATCH 07 – Prozedurale Stadtvorlagen

Erzeuge zwölf Mastervorlagen:

1. Metropole mit Fluss
2. Metropole im Binnenland
3. Metropole mit Hafen
4. Großstadt mit Industrieprofil
5. Großstadt mit Technologieprofil
6. Großstadt mit Verwaltungsprofil
7. Mittelstadt mit historischer Innenstadt
8. Mittelstadt mit Industrie und Gewerbe
9. Mittelstadt mit Universität
10. Kleinstadt in ländlicher Umgebung
11. Kleinstadt an Fluss oder See
12. Kleinstadt mit Gewerbe- und Pendlerprofil

Jede Vorlage benötigt:

* Tag
* Nacht
* Desktop
* Mobile
* Quadrat

Die Varianten dürfen aus demselben konsistenten Master erzeugt werden.

---

## BATCH 08 – Bezirksgrafiken

Verarbeite die Bezirksarchetypen in dieser Reihenfolge:

1. Finanzzentrum
2. Hafenquartier
3. Industriegürtel
4. Altstadt
5. Technologiepark
6. Verwaltungszentrum
7. Nachtviertel
8. Universitätsviertel
9. Logistikkorridor
10. wohlhabendes Wohngebiet
11. dichtes Misch- und Wohngebiet
12. Außenbezirk und Gewerbering

### Pro Bezirksarchetyp

Erzeuge:

1. Normalzustand Tag
2. Normalzustand Nacht
3. Wirtschaftsboom Tag
4. Wirtschaftsboom Nacht
5. Krise Tag
6. Krise Nacht
7. erhöhte Behördenaktivität Tag
8. erhöhte Behördenaktivität Nacht

### Bezirks-Prompt

```text
Create an ultra-realistic gameplay district environment for SHADOWGRID.

District archetype:
{DISTRICT_ARCHETYPE}

City size class:
{CITY_SIZE_CLASS}

State:
{DISTRICT_STATE}

Time:
{TIME_OF_DAY}

The environment must look like a plausible contemporary German urban district.
Show the gameplay state through architecture, activity, lighting, maintenance, traffic and public-space atmosphere.

Do not show real company branding, real police insignia, private addresses or explicit criminal activity.

Keep a visually calm area for interface overlays.
```

---

## BATCH 09 – Unternehmen

Verarbeite:

1. Gastronomie
2. Eventagentur
3. Sicherheitsunternehmen
4. Logistikunternehmen
5. Technologieunternehmen
6. Immobilienverwaltung
7. Bauunternehmen
8. Medienunternehmen

### Pro Unternehmen

Erzeuge:

1. Außenansicht Stufe 1
2. Außenansicht Stufe 2
3. Außenansicht Maximalstufe
4. Innen- oder Managementansicht
5. schlechter Zustand
6. geprüft, eingefroren oder geschlossen

### Unternehmens-Prompt

```text
Create an ultra-realistic contemporary German business environment for SHADOWGRID.

Business category:
{BUSINESS_CATEGORY}

Development level:
{BUSINESS_LEVEL}

Operational state:
{BUSINESS_STATE}

The business must appear plausible, professional and suitable for a modern German city.
The visual progression between levels must be clear through scale, equipment, architecture, staffing and quality.

No real company logos.
No readable brand names.
No illegal activity.
No embedded UI text.
Reserve space for management statistics.
```

---

## BATCH 10 – Hauptquartier und Einrichtungen

Verarbeite:

1. Hauptquartier
2. Finanzbüro
3. Informationszentrum
4. Logistikzentrum
5. Personalakademie
6. Compliancebüro

### Pro Einrichtung

1. Stufe 1
2. Stufe 2
3. Maximalstufe
4. gestörter oder eingeschränkter Zustand

Das Hauptquartier muss als wiederkehrender visueller Kern erkennbar bleiben.

Ausbaustufen dürfen nicht wie völlig andere Gebäude wirken.

---

## BATCH 11 – Spezialisten

Verarbeite:

1. Stratege
2. Finanzleitung
3. Bezirkskoordination
4. Informationsanalyse
5. Verhandlung
6. Sicherheitsmanagement
7. Personalmanagement
8. Technologieexperte

### Pro Rolle

1. jüngere weibliche Person
2. jüngere männliche Person
3. erfahrene weibliche Person
4. erfahrene männliche Person

Danach:

* 16 zusätzliche Boss- und Spieleravatar-Presets.

### Charakter-Prompt

```text
Create an original ultra-realistic professional character portrait for SHADOWGRID.

Role:
{SPECIALIST_ROLE}

Age range:
{AGE_RANGE}

Presentation:
{PRESENTATION}

Character traits:
{CHARACTER_TRAITS}

Visual direction:
contemporary professional clothing,
subtle cyber-noir corporate atmosphere,
credible German or international urban workplace context,
natural facial expression,
cinematic portrait lighting,
highly realistic skin and fabric,
neutral or transparent background,
clear separation from the background,
no branding,
no weapon,
no gangster costume,
no celebrity resemblance,
no stereotypical ethnic presentation.
```

Sorge über alle Charaktere hinweg für Vielfalt bei:

* Hautfarbe
* Alter
* Haarstruktur
* Gesichtsform
* Körperbau
* sichtbaren Behinderungen, soweit respektvoll darstellbar
* professioneller Kleidung

Vermeide Tokenismus und stereotype Rollenzuweisung.

---

## BATCH 12 – PvP

Verarbeite:

1. Wirtschaftsangriff
2. Informationsoperation
3. Einflusskonflikt
4. Personalabwerbung
5. verdeckte Störungsoperation

### Pro PvP-Art

1. Vorbereitung
2. Erfolg
3. Fehlschlag

### PvP-Prompt

```text
Create an ultra-realistic strategic multiplayer conflict visual for SHADOWGRID.

Conflict type:
{PVP_TYPE}

Phase:
{PVP_PHASE}

Represent the conflict through business competition, strategic planning, data analysis, negotiations, market pressure or organizational disruption.

The image must remain abstract and non-instructional.

Do not depict:
technical hacking instructions,
physical attack methods,
weapon use,
graphic violence,
private targets,
real companies,
real authorities.

Use cinematic strategic tension and reserve space for operation results.
```

---

## BATCH 13 – Kartell und Kriege

Erzeuge:

1. Spannung
2. Ultimatum
3. Vorbereitung
4. aktiver Konflikt
5. Wendepunkt
6. Waffenstillstand
7. Nachwirkungen
8. neutrales Gebiet
9. umkämpftes Gebiet
10. kontrolliertes Gebiet
11. dominantes Gebiet
12. blockiertes Gebiet
13. Allianz geschlossen
14. Vertrag gebrochen
15. Friedensvertrag

Darstellung:

* strategische Karten,
* Kontrollräume,
* Verhandlungen,
* Unternehmensdruck,
* Netzwerkverbindungen,
* territoriale Einflussdarstellung.

Keine Schlachtfeld- oder Shooterästhetik.

---

## BATCH 14 – Kartell-Wappensystem

Erzeuge als SVG:

### Grundformen

20 unterschiedliche Formen.

### Symbole

40 unterschiedliche neutrale Symbole.

### Muster

12 Hintergrundmuster.

### Rahmen

12 Rahmenvarianten.

Alle Elemente müssen:

* kombinierbar,
* einfärbbar,
* auch klein erkennbar,
* ohne extremistische Bedeutung,
* ohne reale Gang- oder Organisationssymbole

sein.

Erstelle zusätzlich einen Wappen-Konfigurator-Test mit mindestens 100 zufällig kombinierten Wappen.

Prüfe auf:

* visuelle Duplikate,
* schlechte Kontraste,
* unleserliche Kombinationen,
* unbeabsichtigte problematische Symbole.

---

## BATCH 15 – Weltereignisse

Erzeuge:

1. Hafenstreik
2. Finanzprüfung
3. Datenleck
4. Wirtschaftskrise
5. Medienkampagne
6. Technologieboom
7. Großrazzia
8. Arbeitskräftemangel
9. Immobilienboom
10. Sicherheitskrise
11. Friedensinitiative
12. Lieferkettenunterbrechung

Ereignisbilder dürfen keine realen Firmen, Behörden oder Personen darstellen.

Die Großrazzia verwendet ausschließlich fiktive neutrale Behördenkennzeichnungen.

---

## BATCH 16 – Tutorial

Erzeuge:

1. Deutschlandkarte und Stadtwahl
2. Stadtprofil
3. erstes Unternehmen
4. Spezialisten
5. Ressourcen
6. erste Operation
7. Bezirkskontrolle
8. Player-versus-Player
9. Kartellbeitritt
10. Kartellkrieg und Saisonziele

Tutorialbilder:

* keine eingebrannten Erklärtexte,
* klare visuelle Schwerpunktbereiche,
* UI-Pfeile und Beschriftungen werden separat im Frontend dargestellt.

---

## BATCH 17 – UI-Icons

Erzeuge alle Icons als SVG.

### Navigation

* Kommando
* Stadt
* Deutschland
* Netzwerk
* Unternehmen
* Spezialisten
* Operationen
* PvP
* Kartell
* Kartellkrieg
* Gebiete
* Allianzen
* Diplomatie
* Ermittlungen
* Forschung
* Nachrichten
* Ranglisten
* Profil
* Einstellungen
* Administration

### Ressourcen

* Bargeld
* Kapital
* Einfluss
* Informationen
* Logistik
* Personal
* Loyalität
* Legitimität
* Furcht
* Ermittlungsdruck
* Stress
* Stabilität
* Reputation
* Marktanteil
* Verteidigung
* Aktivität

### Status

Erzeuge die vollständige Statusliste aus dem bestehenden Asset-Katalog.

### PvP

Erzeuge die vollständige PvP-Iconliste.

### Kartell und Diplomatie

Erzeuge die vollständige Kartell- und Diplomatie-Iconliste.

### Unternehmen und Gebäude

Erzeuge die vollständige Unternehmens- und Gebäude-Iconliste.

### Allgemeine Bedienung

Erzeuge die vollständige allgemeine UI-Iconliste.

Iconregeln:

* einheitliche Strichstärke,
* 24 × 24 ViewBox,
* auch bei 16 × 16 erkennbar,
* `currentColor`,
* keine eingebetteten Rasterbilder,
* keine unnötigen Details,
* zugängliche Bezeichnungen in einer separaten Metadatendatei.

---

## BATCH 18 – Wetter und Overlays

Erzeuge:

### Wetter

1. Regen
2. Starkregen
3. Schnee
4. Nebel
5. Sturm
6. Hitze
7. bewölkter Lichtfilter

### Zustände

8. Wirtschaftsboom
9. Krise
10. erhöhte Behördenaktivität
11. Kartellkontrolle
12. umkämpfter Bezirk
13. gesperrtes Gebiet

### Oberflächentexturen

14. dunkles Glas
15. gebürstetes Metall
16. feines Kartenraster
17. Aktenstruktur
18. Beton
19. Asphalt
20. technisches Netzwerk

Overlays benötigen transparente Hintergründe.

---

## BATCH 19 – Ranglisten und Belohnungen

Erzeuge:

1. Goldmedaille
2. Silbermedaille
3. Bronzemedaille
4. stärkster Spieler
5. stärkstes Kartell
6. beste Wirtschaft
7. beste Bezirkskontrolle
8. beste Diplomatie
9. bestes Informationsnetzwerk
10. höchste Stabilität
11. beste Verteidigung
12. stärkste Erholung
13. erfolgreichste Allianz
14. Top 1
15. Top 10
16. Top 100
17. Stadtmeister
18. Landesmeister
19. Deutschlandmeister

Bevorzugt SVG.

Keine echten staatlichen Wappen verwenden.

---

## BATCH 20 – Mobile Assets

Erzeuge beziehungsweise exportiere:

1. iOS-App-Icon
2. Android-App-Icon
3. Android Adaptive Foreground
4. Android Adaptive Background
5. Android Monochrome Icon
6. Splash Desktop-ähnlich
7. Splash Android
8. Splash iOS
9. Benachrichtigungssymbol
10. Mobile-Offline-Hintergrund
11. Mobile-Wartungs-Hintergrund
12. Mobile-Kriegsraum-Hintergrund

Prüfe Safe Areas für:

* iPhone Dynamic Island
* iPhone Notch
* Android Punch-Hole
* Android Navigation
* Tablets

---

## BATCH 21 – Store und Marketing

Erzeuge beziehungsweise erstelle aus echten App-Screens:

### Google Play

1. App-Icon
2. Feature Graphic
3. Stadtwahl-Screenshot
4. Dashboard-Screenshot
5. Stadtkarte-Screenshot
6. PvP-Screenshot
7. Kartell-Screenshot
8. Kartellkrieg-Screenshot
9. Unternehmen-Screenshot
10. Rangliste-Screenshot

### Apple App Store

11–18. acht iPhone-Screenshots
19–22. vier iPad-Screenshots

### Web und Community

23. Open-Graph-Grafik
24. Community-Banner
25. Discord-Banner
26. Saisonstart-Banner
27. Saisonfinale-Banner
28. Closed-Alpha-Banner
29. Open-Beta-Banner
30. Release-Banner

Store-Screenshots dürfen erst nach funktionierender Implementierung erstellt werden.

Keine erfundenen Spieloberflächen darstellen.

---

# 11. Responsive Varianten

Für jedes Raster-Masterasset:

```text
320 px
640 px
960 px
1280 px
1920 px
2560 px
3840 px
```

Erzeuge:

* AVIF
* WebP
* PNG nur als notwendiger Fallback

Für transparente Assets:

* PNG
* WebP mit Transparenz
* SVG, sofern möglich

Nutze:

* korrekte Farbprofile,
* verlustarme Kompression,
* Metadatenbereinigung,
* Content Hashes.

---

# 12. Mobile Cropping

Mobile-Bilder dürfen nicht einfach mittig abgeschnitten werden.

Erstelle pro wichtigem Asset:

* Fokuspunkt
* Safe Area
* Mobile Crop
* Tablet Crop
* Desktop Crop

Metadatenbeispiel:

```json
{
  "focal_point": {
    "x": 0.62,
    "y": 0.44
  },
  "safe_area": {
    "x": 0.08,
    "y": 0.08,
    "width": 0.84,
    "height": 0.76
  }
}
```

---

# 13. Qualitätsprüfung

Prüfe jedes Rasterbild automatisiert und visuell.

## Technische Prüfung

* Datei existiert
* Dateigröße größer als Mindestwert
* Bild kann geöffnet werden
* richtige Auflösung
* richtiges Seitenverhältnis
* keine beschädigten Pixelblöcke
* gültiges Farbprofil
* keine unerwartete Transparenz
* responsive Varianten vorhanden

## Inhaltliche Prüfung

* Asset entspricht dem Manifest
* Architektur plausibel
* Tageszeit korrekt
* Zustand korrekt
* keine eingebrannten Texte
* keine Wasserzeichen
* keine realen Markenlogos
* keine echten Behördenlogos
* keine realen Kennzeichen
* keine offensichtlichen Bildfehler
* keine deformierten Personen
* keine kopierte Fotoperspektive
* keine extremistischen Symbole
* keine explizite Gewalt
* genügend UI-Freiraum

## Stilprüfung

Bewerte 0 bis 100:

```text
Realismus
Stilkonsistenz
Komposition
Materialqualität
Lichtqualität
Architekturplausibilität
UI-Eignung
Mobile-Eignung
Originalität
Sicherheitskonformität
```

Freigabe nur, wenn:

```text
Gesamtwert mindestens 85
Sicherheitskonformität 100
UI-Eignung mindestens 80
Originalität mindestens 85
```

---

# 14. Visuelle Konsistenzprüfung

Nach jedem Batch:

1. Kontaktbogen erstellen.
2. alle Bilder nebeneinander vergleichen.
3. Farbstimmung prüfen.
4. Goldanteil prüfen.
5. Cyber-Noir-Anteil prüfen.
6. Realismus prüfen.
7. Helligkeitsverteilung prüfen.
8. Gesichter und Architektur prüfen.
9. Ausreißer markieren.
10. Ausreißer regenerieren.

Kontaktbögen speichern unter:

```text
assets/reports/contact-sheets/
```

---

# 15. Sicherheitsprüfung

Jedes Bild wird geprüft auf:

* NS-Symbole
* extremistische Symbole
* reale Gangzeichen
* reale Kartellzeichen
* reale Behördenlogos
* reale Firmenlogos
* lesbare Kennzeichen
* lesbare Adressen
* erkennbare reale Personen
* grafische Gewalt
* Waffenfokus
* illegale Anleitungen
* Wasserzeichen
* urheberrechtlich verdächtige Kopien

Unsichere Assets verschieben nach:

```text
assets/rejected/
```

Sie dürfen nicht im Build erscheinen.

---

# 16. Metadaten pro Asset

Erstelle für jedes Asset:

```text
assets/metadata/{asset_id}.json
```

Schema:

```json
{
  "asset_id": "city-koeln-hero-day-21x9-v1",
  "manifest_order": 1001,
  "category": "city",
  "batch": "premium-cities",
  "city": "koeln",
  "variant": "day",
  "gameplay_state": "normal",
  "aspect_ratio": "21:9",
  "width": 3840,
  "height": 1646,
  "source_type": "generated",
  "provider": "configured-provider",
  "model": "configured-model",
  "prompt_file": "assets/prompts/city-koeln-hero-day-21x9-v1.txt",
  "prompt_version": "1.0.0",
  "style_version": "1.0.0",
  "seed": 100001,
  "content_hash": "sha256",
  "contains_text": false,
  "contains_real_people": false,
  "contains_real_logos": false,
  "moderation_status": "approved",
  "quality_score": 91,
  "quality_status": "approved",
  "review_status": "automatic-approved",
  "focal_point": {
    "x": 0.5,
    "y": 0.45
  },
  "created_at": "ISO-8601",
  "license": "project-owned-generated-asset"
}
```

---

# 17. Integrationstest

Nach jedem Batch:

* Assets in das Spiel laden.
* fehlende Pfade erkennen.
* responsive Varianten testen.
* Dark Mode prüfen.
* Mobile prüfen.
* Datensparmodus prüfen.
* Ladezeiten prüfen.
* Alt-Texte prüfen.
* Screenreader-Verhalten prüfen.
* Fallback testen.

Kein Asset gilt als fertig, nur weil die Datei generiert wurde.

Es muss im tatsächlichen Spiel funktionieren.

---

# 18. Performancebudgets

Maximale Zielgrößen:

| Assettyp         | Produktionsziel |
| ---------------- | --------------: |
| Mobile Hero      |      250–450 KB |
| Desktop Hero     |      400–850 KB |
| Ultra-Wide Hero  |   700 KB–1,4 MB |
| Unternehmensbild |      300–700 KB |
| Charakterporträt |      150–350 KB |
| Tutorialbild     |      250–600 KB |
| SVG-Icon         |     unter 20 KB |
| komplexes SVG    |    unter 100 KB |

Überschreitungen müssen dokumentiert und begründet werden.

---

# 19. Generierungsbefehle

Erstelle:

```bash
make assets-manifest
make assets-style-proof
make assets-generate-next
make assets-generate-batch BATCH=branding
make assets-generate-city CITY=koeln
make assets-generate-all
make assets-resume
make assets-validate
make assets-optimize
make assets-contact-sheets
make assets-integration-test
make assets-report
```

Zusätzlich:

```bash
pnpm assets:manifest
pnpm assets:style-proof
pnpm assets:next
pnpm assets:batch --batch=branding
pnpm assets:city --city=koeln
pnpm assets:all
pnpm assets:resume
pnpm assets:validate
pnpm assets:optimize
pnpm assets:report
```

---

# 20. Kostenkontrolle

Vor jeder kostenpflichtigen Generierung:

* geschätzte Kosten berechnen,
* Batchkosten dokumentieren,
* Tages- und Gesamtlimit beachten.

Konfiguration:

```env
ASSET_DAILY_BUDGET_EUR=20
ASSET_TOTAL_BUDGET_EUR=500
ASSET_MAX_RETRIES=3
```

Wenn ein Budget überschritten würde:

* keine kostenpflichtige Anfrage senden,
* prozeduralen Fallback verwenden,
* Asset als `provider_budget_blocked` markieren,
* Bericht aktualisieren.

Kosten werden in Euro dokumentiert.

---

# 21. Abnahmeberichte

Erstelle:

```text
assets/reports/ASSET_MANIFEST_REPORT.md
assets/reports/STYLE_CONSISTENCY_REPORT.md
assets/reports/IMAGE_QUALITY_REPORT.md
assets/reports/IMAGE_SAFETY_REPORT.md
assets/reports/ASSET_LICENSE_REPORT.md
assets/reports/ASSET_PERFORMANCE_REPORT.md
assets/reports/MOBILE_CROP_REPORT.md
assets/reports/ASSET_INTEGRATION_REPORT.md
assets/reports/ASSET_GENERATION_COST_REPORT.md
assets/reports/FINAL_ASSET_COVERAGE.md
```

`FINAL_ASSET_COVERAGE.md` muss enthalten:

* Gesamtzahl
* generiert
* prozedural erzeugt
* freigegeben
* Review erforderlich
* abgelehnt
* fehlend
* Kosten
* Speicherverbrauch
* Assets pro Kategorie
* Assets pro Stadt
* Assets ohne Mobile-Variante
* Assets ohne Metadaten
* Assets ohne gültige Lizenzangabe

---

# 22. Definition of Done

Die Grafikproduktion ist nur abgeschlossen, wenn:

1. das vollständige Manifest existiert,
2. jeder verpflichtende Eintrag verarbeitet wurde,
3. jedes Asset eine eindeutige ID besitzt,
4. jedes Asset Metadaten besitzt,
5. jedes Asset einen gespeicherten Prompt besitzt,
6. jedes Asset validiert wurde,
7. kein abgelehntes Asset im Produktionsbuild enthalten ist,
8. alle wichtigen Assets responsive Varianten besitzen,
9. Mobile Crops geprüft wurden,
10. alle Icons gültige SVGs sind,
11. alle Stadtpakete vollständig sind,
12. alle Bezirkszustände vorhanden sind,
13. alle Unternehmen vorhanden sind,
14. alle Spezialistenrollen vorhanden sind,
15. PvP und Kartellkrieg vollständig bebildert sind,
16. Store-Screenshots echte Spieloberflächen zeigen,
17. alle Assetpfade im Spiel funktionieren,
18. Datensparmodus funktioniert,
19. Performancebudgets eingehalten oder begründet sind,
20. sämtliche Abschlussberichte erstellt wurden.

---

# 23. Abschließende Codex-Anweisung

Beginne jetzt mit:

```text
1. vorhandenes Asset-System analysieren
2. Asset-Manifest erzeugen
3. Provider prüfen
4. Style-Proof generieren
5. Style Lock validieren
6. jedes Asset exakt nach Manifestreihenfolge generieren
7. jedes Asset prüfen
8. Varianten erzeugen
9. Spielintegration testen
10. Fortschritt nach jedem Asset speichern
```

Überspringe keine Pflichtgrafik.

Generiere nicht ungeprüft Hunderte Bilder gleichzeitig.

Beende die Aufgabe nicht nach einigen Beispielbildern.

Die Aufgabe ist erst abgeschlossen, wenn:

> Die vollständige SHADOWGRID-Asset-Bibliothek in der definierten Reihenfolge erzeugt, validiert, optimiert, dokumentiert und im tatsächlichen Web-, Android- und iOS-Spiel integriert wurde.
