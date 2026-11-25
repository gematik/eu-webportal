# OpenAPI/Arazzo Mocking Test Tool

Lokales Python-CLI-Tool zur Validierung von OpenAPI-3.1.x-Spezifikationen und
Arazzo-1.1.x-Workflows sowie zur Cross-Validation zwischen beiden. Details zu
Architektur, Scope und Milestones stehen in `docs/implementation-plan.md`.

## Voraussetzungen

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- Abhängigkeiten aus `pyproject.toml` (`PyYAML`, `jsonschema`)

Installation aus dem Repository-Root:

```powershell
uv sync --locked
```

## Aufruf

```powershell
uv run python -m tools.openapi_arazzo_tool.cli <command> --config <pfad-zur-config>
```

Ohne `--config` wird `tool.yaml` im aktuellen Verzeichnis erwartet.

### Verfügbare Befehle

| Befehl | Status |
|---|---|
| `validate-openapi` | implementiert |
| `validate-arazzo` | implementiert |
| `validate-all` | implementiert (OpenAPI + Arazzo + Cross-Validation) |
| `generate-mocks` | implementiert (versioniertes Mock-Paketverzeichnis) |
| `start-mocks` | implementiert (direkte Konfiguration oder Paketverzeichnis) |
| `stop-mocks` | implementiert (dokumentiert das Prozessmodell) |
| `list-workflows` | implementiert |
| `run-workflow` | implementiert |
| `run-tests` | implementiert |
| `report` | implementiert |
| `explain` | noch nicht implementiert |

Nicht implementierte Befehle scheitern explizit mit `COMMAND_NOT_IMPLEMENTED`
und Exit-Code ungleich `0` — sie melden niemals stillschweigend Erfolg.

## Konfiguration

Die Konfiguration ist eine YAML-Datei mit folgenden Schlüsseln:

```yaml
openapi:
  - <pfad-zu-openapi-dokument-1>.yaml
  - <pfad-zu-openapi-dokument-2>.yaml

arazzo:
  - <pfad-zu-arazzo-workflow>.yaml

security:
  allowedRefRoots:
    - <erlaubtes-root-verzeichnis-fuer-lokale-$ref-und-sourceDescriptions>
```

`security.allowedRefRoots` ist verpflichtend, sobald `$ref` oder Arazzo
`sourceDescriptions` aufgelöst werden sollen. Es legt fest, innerhalb welcher
Verzeichnisse lokale Referenzen liegen dürfen (siehe `docs/adr/ADR-0009-ref-resolution-strategy.md`).
Remote-Referenzen, absolute Pfade und Pfad-Traversal außerhalb der erlaubten
Roots werden abgelehnt.

## Beispielnutzung: Validierung eines lokalen `api-ncpeh`-Standes

Dieses Beispiel validiert einen lokal ausgecheckten Stand von `api-ncpeh`
gegen den ISM-Bereitstellungs-Workflow, so wie es in einem echten Probelauf
gegen das Sibling-Repository `../api-ncpeh` durchgeführt wurde.

### 1. `api-ncpeh` auschecken (optional: bestimmter Tag)

```powershell
Set-Location ..\api-ncpeh
git fetch --tags
git checkout <TAG>
Set-Location ..\eu-webportal
```

### 2. Temporäre Konfiguration anlegen

```powershell
@'
openapi:
  - ../api-ncpeh/src/interfaces/ncpeh-proxy/http-proxy/I_ISM_Service.yaml
  - ../api-ncpeh/src/interfaces/ncpeh-proxy/http-proxy/I_HTTP-Proxy_basic.yaml
  - ../api-ncpeh/src/interfaces/ncpeh-fd/I_ISM_Service_FD.yaml
arazzo:
  - ../api-ncpeh/src/workflows/wf-ism-bereitstellen.yaml
security:
  allowedRefRoots:
    - ../api-ncpeh
'@ | Set-Content tools\local-api-ncpeh-probe.yaml
```

Pfade sind relativ zum Repository-Root (`eu-webportal`) anzugeben.

### 3. Durchlauf starten

```powershell
uv run python -m tools.openapi_arazzo_tool.cli validate-all --config tools\local-api-ncpeh-probe.yaml
```

Erwartete Ausgabe bei einem validen Stand:

