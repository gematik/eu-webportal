# Angular Shell

Standalone Angular-Anwendung mit Routing und SCSS.
Unterstuetzte Node-Versionen: `^22.22.3`, `^24.15.0` oder `>=26.0.0`.
Der [Frontend-Meilensteinplan](MILESTONE-PLAN.md) beschreibt den geplanten
Ausbau der Shell und der ISM-Web-Component.

Aus dem Repository-Root:

```powershell
npm --prefix frontend ci
npm --prefix frontend start
```

Die Anwendung ist unter `http://localhost:4200` erreichbar.

Public examples are the default dataset. Internal development is selected explicitly:

```powershell
npm --prefix frontend run start:internal
npm --prefix frontend run build:internal
```

The dataset is an application build configuration, not a browser-side switch.
Stop the development server before changing profiles. Public and internal inputs
and generated files remain in separate sibling directories:

```text
ism/
  public/
    sources/
    flags/
    generated/
  internal/
    sources/
    flags/
    generated/
```

Only the selected `generated` directory is served under `ism/`.
Raw XML files and unselected dataset outputs are not Angular assets.
The internal directory is versioned in GitLab but excluded from the GitHub
publishing export using the root `.githubignore`. See `ism/README.md`.
This filter applies only to a publishing workflow that explicitly processes it.
A normal Git push does not filter files or history.

```powershell
npm --prefix frontend run build
npm --prefix frontend test -- --watch=false
```

Der Produktionsbuild liegt in `frontend\dist\eu-webportal\browser`.
Unit-Tests verwenden Vitest mit jsdom.

## Verantwortlichkeiten

