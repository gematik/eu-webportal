# Frontend-Meilensteinplan

## Zielbild

Angular stellt den portalweiten Rahmen bereit. Header und Footer gehoeren zur
Shell; der Inhaltsbereich dazwischen scrollt unabhaengig. Fachliche Anwendungen,
beginnend mit der polnischen ISM, werden als Web Components eingebunden.

Der erste PoC zeigt und validiert die polnische Suchmaske. Er sendet keine
Suchanfrage ab. Eine spaetere Unterstuetzung weiterer Laender bleibt moeglich,
ist aber kein Grund, jetzt ein allgemeines ISM-Datenmodell zu entwerfen.

## Meilensteine

### F0 – Angular-Shell (abgeschlossen)

- Standalone-Angular-Anwendung mit Routing und SCSS anlegen.
- Einen klaren Host-Bereich fuer spaetere Web Components bereitstellen.
- Build erfolgreich; Tests fuer Shell und Host vorhanden.

### F1 – Portal-Layout (abgeschlossen)

- Header, scrollbaren Hauptbereich und Footer in der Angular-Shell umsetzen.
- Header und Footer bleiben sichtbar; nur der Inhaltsbereich scrollt.
- Responsive Verhalten, Skip-Link, Fokusfuehrung und semantische Landmarken
  sicherstellen.
- Grid-Layout begrenzt Scrollen auf den Inhaltsbereich; kleine Viewports erhalten
  angepasste Abstaende.
- Automatisierte Shell-Tests pruefen Landmarken, Navigation und Fokusziel.
  Der Testlauf wurde vom Nutzer als erfolgreich bestaetigt.

### F2 – Web-Component-Einbindung (abgeschlossen)

- Startseite mit Textkacheln als Einstieg fuer fachliche Anwendungen bereitstellen.
- Die Internationale Patientensuche liegt unter `/patientensuche`,
  erreichbar per Kachel und Header-Link.
- Angular-Host fuer ein benutzerdefiniertes Element vorbereiten.
- Elementname, Eingaben, Ausgaben und Fehlerdarstellung fuer die erste
  Komponente dokumentieren.
- Angular-Templatepruefung gezielt fuer das Host-Element konfigurieren; keine
  globale Abschaltung der Templatepruefung.
- Die erste Lit-Komponente ist eingebunden; eine produktive Suchanbindung
  bleibt ausserhalb des PoC.

### F3 – Polnische ISM-Komponente (abgeschlossen)

- Beim Build erzeugt `npm run ism:generate` aus der polnischen ISM ein Anzeigemodell.
- Die Lit-Komponente `<ism-patient-search>` zeigt Felder, Pflichtangaben, Formathinweise und Hilfsbild.
- Die Formatpruefung beim Tippen (Teil von F4) ist bereits enthalten.
- Polen als einziges Land im ersten PoC anbieten.
- Suchfelder anhand der bereitgestellten polnischen ISM-Beschreibung darstellen.
- Labels und Pflichtfelder aus den verfuegbaren Metadaten anzeigen.
- Keine Suche absenden und keine Token- oder Backend-Integration ergaenzen.
- Generator- und Frontend-Tests wurden vom Nutzer als erfolgreich bestaetigt.

### F4 – Eingabevalidierung (abgeschlossen)

- Verfuegbare Feldformate beim Eingeben pruefen.
- Pflichtfeld- und Formatfehler verstaendlich und barrierearm ausgeben.
- Fehlende oder nicht uebertragbare Regeln nicht erraten; Verhalten sichtbar
  machen und dokumentieren.
- Gueltige und ungueltige Eingaben einschliesslich Randfaellen testen.
- Eingabevalidierung im Browser vom Nutzer erfolgreich geprueft.
  Die uebergreifende Browserabnahme von Layout und Navigation bleibt Teil von F5.

### F4a – Eingangsprofile und Laenderabdeckung (in Bearbeitung; vor F5)