```text
OK ..\api-ncpeh\src\interfaces\ncpeh-proxy\http-proxy\I_ISM_Service.yaml (OpenAPI 3.1.0)
OK ..\api-ncpeh\src\interfaces\ncpeh-proxy\http-proxy\I_HTTP-Proxy_basic.yaml (OpenAPI 3.1.0)
OK ..\api-ncpeh\src\interfaces\ncpeh-fd\I_ISM_Service_FD.yaml (OpenAPI 3.1.0)
OK ..\api-ncpeh\src\workflows\wf-ism-bereitstellen.yaml (Arazzo 1.1.0)
```

`validate-all` prüft in dieser Reihenfolge:

1. jedes konfigurierte OpenAPI-Dokument (Version, Struktur, `$ref`,
   Parameter, Request Bodies, Responses, Security, Examples),
2. jedes konfigurierte Arazzo-Dokument (Struktur, Workflows/Steps, Inputs,
   Outputs, Actions, Dependencies, Control-Flow),
3. Cross-Validation: Auflösung der Arazzo `sourceDescriptions` gegen die
   OpenAPI-Dokumente, `operationId`/`operationPath`-Auflösung, Parameter- und
   Request-Body-Kompatibilität sowie statische Response-Status-, Header- und
   Body-Schema-Referenzen. Security-Definitionen werden strukturell geprüft,
   aber nicht auf Ausführbarkeit durch den Workflow-Runner. Auch mTLS-only
   Operationen sind daher statisch validierbar. Runtime-Expression-Abhängigkeiten werden
   gegen deklarierte Workflow-Inputs, Outputs, Steps und Workflows aufgelöst.

Diese Trennung implementiert keine mTLS-Unterstützung. Bei tatsächlicher
Workflow-Ausführung bleiben die Authentisierungsprüfungen aktiv; nicht
unterstützte Anforderungen werden nicht stillschweigend umgangen.

Fehler werden nach `stderr` ausgegeben und führen zu einem Exit-Code ungleich
`0`; das Kommando bricht nicht beim ersten Fehler ab, sondern sammelt alle
gefundenen Probleme pro Dokument.

### 4. Temporäre Konfiguration entfernen

```powershell
Remove-Item tools\local-api-ncpeh-probe.yaml
```

## Einzelne Validierungsschritte

Nur OpenAPI validieren:

```powershell
uv run python -m tools.openapi_arazzo_tool.cli validate-openapi --config tools\local-api-ncpeh-probe.yaml
```

Nur Arazzo validieren (ohne Cross-Validation gegen OpenAPI):

```powershell
uv run python -m tools.openapi_arazzo_tool.cli validate-arazzo --config tools\local-api-ncpeh-probe.yaml
```

## Tests ausführen

Vom Repository-Root aus:

```powershell
uv run python -m unittest discover -s tests
```

Workflows können aufgelistet und direkt ausgeführt werden:

```powershell
tool list-workflows --config .\tool.yaml
tool run-workflow create-widget --input 'locale="de-DE"' --config .\tool.yaml
```

Für die Ausführung müssen `network.allowedHosts` und
`network.allowedPorts` explizit gesetzt sein. `timeouts.request` und
`timeouts.workflow` akzeptieren Werte wie `500ms`, `5s` oder `1m`.
Requests und Responses werden standardmäßig gegen OpenAPI validiert. Dies
kann über `tests.validateRequests` beziehungsweise `tests.validateResponses`
gezielt deaktiviert werden.

Mock-Paket wird deterministisch generiert. `mock.packageVersion` muss eine
SemVer-Version enthalten; `--output` überschreibt den Standardpfad
`dist/mock-<packageVersion>`. Existierende Paketverzeichnisse werden nicht
überschrieben. Der Export prüft Antworten gegen ihren Vertrag und lädt das
fertige Paket zur Integritätsprüfung aus einem temporären Verzeichnis.
Erst danach wird es veröffentlicht; fehlerhafte Exporte hinterlassen kein
freigegebenes Paket:

```powershell
tool generate-mocks --config .\tool.yaml --output .\dist\mock-1.0.0
tool start-mocks --package-dir .\dist\mock-1.0.0
```

Das Paket enthält `runtime/routes.json`, vorgebündelte
`runtime/contracts/openapi-*.json`, vollständige Quellkopien unter
`sources/openapi/` und `sources/arazzo/` sowie `manifest.json` mit getrennten
Paket-/Generatorversionen und SHA-256-Prüfsummen. Zur Paketerzeugung
konfigurierte Szenarien und Beispiele werden festgelegt. Zur Laufzeit werden
die OpenAPI-/Arazzo-Quellen nicht erneut ausgewertet.