- `src\app\app.*`: Portal-Layout und Router-Outlet.
- `src\app\home\home.*`: Startseite mit Textkacheln fuer fachliche Anwendungen.
- `src\app\ism\ism-page.*`: Angular-Routenadapter fuer die ISM-Web-Component.
- `src\web-components\ism-patient-search\`: Lit-Web-Component `<ism-patient-search>`.

Die Startseite (`/`) verlinkt per Kachel auf die Internationale Patientensuche
(`/patientensuche`). Dieselbe Unterseite ist ueber die Hauptnavigation erreichbar.
Header, Inhalt und Footer nutzen die verfuegbare Bildschirmbreite mit gemeinsamen
Seitenabstaenden. Das Kachelraster bildet abhaengig von der verfuegbaren Breite
Spalten mit mindestens 16rem; auf schmaleren Bildschirmen passt sich eine einzelne
Spalte an. Freie Spalten bleiben erhalten, damit eine einzelne Kachel nicht die
gesamte Zeile fuellt.
Weitere Anwendungskacheln werden mit den jeweiligen fachlichen Anwendungen
ergaenzt. Die Anwendungen sollen spaeter als Lit/Web Components eingebunden werden.
Vier nicht verlinkte Kacheln mit den Namen „Dummy Anwendung 1“ bis
„Dummy Anwendung 4“ demonstrieren vorerst das responsive Raster.

Die Unterseite `/patientensuche` zeigt eine Zwischenseite zur E-Rezept-Einloesung.
Der Button „Patientensuche starten“ fuehrt zu `/patientensuche/suche`.
Diese Seite kombiniert die Laenderauswahl mit den darunterliegenden Suchparametern.
Nach Auswahl bleibt das Land ueber dieselbe Auswahl aenderbar. Direktlinks unter
`/patientensuche/XA`, `/patientensuche/XB` oder `/patientensuche/XC` bleiben im
oeffentlichen Profil erhalten.
Im internen Profil werden stattdessen die konfigurierten echten Laender angeboten.
API-Aufrufe, Authentifizierung und
Absenden sind nicht implementiert; das MVP1-Ziel bleibt unveraendert.

## ISM-Web-Component

Der Header bietet ein Burgermenue fuer fachliche Anwendungen. Menue und
Startseitenkacheln verwenden denselben Anwendungskatalog in
`src\app\applications.ts`. Nicht implementierte Anwendungen bleiben im Menue
als nicht verfuegbar gekennzeichnet, ohne Link. Die native Details-Auswahl
ist per Tastatur bedienbar und schliesst bei Navigation, Klick ausserhalb
oder Escape. Escape setzt den Fokus auf den Menueschalter zurueck.

`<ism-application>` kapselt die gesamte Fachanwendung: Laenderauswahl,
zentriertes Layout, Laenderwechsel und Suchmaske. Das optionale Attribut
`country` waehlt ein Land direkt aus. Ohne Land erscheint die Auswahl.
Das Ereignis `country-change` liefert den Landcode als `detail`, bei Rueckkehr
einen leeren String. Es ist `bubbles` und `composed`.
„Zurueck“ und „Abbrechen“ melden `search-cancel`, ebenfalls mit `bubbles` und
`composed`. Der Angular-Host navigiert damit zur Zwischenseite. Ein erneuter
Start beginnt ohne Land, Eingaben oder Datenschutzbestaetigung.
Alle Buttons der Patientensuche haben vollstaendig gerundete Seiten.
„Zurueck“ steht auf grossen Bildschirmen links in derselben Aktionszeile wie
„Abbrechen“ und „Patient suchen“. Mobil erscheint „Zurueck“ oberhalb der
Patientensuche. Die beiden anderen Aktionen teilen sich die untere Zeile.
`<ism-patient-search>` nimmt den Zurueck-Button ueber den Slot `back` auf.
Dieser Slot bleibt auch beim Laden und bei Ladefehlern sichtbar.
Die Komponente funktioniert ohne Angular. Der Angular-Host synchronisiert
lediglich das Attribut und das Ereignis mit den bestehenden URLs.
Dieser Adapter heisst `IsmPage`. Er existiert, weil der Angular-Router eine
Angular-Seite als Routenziel benoetigt. Er bettet `<ism-application>` ein,
uebergibt den Landcode aus der URL und uebersetzt `country-change` in Navigation.
So bleiben Direktlinks und Browser-Zurueck/Vorwaerts erhalten, ohne die
Fachkomponente vom Angular-Router abhaengig zu machen. Laenderauswahl,
Formularlogik und fachliche Darstellung bleiben in Lit.
Die Laenderauswahl wird aus `ism/countries.json` des ausgewaehlten Profils geladen.
Fehlerhafte oder fehlende Konfiguration zeigt einen Ladefehler, keine Ersatzlaender.
Echte Laender verwenden standardmaessig Emoji-Flaggen mit automatischem
Rueckfall auf lokale flag-icons-SVGs. Eine Checkbox wird nicht angezeigt.
Fiktive Laender zeigen immer ihre konfigurierten generierten Flaggen.
Alle Flaggen sind dekorativ. Der ausgeschriebene Name bleibt die barrierefreie Beschriftung.

Configure flag display in `src/app/webapp-settings.ts`:

```typescript
export const webappSettings = {
  flagDisplay: 'auto',
};
```

`auto` prefers emoji flags when a canvas measurement detects a combined flag
glyph rather than separate regional letters. Otherwise it uses the local SVG.
Browsers expose no definitive flag emoji API, so this detection is a heuristic.
Use `svg` to force images on platforms where detection is inaccurate, or
`emoji` to explicitly force emoji rendering. Changes require rebuilding the
application. Fictional countries always use images, regardless of this setting.

For standalone integration, the equivalent attribute is `flag-display="auto"`,
`flag-display="svg"` or `flag-display="emoji"`.
Configure real countries through the selected dataset's country
list using their uppercase ISO codes and display names. Real countries omit a
custom `flag` entry when using the conventional `flags/{code}.svg` fallback,
or specify the generated fallback image path explicitly. The corresponding
SVGs and their MIT license must be included in that dataset. Fictional countries
provide an explicit image path instead of constructing unsupported emoji codes.
Das gematik-Logo unter `public\Gematik_Logo_Flag.png` erscheint oben links im Header.
Der weisse Header mit Schatten enthaelt rechts Menue und Suchsymbol.
Das Suchsymbol oeffnet die Zwischenseite der Patientensuche.
Der hellgraue Footer zeigt Copyright und Demonstratorhinweise linksbuendig.
Im Header verlinkt das Logo auf die Startseite. Alle Bilder werden lokal
ausgeliefert, ohne externe Bilddienste. Zusaetzliche Flaggen erweitern die
Laenderauswahl nicht automatisch.

## Vorlaeufiges Screenshot-Design

Die Darstellung orientiert sich an den bereitgestellten Desktop- und
Mobil-Screenshots. Sie ist eine vorlaeufige Umsetzung ohne abschliessende
UX-Spezifikation. Dunkelblau, Gruen, weisse Flaechen und der helle Footer
ersetzen das bisherige Farblayout.

Farben, Schriftfamilie und Inhaltsbreite sind als `--portal-*` Variablen in
`src\styles.scss` zentral anpassbar. Die Lit-Komponenten verwenden gemeinsame
Basisstile aus `ism-styles.ts` und entsprechende Fallbacks ohne Angular-Host.
Es werden keine externen Schriftarten oder Icons geladen.
Bis zur Bereitstellung der Hausschrift bleibt die Systemschrift aktiv.
Das vorhandene gematik-Logo wird unveraendert verwendet. Das separate
runde Footer-Logo aus dem Screenshot liegt noch nicht als freigegebenes Asset vor.

Ab 40rem stehen Titel und Untertitel oberhalb des Suchbereichs.
Auf schmaleren Bildschirmen steht die kompakte Patientensuche im Vordergrund,
mit Zurueck-Navigation darueber. Formularfelder sind mindestens 3.5rem hoch,
Buttons mindestens 2.75rem. Fokusmarkierungen und sichtbare Fehlermeldungen
bleiben erhalten. Deaktivierte Buttons haben fuer bessere Lesbarkeit
dunkle Beschriftungen statt der weissen Schrift aus dem Screenshot.
Formatangaben stehen in aufklappbaren i-Hinweisen neben dem Feldnamen.
Escape schliesst den Hinweis und fokussiert den Schalter.
Originalbeschreibungen bleiben sichtbar. Es werden
keine Beispielkennungen oder Platzhalter aus Screenshots fuer andere Laender erfunden.
Ein Datenschutzlink benoetigt weiterhin die fachlich freigegebene Zieladresse.
Menue, Suche, Direktlinks und Demonstratorverhalten bleiben funktionsfaehig.

Real country fallback flags come from `lipis/flag-icons` version 7.5.0
(4:3 variants). The internal dataset retains their MIT notices and provenance.
Public fictional flag images are independently generated and are not flag-icons assets.

The MyHealth@EU footer logo and browser tab icon are excluded pending rights
clarification. Both image files have been removed from the current tree.
Their removal does not clear earlier Git history or existing build artifacts.

`<ism-patient-search model-url="ism/PL.json">` laedt das beim Build erzeugte Modell als
statische Ressource und zeigt alle Eingabefelder der Patientensuche mit englischer und
originaler Beschreibung, Pflichtmarkierung und Formathinweis. Die Eingabe wird beim
Tippen gegen das ISM-Format (Regex, ganzer Wert) geprueft. Felder ohne Format werden
nicht geprueft. Fehlende Pflichtangaben werden gemeldet. Vorhandene Hilfsmedien
werden ueber einen i-Button ein- und ausgeblendet. Ohne Hilfsmedien fehlt der Button.
Unter den Suchparametern muss die Uebergabe der Datenschutzinformationen
bestaetigt werden. Die Bestaetigung wird nicht gespeichert. Ein Dokumentlink
ist mangels bereitgestellter Zieladresse noch nicht eingebunden.
„Patient suchen“ wird erst bei gueltigen aktiven Feldern, ausgewaehlten
Suchverfahren und gesetzter Checkbox aktiviert. Die Komponente sendet nichts
ab und zeigt stattdessen einen ausdruecklichen Demonstratorhinweis.
Ein Laenderwechsel setzt Eingaben, Hilfe und Bestaetigung zurueck.
Ein Ladefehler wird angezeigt.

Der Angular-Host aktiviert `CUSTOM_ELEMENTS_SCHEMA` nur fuer diese Einbindung; die globale`nAngular-Templatepruefung bleibt erhalten. Weitere Komponenten legen Elementname, Attribute`nund Ereignisse selbst fest.

## ISM-Generierung

### Browserabnahme der Integration

Nach `npm start` auf der Startseite die Patientensuche per Kachel und alternativ
per Header-Link oeffnen. Auf `/patientensuche` die Patientensuche starten,
anschliessend ein fiktives Land auswaehlen.
Fuer Caldoria wird `XC000001` akzeptiert, ein abweichendes Format meldet
einen Formatfehler. Nach Eingabe und anschliessendem Leeren erscheint ein
Pflichtfeldfehler. Tab und Shift+Tab muessen das Feld erreichbar machen.
Bei kleinem Viewport scrollt nur der Inhalt zwischen Header und Footer.
Enter darf keine Suchanfrage ausloesen.
Die Hilfe ueber den i-Button oeffnen und wieder schliessen.
Die Suche bleibt ohne Datenschutzbestaetigung deaktiviert.
Nach Bestaetigung zeigt „Patient suchen“ nur den Demonstratorhinweis.
Ein Laenderwechsel setzt die Bestaetigung zurueck.
„Zurueck“ und „Abbrechen“ fuehren zur Zwischenseite.

In den Browser-Netzwerkwerkzeugen pruefen, dass nur die statischen ISM-Ressourcen
geladen werden. Einen fehlgeschlagenen Abruf von `ism/XC.json` simulieren:
Die Komponente muss einen sichtbaren Ladefehler statt eines leeren Formulars zeigen.
Ungueltige Modellmetadaten werden ebenfalls als Ladefehler angezeigt.

`npm run ism:generate` erzeugt ausschliesslich das oeffentliche Profil.
`npm run ism:generate:internal` erzeugt das interne Profil.
Die Ausgabe liegt jeweils im eigenen `generated`-Verzeichnis und enthaelt
Anzeigemodelle, Hilfsmedien, Flaggen, Laenderkonfiguration und ein Manifest mit Hashes.
`npm start` und `npm run build` fuehren die oeffentliche Generierung vorab aus.
Interne Start-/Buildbefehle generieren ausschliesslich das interne Profil.
Der Browser ruft keine ISM-Schnittstelle auf.

26 Quellen sind auf den eigentlichen ISM-Block ab
`<searchFields xmlns="http://ec.europa.eu/sante/ehncp/ism">` reduziert.
Die enthaltenen Feldregeln und Medien bleiben erhalten. CH und FR behalten
ihre urspruengliche Struktur als negative Referenzen, da ein Herausschneiden
ihres verschachtelten `searchFields` den Landcode verlieren wuerde.
Der aktuelle Bestand umfasst 28 Dateien ohne DE und EU. Die Einzelbefunde zu
Profilen, Feldgruppen, Regeln, Medien und Generatorunterstuetzung stehen im
`MILESTONE-PLAN.md` unter F4a. Generierung, XSD-Konformitaet und Browserabnahme
werden dort getrennt bewertet.

Das interne Profil verwendet den Diagnosemodus. Nicht unterstuetzte
Masken erzeugen dabei ein Fehlerartefakt statt eines Formularmodells und werden
im Manifest als `unavailable` gekennzeichnet. Diese Fehler werden im Terminal
gemeldet und bei Anzeige der Maske sichtbar ausgegeben. Ohne diesen Parameter
bleibt der direkte Skriptaufruf strikt und bricht bei Profilfehlern ab.
Ungueltiges XML ohne zuordenbares Land und widerspruechliche Quellen fuer dasselbe
Land verhindern auch im Diagnosemodus die Ausgabe. Identische Quellen wie
`el.xml` und `gr.xml` werden mit Warnung zu einem Land zusammengefasst.

Das Modell enthaelt je Eingabefeld Domain, Label, englische und originale
Beschreibung, Pflichtangabe und `format` als Regex. Fehlt `format`, bleibt das Muster
leer; es wird keine Regel geraten. Medien (z. B. ein Ausweisbeispiel) werden als
Hilfen referenziert. `documentSearch` wird nicht verarbeitet.
Mehrere NORMAL-Felder erscheinen in Quellreihenfolge, auch ueber mehrere
identifier-Gruppen hinweg. Ihre lokale Identitaet ist die Feldposition im
Modell, nicht die Domain oder das Label. Gleiche Domains teilen daher weder
Werte noch Fehlerzustaende oder DOM-IDs. Ein Maskenwechsel leert alle Eingaben.

Unterstuetzt ist `patientSearch` mit `identifier` vom Typ `NORMAL` oder `CHOICE`
und optionalem `media`. CHOICE-Alternativen aus `ids` behalten ihren `display`-Text
und verweisen im optionalen `choiceGroups` auf ihre Feldpositionen.
Jede Gruppe erfordert eine bewusste Auswahl ohne Vorauswahl. Nur aktive
Alternativen werden angezeigt und validiert. Eingaben und Fehlerzustaende
bleiben beim Wechsel erhalten, beim Maskenwechsel werden sie geloescht.
Weitere Elemente, ungueltiges Base64, ein
nicht als Browser-Muster nutzbares `format` oder mehrfach gelieferte Laender
brechen im strikten Modus die Generierung ab; dann wird nichts geschrieben.
Weicht die deklarierte Bildendung vom erkannten JPEG-/PNG-Inhalt ab, meldet der
Generator `MEDIA_TYPE_MISMATCH` und verwendet den erkannten Typ. Die griechische
Quelle deklariert PNG, enthaelt aber JPEG; die XML-Quelle bleibt unveraendert.

Quelle und Ausgabeziel sind Parameter (`--source`, `--out`). Lokal und in einer
Pipeline laeuft dasselbe Skript. Die Ausgabe ist deterministisch und steht in
`.gitignore`. Interne Ausgaben duerfen nicht ins oeffentliche Repository gelangen.
Der Abruf ueber `GET /ismlist` des HTTP-Proxys ist als
weitere Quelle vorgesehen (`tools\ism\sources.mjs`); der FHIR-Bundle-Aufbau ist noch
nicht festgelegt.

```powershell
npm --prefix frontend run ism:generate
npm --prefix frontend run test:ism
```