Die bisherige Umsetzung deckt die Beispiele PL, GR und IS ab. Inzwischen liegen
28 XML-Dateien in `ism\sources`. DE und EU sind nicht im Quellenordner.
Ihre Aufnahme bedeutet noch keine Freigabe fuer
Generierung oder Anzeige. Die folgenden Schritte werden nacheinander bearbeitet.

#### Schritt 1 – Schnittstellenfragment pruefen (abgeschlossen)

Stand: 26 der aktuell 28 lokalen Quellen auf `searchFields` reduziert.
CH und FR bleiben unveraenderte negative Referenzen. FR wird als Fehlerbeispiel
angeboten, CH nicht. Der Diagnosemodus erzeugt explizite Fehlerartefakte,
keine reparierten Formulare. Fragment- und Fehlerfalltests wurden vom Nutzer
als erfolgreich bestaetigt.

- Die Systemausgabe beginnt gemaess Klarstellung mit
  `<searchFields xmlns="http://ec.europa.eu/sante/ehncp/ism">` und enthaelt
  darunter `country` samt Landcode. Die SMP-Huelle wird nicht geliefert.
- Ein solches Fragment als Referenzfixture verwenden. Namespace und Landcode
  sind darin enthalten und muessen nicht ergaenzt oder geraten werden.
- Die Transportkodierung des Schnittstellen-Response bleibt separat zu klaeren.
- Vollstaendige XML-Fixtures und Schnittstellenfragmente durch getrennte,
  nachvollziehbare Eingangsadapter auf dieselbe unterstuetzte Struktur abbilden.
  Fehlende Metadaten nicht erraten und Quellen nicht stillschweigend reparieren.
- Akzeptanz: Eine vollstaendige Quelle und ihr entsprechendes Fragment erzeugen
  dasselbe Anzeigemodell und dieselben Medien. Unvollstaendige oder mehrdeutige
  Eingaben werden mit konkreter Diagnose abgelehnt.

#### Schritt 2 – Alle XML-Quellen einzeln inventarisieren (abgeschlossen)

- Alle vorhandenen Dateien (aktuell 28)
  unabhaengig pruefen, ohne generierte Deployment-Dateien zu
  ersetzen. Ein Fehler in einem Land darf die Bestandsaufnahme nicht abbrechen.
- Je Datei Landcode, Eingangsprofil, Felder, Gruppen, Regex und Medien erfassen.
- XML-Lesbarkeit, XSD-Konformitaet, Generatorunterstuetzung und Browserdarstellung
  getrennt bewerten. Eine erfolgreiche Generierung belegt keine XSD-Konformitaet.
- Ergebnisse je Datei dokumentieren. `el.xml` und `gr.xml` getrennt untersuchen,
  aber doppelte Landcodes vor gemeinsamer Auslieferung bewusst aufloesen.
- Akzeptanz: Jede Datei hat einen Befund mit unterstuetzten Eigenschaften,
  konkreten Blockern und benoetigten Erweiterungen. Keine pauschale
  Unterstuetzungszusage fuer alle Laender.

Bestandsaufnahme vom 13.10.2026, Generatorstatus aktualisiert am 14.10.2026:
Alle 28 Dateien sind XML-lesbar.
Die Einzelpruefung mit dem bestehenden Parser hat keine Deployment-Dateien
geschrieben. Mit der inzwischen implementierten CHOICE-Unterstuetzung erzeugen
23 Dateien Modelle fuer 22 unterschiedliche Laender.
Fuenf Dateien werden explizit abgelehnt. Die XSD-Pruefung gegen
`specs\ism\schema\ehdsi-ism-2023.xsd` ergibt 24 konforme und vier abweichende
ISM-Strukturen. Bei CH und FR betrifft diese Aussage den eingebetteten
ISM-Block, nicht die Validitaet der SMP-Huelle oder ihrer Signatur.

Die Tabelle beschreibt ausschliesslich `patientSearch`. Zahlen in der
Regelspalte bezeichnen die geforderte Ziffernanzahl. Alle Felder sind
Pflichtfelder, ausser NO und SK. Die Originalmuster bleiben in den Quellen,
die Kurzbeschreibungen sind keine Ersatzregeln. Alle NORMAL-Felder haben
unterschiedliche Domains innerhalb ihrer jeweiligen Maske.