Das Quellenarchiv umfasst auch transitiv referenzierte lokale Dateien und
OpenAPI-Quellen aus Arazzo-`sourceDescriptions`. Es werden ausschließlich
referenzierte Dateien innerhalb erlaubter Roots kopiert, keine vollständigen
Verzeichnisbäume. Originalbytes bleiben erhalten. `sourceReferences` im
Manifest ordnet ursprüngliche Referenzen und JSON-Positionen den nummerierten
Quellkopien zu, auch bei identischen Dateinamen. Die Kopien sind ein
Nachschlagearchiv; ihre ursprünglichen relativen Pfade werden nicht als
Dateibaum rekonstruiert. Der Server nutzt ausschließlich gebündelte
Laufzeitverträge.

Ein Szenario wird über `mock.scenario` aus der Top-Level-Map `scenarios`
gewählt. `mock.examples` kann Example-Namen je `operationId` festlegen.
Generator-Eingaben und Laufzeit-Netzwerkeinstellungen sind getrennt zu
konfigurieren.

Paket lokal starten:

```powershell
tool start-mocks --package-dir .\dist\mock-1.0.0
tool start-mocks --package-dir .\dist\mock-1.0.0 --port 9090
```

Alternativ startet `just start-mock-package .\dist\mock-1.0.0 --port 9090`
dasselbe Paket mit den angegebenen Laufzeitoptionen.

Der Standard bindet an `127.0.0.1:8080`. `--bind-host` und `--port` überschreiben
Laufzeitwerte; Request-Prüfung bleibt aktiv und verwendet die im Paket
enthaltenen Vertragsdaten. Paketmanifest, Dateien, Prüfsummen und unterstützte
Versionen werden vor dem Binden validiert. Die Quelldefinitionen werden dabei
nicht geparst oder neu ausgewertet.

### Mock mit Postman oder curl nutzen

Der Mockserver ist ein normaler HTTP-Server auf Loopback und kann direkt von
jedem Client angesprochen werden. Minimale Konfiguration:

```yaml
openapi:
  - ../api-ncpeh/src/interfaces/ncpeh-proxy/http-proxy/I_ISM_Service.yaml

security:
  allowedRefRoots:
    - ../api-ncpeh

mock:
  packageVersion: 1.0.0
```

```powershell
# Paket aus Spezifikation und ausgewählten Antworten erstellen
uv run python -m tools.openapi_arazzo_tool.cli generate-mocks --config .\tool.yaml --output .\dist\mock-1.0.0

# Paket starten (Vordergrund, Ctrl+C beendet ihn)
uv run python -m tools.openapi_arazzo_tool.cli start-mocks --package-dir .\dist\mock-1.0.0
```

Der bisherige direkte Start aus der Konfiguration bleibt für Entwicklung
verfügbar und erzeugt Routen beim Start erneut:

```powershell
uv run python -m tools.openapi_arazzo_tool.cli start-mocks --config .\tool.yaml
```

In Postman als Basis-URL `http://127.0.0.1:8080` eintragen. Beispielantwort:

```powershell
curl.exe -i "http://127.0.0.1:8080/assets/flags?countryCodes=DE"
# HTTP/1.0 200 OK
# {"CountryFlag":[{"CountryCode":"AA","Flag":"mock-0"}]}
```

Eingehende Requests werden gegen OpenAPI validiert. Ein fehlender Pflicht-
parameter liefert daher bewusst `400` statt einer Erfolgsantwort:

```json
{"code":"OPENAPI_REQUEST_CONTRACT_VIOLATION",
 "message":"Required parameter 'countryCodes' in 'query' is missing."}
```

Unbekannte Pfade liefern `404`. Diese Prüfung lässt sich über
`tests.validateRequests: false` abschalten.

Hinweise:

* Jede gemockte Operation benötigt eine `operationId`.
* Dateiübergreifende `$ref` werden vor der Generierung gebündelt; alle
  Zieldateien müssen innerhalb von `security.allowedRefRoots` liegen.
* Ohne Example wird der Wert aus dem Schema erzeugt. `format` und `pattern`
  werden dabei berücksichtigt (unterstützte Regex-Teilmenge: Anker, Literale,
  `.`, Escapes, Zeichenklassen mit Bereichen, Gruppen, Alternation sowie `?`,
  `*`, `+`, `{n}`, `{n,m}`). Nicht unterstützte Patterns scheitern explizit
  mit `MOCK_GENERATION_FAILED` und verlangen ein Example.
