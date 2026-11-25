# ADR-0009 $ref- und sourceDescriptions-Auflösung im Mocking-/Test-Tool

## Status

Accepted

## Datum

2026-09-18

## Kontext

Das in `tools/openapi_arazzo_tool/` entstehende CLI-Tool (siehe
`docs/openapi-arazzo-mocking-test-tool-requirements.md`) muss OpenAPI-`$ref`
und Arazzo-`sourceDescriptions` lokal auflösen (Kap. 7.1, 7.3, 17).

Die Upstream-Spezifikationen aus `api-ncpeh` wurden kürzlich auf tief
verschachtelte relative Pfade umgestellt, z. B.

```
../../../domain/domainobj-eped-b.yaml
```

statt vormals flacher Pfade wie `./domainobj-eped-b.yaml`.

Für den bestehenden Specmatic-PoC (`tools/legacy/collect-specs.mjs`) wurde
dafür ein "virtuelles Arbeitsverzeichnis" eingeführt: Alle referenzierten
Dateien werden anhand ihres Basisnamens in ein flaches Verzeichnis kopiert,
`$ref`- und `url`-Werte werden dabei automatisiert umgeschrieben. Hintergrund
laut Architektur: Specmatics eigene Tooling-Erwartung an eine flache
Verzeichnisstruktur, verbunden mit dem Wunsch, bei künftigen
Repository-Restrukturierungen in `api-ncpeh` nicht manuell jede relative
Referenz nachziehen zu müssen.

Für das neue OpenAPI/Arazzo-Tool stellt sich dieselbe Frage erneut: Soll das
Tool ebenfalls auf einer geflachten Kopie arbeiten, oder direkt auf der
Originalstruktur?

## Entscheidung

Das Tool löst `$ref` und `sourceDescriptions.url` **direkt gegen die reale,
verschachtelte Verzeichnisstruktur** auf. Es wird keine Flatten-Kopie für die
eigene Validierung, Cross-Validation oder Mock-Generierung benötigt oder
erzeugt.

Konkret:

- Pfade werden relativ zum Verzeichnis der referenzierenden Datei aufgelöst
  (`dirname(datei)` + relativer Pfad), unabhängig von der Verschachtelungstiefe.
- Nach der Auflösung wird kanonisiert (`resolve` + `realpath`) und gegen die
  konfigurierten, erlaubten Root-Verzeichnisse geprüft (Sicherheitsanforderung
  aus Kap. 17: keine Pfad-Traversal aus dem erlaubten Root heraus, keine
  Symlinks, die aus dem Root herausführen).
- Diagnosen (Fehlercode, Datei, JSON-Pointer, ggf. Zeile/Spalte) referenzieren
  die reale Quelldatei, nicht eine Kopie.
- Für hermetische Unit-Tests werden kleine, im Repository gepflegte Fixtures
  mit echter Mehrebenen-Verschachtelung verwendet
  (`tests/fixtures/openapi/...`), die das reale Muster aus `api-ncpeh`
  nachbilden. Diese Fixtures hängen nicht von einem Checkout von `api-ncpeh`
  ab und sind damit CI-fähig und deterministisch.
- Für echte Integrationstests wird das `api-ncpeh`-Repository aus GitHub
  ausgecheckt. Der Repository-URL und der zu verwendende Git-Tag werden beim
  Start des jeweiligen Runs angegeben.
- Der authentifizierte Zugriff auf GitHub erfolgt über den vorgesehenen
  Automatisierungsmechanismus der JSL. Das Tool selbst verwaltet keine
  Zugangsdaten und implementiert keinen eigenen Authentifizierungsmechanismus
  für den Repository-Checkout.
- Der Checkout auf Basis eines unveränderlichen Git-Tags stellt die
  reproduzierbare Bezugsquelle für Integrationstests bereit. Die hermetischen
  Unit-Tests bleiben davon unabhängig.

`tools/legacy/collect-specs.mjs` war ein eigenständiger, Specmatic-spezifischer
Adapter und war kein Vorbild für die `$ref`-Auflösung des OpenAPI/Arazzo-Tools.
Der Specmatic-PoC wurde am 2026-09-23 nicht weiterverfolgt; das Skript,
`specs/upstream/` und die daraus abgeleiteten Mock-Szenario-Fixtures
(`mocks/scenarios/...`) wurden entfernt. Diese Entscheidung berührt die
`$ref`-Auflösungsstrategie des neuen Tools nicht, da dafür ohnehin nie Bedarf
an dieser Kopie bestand.

## Begründung

- Kanonisierung und Root-Allowlisting sind ohnehin verpflichtend
  (Sicherheitsanforderung). Verschachtelte relative Pfade sind dabei kein
  Mehraufwand: `Path.resolve()`/`realpath()` behandelt beliebige
  `../`-Tiefe korrekt.
- Ein zusätzlicher Flatten-Schritt wäre eine weitere Pipeline-Stufe mit
  eigenem Fehlerpotenzial (Basisnamen-Kollisionen, Refs werden umgeschrieben,
  Kopie weicht vom Original ab).
- Flatten verschlechtert die Nachvollziehbarkeit: Fehlermeldungen und
  Source-Locations (Requirement 7.1) sollen auf die echte Datei zeigen, nicht
  auf eine automatisch erzeugte Kopie.
- Das eigentliche Problem hinter Olivers Vorschlag – manuelles Nachziehen von
  relativen Pfaden bei Restrukturierung – entsteht nur bei manueller Pflege
  einer Kopie. Bei automatisierter, direkter Auflösung entfällt dieses
  Problem vollständig, ohne dass geflacht werden muss.

## Konsequenzen

### Positiv

- Kein zusätzlicher Build-/Ingest-Schritt für das OpenAPI/Arazzo-Tool nötig.
- Bessere Diagnosequalität (reale Dateipfade in Fehlermeldungen).
- Keine Basisnamen-Kollisionsgefahr.
- Hermetische Unit-Tests bleiben unabhängig vom `api-ncpeh`-Checkout.
- Integrationstests können reproduzierbar gegen den beim Run ausgewählten
  Git-Tag ausgeführt werden.

### Negativ

- Der `$ref`-Resolver muss Root-Allowlisting und Kanonisierung von Anfang an
  korrekt implementieren (kein triviales "einfach Datei lesen").
- Milestone 13 stellt einen plattformneutralen Einstieg bereit, der den durch
  JSL authentifiziert ausgecheckten Stand gegen Origin-URL, Git-Tag, Commit
  und sauberen Worktree prüft. Der konkrete JSL-Checkout bleibt außerhalb des
  Tools; Zugangsdaten werden dort und nicht im Tool verwaltet.