| Datei / Land | Felder und Gruppen | Format / Besonderheit | Hilfsmedien | XSD | Generator |
|---|---|---|---|---|---|
| at.xml / AT | CHOICE: 1 oder 4 Felder | Token oder Ausweisnummer, Vorname, Nachname, Geburtsdatum als `id` | keine | konform | Modell erzeugt, CHOICE |
| ch.xml / CH | anderes Profil: ID und Geburtsdatum | `min`/`max` statt unterstuetzter Feldmetadaten | keine | abweichend | country nicht unter searchFields |
| cy.xml / CY | 1 ID und birthDate | Ziffern und Datum, birthDate/@format sowie leerer xs:date-Inhalt unzulaessig | PNG | abweichend | birthDate fehlt |
| cz.xml / CZ | NORMAL: 1 | 8 bis 9 alphanumerische Zeichen | PNG | konform | Modell erzeugt |
| dk.xml / DK | NORMAL: 1 | 6 und 4 Ziffern, Bindestrich optional | keine | konform | Modell erzeugt |
| ee.xml / EE | NORMAL: 1 | 11 Ziffern | keine | konform | Modell erzeugt |
| el.xml / GR | NORMAL: 1 | 11 Ziffern, identisch mit gr.xml | JPEG, als PNG deklariert | konform | Modell erzeugt, Medienwarnung |
| es.xml / ES | CHOICE: 2 oder 1 Felder | regionale Kennung plus Region oder nationale Kennung | JPEG | konform | Modell erzeugt, CHOICE |
| fi.xml / FI | NORMAL: 1 | Regex mit unter v-Flag unzulaessiger Zeichenklasse | keine | konform | PATTERN_NOT_PORTABLE |
| fr.xml / FR | anderes Profil: 1 ID | `min`/`max` statt unterstuetzter Feldmetadaten | keine | abweichend | country nicht unter searchFields |
| gr.xml / GR | NORMAL: 1 | 11 Ziffern, identisch mit el.xml | JPEG, als PNG deklariert | konform | Modell erzeugt, Medienwarnung |
| hr.xml / HR | NORMAL: 1 | 9 Ziffern | keine | konform | Modell erzeugt |
| hu.xml / HU | NORMAL: 2 in einer Gruppe | 9 Ziffern und 6 Ziffern plus 2 Grossbuchstaben | JPEG | konform | Modell erzeugt |
| ie.xml / IE | NORMAL: 1 | 18 Ziffern laut Quelle | keine | konform | Modell erzeugt |
| is.xml / IS | NORMAL: 1 | 6 Ziffern und 4 alphanumerische Zeichen | keine | konform | Modell erzeugt |
| it.xml / IT | NORMAL: 2 in einer Gruppe | strukturierte Kennung und 5 Ziffern | keine | konform | Modell erzeugt |
| lt.xml / LT | NORMAL: 1 | 11 Ziffern | keine | konform | Modell erzeugt |
| lu.xml / LU | NORMAL: 1 | 13 Ziffern | PNG | konform | Modell erzeugt |
| lv.xml / LV | NORMAL: 1 | 6 Ziffern, Bindestrich, 5 Ziffern | JPEG, als PNG deklariert | konform | Modell erzeugt, Medienwarnung |
| mt.xml / MT | NORMAL: 1 | 7 Ziffern und Grossbuchstabe | keine | konform | Modell erzeugt |
| nl.xml / NL | 1 ID und birthDate | 9 Ziffern und Datum, birthDate/@format sowie leerer xs:date-Inhalt unzulaessig | keine | abweichend | birthDate fehlt |
| no.xml / NO | NORMAL: 1 | optional, leeres Format, keine Regel ergaenzt | keine | konform | Modell erzeugt |
| pl.xml / PL | NORMAL: 1 | 11 Ziffern | JPEG | konform | Modell erzeugt |
| pt.xml / PT | NORMAL: 1 | 9 Ziffern | PNG | konform | Modell erzeugt |
| ro.xml / RO | NORMAL: 2 Gruppen mit je 1 Feld | CID: 20 Ziffern, PIN: 6 Ziffern | keine | konform | Modell erzeugt |
| se.xml / SE | NORMAL: 1 | 12 Ziffern | keine | konform | Modell erzeugt |
| si.xml / SI | NORMAL: 1 | 13 Ziffern | keine | konform | Modell erzeugt |
| sk.xml / SK | NORMAL: 1 | optional, 9 bis 10 Ziffern mit Positionsregeln | PNG | konform | Modell erzeugt |