* Generierte Antworten werden gegen den eigenen Contract validiert; der Mock
  kann also nichts ausliefern, was die Spezifikation verletzt.
* Das Docker-Compose-Setup exponiert bewusst keine Ports. Für den Zugriff von
  außerhalb des Containers muss ein Port explizit freigegeben werden.

`tool run-tests --config .\tool.yaml` führt YAML-/JSON-Dateien unter
`tests.path` alphabetisch und sequenziell aus. Jede Datei nennt `workflow`,
optional `inputs` und `mockScenario` (Operation-ID auf einen Namen aus
`scenarios`), sowie `expect.workflow` (`success` oder `failure`) und
optional `expect.step`/`expect.status`. Jeder Lauf erhält einen eigenen
Loopback-Mockserver. Dafür muss `mock.bindHost` explizit `127.0.0.1` oder
`::1` sein; `mock.port: 0` wählt einen freien Port. `tests.failFast: true`
stoppt nach dem ersten Fehltest. `environment`-Overrides werden abgelehnt.
Ein explizites 401-Mock-Szenario kann Authentifizierungsfehler ohne
Credentials gegen den lokalen Loopback-Server prüfen; reale Workflow-Ziele
erhalten diese Ausnahme nicht.

`tool report --config .\tool.yaml` führt konfigurierte Szenarien erneut aus
und erzeugt die unter `report.formats` ausgewählten Formate `console`, `json`,
`junit` und optional `html`. Für Datei-Artefakte muss `report.path` gesetzt
sein; erzeugt werden `report.json`, `report.xml` und `report.html`.
`run-tests` verwendet dieselben Report-Einstellungen. Ohne Report-Konfiguration
bleibt dessen kompakte JSON-Ausgabe erhalten.

Docker baut das CLI aus dem Repository-Root:

```powershell
docker compose build tool
docker compose run --rm tool validate-all --config /workspace/config/tool.yaml
```

`docker-compose.yml` mountet Specs (`SPECS_PATH`, Standard `./specs`),
Workflows (`/workspace/workflows`), Tests (`TESTS_PATH`, Standard `./tests`),
Beispiele (`EXAMPLES_PATH`, Standard `./tests/fixtures`) und `tools/` nur lesbar.
Die Tool-Konfiguration liegt im Container unter `/workspace/config/`.
Nur `/workspace/reports` ist schreibbar; dieser Ordner muss für UID `10001`
beschreibbar sein. Der Mock-Server bleibt innerhalb des Containers an
Loopback gebunden und wird nicht öffentlich exponiert.

Ein unveränderliches Mock-Serverimage pro Paketversion wird separat mit
`Dockerfile.mock` erstellt. Das Paket muss im Build-Kontext liegen:

```powershell
just docker-build-mock .\dist\mock-1.0.0 1.0.0
docker run --rm --read-only --tmpfs /tmp euwp-mock:1.0.0
```

Das Image startet standardmäßig mit dem Paket unter `/opt/mock-package` und
bindet innerhalb des Containers an Loopback. Für Hostzugriff Port explizit
veröffentlichen und Laufzeitadresse überschreiben:

```powershell
docker run --rm --read-only --tmpfs /tmp -p 127.0.0.1:8080:8080 euwp-mock:1.0.0 start-mocks --package-dir /opt/mock-package --bind-host 0.0.0.0 --port 8080
```

`Ctrl+C` und `docker stop` schließen den Server sauber. SIGTERM wird im
Vordergrundprozess verarbeitet; Container müssen nicht per SIGKILL beendet
werden. Startmeldungen erscheinen auch ohne interaktives Terminal sofort
in `docker logs`.