Die SHA256-Hashes von EL und GR stimmen ueberein. Beide Dateien wurden getrennt
geprueft, bei Auslieferung bleibt nur das Land GR. Die Browserdarstellung ist
mit dieser Bestandsaufnahme nicht fuer alle Modelle abgenommen.

Gepruefte Referenzen fuer Schritt 3 sind HU und IT (zwei Felder in einer Gruppe)
sowie RO (zwei NORMAL-Gruppen). NO und SK decken optionale Angaben bzw. fehlende
Formate ab. Ein zusaetzlicher Testfall mit gleicher Domain sichert die unabhaengige
Feldidentitaet ab. Fuer Schritt 4 dient ES als Referenz mit Alternativen
aus zwei beziehungsweise einem Feld, AT ergaenzt den Fall mit vier Feldern.
CHOICE-Tests wurden vom Nutzer als erfolgreich bestaetigt, die Browserabnahme
der CHOICE-Auswahl bleibt ausstehend. HU, IT und RO wurden auch im Browser
erfolgreich geprueft.
CY/NL benoetigen eine Profilklaerung, FI eine explizite Regex-Entscheidung,
CH/FR passende Quellen. Keine dieser Quellen wird stillschweigend korrigiert.

#### Schritt 3 – Masken mit mehreren Eingabefeldern pruefen (abgeschlossen)

Stand: Tests und Browserpruefung vom Nutzer erfolgreich bestaetigt.
Generator-Tests verwenden die realen Quellen
HU, IT und RO und pruefen Feldreihenfolge, Regeln, Pflichtangaben und Medien.
Komponententests pruefen die Regeln dieser Masken sowie getrennte Werte,
Fehler und Interaktionszustaende. Zusaetzliche Faelle decken gleiche Domains
und Labels, optionale Felder ohne Format sowie den Maskenwechsel ab.

Die Feldposition im geordneten Modell identifiziert den lokalen Eingabezustand
und die DOM-Verknuepfungen. Die Domain bleibt unveraendert als fachliche
Metadaten erhalten, ist aber kein eindeutiger Feldschluessel.
Ein Maskenwechsel setzt Werte und Interaktionszustaende vollstaendig zurueck.
Das JSON-Format bleibt unveraendert.

- Reale Mehrfeldmasken aus der Bestandsaufnahme als Referenzfaelle verwenden.
- Alle Felder in Quellreihenfolge darstellen und unabhaengig validieren.
- Eindeutige Feldidentitaeten sicherstellen. Die OID allein darf Felder nicht
  zusammenlegen, falls dieselbe Domain mehrfach vorkommt.
- Pflichtangaben, optionale Felder, fehlende Formate und vorhandene Hilfen pruefen.
- Akzeptanz: Anzahl und Reihenfolge stimmen mit der Quelle ueberein.
  Feldwerte und Fehlermeldungen beeinflussen keine anderen Felder.

#### Schritt 4 – CHOICE-Auswahl pruefen und umsetzen

Stand: Umsetzung implementiert, Tests vom Nutzer erfolgreich bestaetigt.
Browserabnahme der CHOICE-Auswahl ausstehend.
ES und AT werden ohne Quellkorrekturen als CHOICE-Modelle erzeugt.
`choiceGroups` erhaelt `ids/@display` und die Feldpositionen jeder Alternative.
NORMAL-Modelle behalten ihre bisherige Struktur.

Festgelegtes Verhalten: Keine Vorauswahl. Jede CHOICE-Gruppe hat eine eigene
tastaturbedienbare Auswahl. Eingaben und Interaktionszustaende bleiben je
Alternative erhalten, nur aktive Felder werden dargestellt und validiert.
NORMAL-Felder bleiben unabhaengig von der Auswahl sichtbar. Ein Maskenwechsel
loescht sowohl Auswahl als auch Eingaben. Mehrere CHOICE-Gruppen werden
unabhaengig voneinander behandelt.

- Eine reale `identifier type="CHOICE"`-Maske und die Bedeutung ihrer
  Alternativen, insbesondere `ids/@display`, als Referenz festlegen.
- Alternativen explizit im Anzeigemodell erhalten und eine Auswahl anbieten.
- Nur die aktive Alternative validieren. Pflichtfelder in inaktiven
  Alternativen duerfen das ausgewaehlte Suchverfahren nicht blockieren.
- Umgang mit Werten beim Wechsel, initialer Auswahl und mehreren Auswahlgruppen
  vor Umsetzung festlegen.
- Akzeptanz: Auswahl und Wechsel funktionieren per Tastatur. Regeln gelten
  ausschliesslich fuer die aktive Alternative und gehen bei Generierung nicht
  verloren. Nicht unterstuetzte Varianten bleiben explizite Fehler.

#### Schritt 5 – Freigegebenen Bestand integrieren

- Nur erfolgreich gepruefte Masken zur gemeinsamen Generierung zulassen.
- Laenderauswahl und Suchseiten aus demselben generierten Bestand versorgen,
  statt eine unabhaengige feste Laenderliste zu pflegen.
- Generator-, Modell-, Komponenten- und Navigationstests ergaenzen.
- Akzeptanz: Jedes angebotene Land hat eine generierte, darstellbare Maske.
  Nicht freigegebene Quellen bleiben sichtbar dokumentiert, aber werden nicht
  als nutzbare Suchmaske angeboten. Anschliessend erfolgt F5.

### F5 – Shell- und Komponentenintegration

- Angular-Shell und Web Component gemeinsam im Browser betreiben.
- Layout, Navigation, Scrollverhalten, Tastaturbedienung und Fehlerzustaende
  end-to-end pruefen.
- Build- und Startanleitung fuer das Frontend aktualisieren.

Nach F4a folgt die Browserabnahme mit den synthetischen XA-Ressourcen:
Musterwert `AB` akzeptieren, abweichende Eingaben und leere Pflichtangaben
nach Interaktion melden, Beispielbild anzeigen und keine Suchanfrage absenden.
Dabei Navigation ueber Kachel und Header sowie Scrollen und Tastaturbedienung
pruefen. Unit-Tests mit jsdom ersetzen diese Layout- und Browserpruefung nicht.

## Nicht Teil des ersten PoC

- Absenden einer Patientensuche oder Aufruf eines Backend-Endpunkts.
- Token-Handling und Authentifizierung.
- Frankreich oder weitere Laender, bevor deren ISM-Schema und Feldregeln
  geklaert sind.
- Ein vollstaendiges kanonisches Modell fuer alle ISM-Varianten.
- Styling und globale Navigation innerhalb der einzelnen Web Components.

## Arbeitsregeln

- Portalweites Layout und Navigation bleiben in Angular.
- Eine Web Component kapselt jeweils eine fachliche Anwendung.
- Der Austausch zwischen Shell und Komponente erfolgt ueber einen kleinen,
  expliziten Kontrakt; keine stillschweigende Abhaengigkeit auf Angular-Interna.
- Jede Ausbaustufe behaelt den PoC ohne Suchabsendung.
- Ein Meilenstein gilt als abgeschlossen, wenn seine Akzeptanzkriterien
  implementiert und durch Build beziehungsweise passende Tests abgedeckt sind.