Ein vollständiger, ohne externe Spezifikationen nutzbarer Demolauf steht in
[`mock-verarbeitungsablauf.md`](../../docs/architecture/mock-verarbeitungsablauf.md#reproduzierbarer-demolauf).

### Rezepte mit `just`

Das Justfile liegt im Repository-Root und bildet alle implementierten
Kommandos ab. `just` sucht aufwärts, der Aufruf funktioniert daher aus dem
Root und aus jedem Unterverzeichnis:

```powershell
just                        # Rezepte auflisten
just validate .\tool.yaml
just generate-mocks .\tool.yaml
just start-mocks .\tool.yaml
just unit                   # Unit-Tests
just docker-build
```

Der `config`-Parameter ist überall optional und fällt auf `tool.yaml` zurück.
Argumente werden positionell übergeben — `just validate my.yaml`, nicht
`just validate config=my.yaml`. `explain` ist bewusst nicht als Rezept
hinterlegt, solange das Kommando nicht implementiert ist.

Für taggebundene CI-Läufe checkt die JSL-Automation `api-ncpeh` authentifiziert
aus. Anschließend prüft das Tool ausschließlich den vorhandenen Checkout:

```powershell
python -m tools.openapi_arazzo_tool.integration --checkout <checkout> --repository-url <url> --tag <git-tag> --config <tool.yaml>
```

Das `tool.yaml` muss nur Spec-Dateien innerhalb des Checkouts aufführen und
`security.allowedRefRoots` exakt auf den Checkout begrenzen. Origin-URL, Tag,
sauberer Worktree und Commit-SHA werden geprüft; Secrets für den Git-Zugang
verbleiben bei der JSL-Automation.

Credentials für `run-workflow` werden ausschließlich aus Environment-Variablen
geladen. Jede Credential-Konfiguration (z. B. `auth.schemes.<schemeName>` oder
`auth.bearerToken`) benötigt `env`, `workflowIds`, `origins`, `methods` und
`paths` und `workflowSha256` (SHA-256 der unveränderten Arazzo-Datei).
Basic Auth benötigt zusätzlich `username`; `env` enthält das Passwort.
Beispiel: `auth.schemes.token: {env: TEST_TOKEN, workflowIds: [find-widget],
origins: [https://api.example.org], methods: [GET], paths: [/widgets/{id}],
workflowSha256: <SHA-256-Fingerprint>}`.
Untrusted Szenarioläufe erhalten keine Secrets. Bei credentialierten Requests
sind Redirects gesperrt. Secrets werden in Outputs und Fehlern maskiert.

## Bekannte Grenzen (V1)

- Nur OpenAPI 3.1.x und Arazzo 1.1.x werden unterstützt; andere Versionen
  scheitern explizit.
- Nur lokale, relative `$ref`- und `sourceDescriptions`-Pfade werden
  unterstützt; Remote-Referenzen sind deaktiviert.
- Runtime Expressions werden mit einer strikt erlaubten Arazzo-1.1-Grammatik
  syntaktisch geprüft. Vollständige und eingebettete Expressions können über
  einen expliziten `RuntimeContext` sicher ausgewertet werden; native Typen,
  RFC-6901-JSON-Pointer und deterministische JSON-Einbettung werden unterstützt.
  Ein sicherer Parser wertet `simple` Criteria mit Vergleichen, `&&`, `||`,
  Klammern und Literalen aus. Criterion-Context, Regex-, JSONPath-, XPath- und
  Expression-Type-Criteria sind außerhalb der V1-Supportmatrix und scheitern
  explizit mit `ARAZZO_FEATURE_UNSUPPORTED`. Workflow-Runner-Integration folgt
  in Milestone 7. Dynamische Codeauswertung wird nicht verwendet.
- Security Requirements werden mit OR-/AND-Semantik geprüft und Credentials
  ausschließlich nach expliziter Vertrauensbindung injiziert.
- Ein OpenAPI-3.1-Parameter-Serializer unterstützt Pfad-, Query-, Header- und
  Cookie-Parameter inklusive `style`, `explode`, `allowReserved`,
  `deepObject` und RFC-konformer Prozentkodierung. Request Bodies unterstützen
  deterministisches JSON, `application/x-www-form-urlencoded`,
  `multipart/form-data`, Binärdaten sowie Text/XML. Ein transportneutraler
  Request-Assembler kombiniert Base-URL, Pfad, Query, Header, Cookies und Body
  deterministisch und lehnt Header-Injection sowie Konflikte ab.
- Unbekannte Arazzo-Felder werden abgelehnt. Bekannte, aber in V1 nicht
  unterstützte Felder erzeugen `ARAZZO_FEATURE_UNSUPPORTED`; `x-*` Extensions
  bleiben erlaubt und werden nicht semantisch ausgewertet.
- Sichere HTTP-Ausführung verwendet `httpx` mit expliziten Host-/Port-
  Allowlists, DNS/IP-Prüfung, Redirect-Revalidierung, Timeouts und maximaler
  Response-Größe. Private Adressen sind standardmäßig blockiert und müssen für
  lokale Tests ausdrücklich erlaubt werden.
