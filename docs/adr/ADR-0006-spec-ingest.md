# ADR-0006 Einbindung externer OpenAPI- und Arazzo-Spezifikationen

## Status

Proposed

## Datum

2026-09-10

## Kontext

Die OpenAPI- und Arazzo-Spezifikationen des NCPeH-Proxys werden nicht in diesem
Repository gepflegt. Sie werden durch die Architektur in einem separaten Projekt
bereitgestellt.

ADR-0003 und ADR-0004 legen fest, dass Clients, Mocks und Tests aus diesen
Artefakten erzeugt werden. Damit besteht eine harte Build-Abhängigkeit zu einem
fremden Repository.

Dieses Projekt ist ein PoC. Der Build muss auch dann funktionieren, wenn das
Architektur-Repository nicht erreichbar ist oder sich unabgestimmt ändert.

Betrachtete Optionen:

- Git Submodule auf das Architektur-Repository
- Bezug über ein internes npm-Package
- Vendoring der Spezifikationen mit Versions-Pinning

## Entscheidung

Die Spezifikationen werden per Vendoring eingebunden.

Kopien der Upstream-Artefakte liegen versioniert im Repository:

```
openapi/upstream/     # kopierte OpenAPI-Dokumente, read-only
arazzo/upstream/      # kopierte Arazzo-Workflows, read-only
specs.lock.json       # Quelle, Ref, Commit-SHA und Prüfsumme je Datei
tools/fetch-specs.mjs # Aktualisierungs-Skript
```

Regeln:

- `npm run specs:fetch` lädt die Artefakte anhand eines Tags oder Commit-SHA
  und schreibt `specs.lock.json` fort.
- Die Verzeichnisse `*/upstream/` werden nicht manuell bearbeitet.
- Aktualisierungen erfolgen ausschließlich als eigener Commit.
- `npm run specs:check` prüft in der CI auf Abweichung zum Upstream und meldet
  Drift, zieht aber nicht automatisch nach.

Aus den Spezifikationen abgeleitete Artefakte, insbesondere der generierte
Angular-Client, sind Build-Ergebnisse und werden nicht eingecheckt.

Projekteigene Ergänzungen werden getrennt von `upstream/` abgelegt, damit sie
bei Aktualisierungen nicht verloren gehen.

## Begründung

Vendoring erfüllt die Anforderungen des PoC am besten:

- reproduzierbare und offline lauffähige Builds
- keine Abhängigkeit von Erreichbarkeit oder Berechtigungen des Fremd-Repositories
- Änderungen an der Spezifikation werden im Git-Verlauf sichtbar und reviewbar,
  statt still einzufließen
- Prüfsummen machen unbemerkte Änderungen erkennbar

Git Submodule wurden verworfen, da sie kein Teil-Checkout erlauben, zusätzliche
Authentisierung in der CI erfordern und im Entwicklungsalltag fehleranfällig
sind.

Ein npm-Package wurde verworfen, da die dafür nötige Publish-Pipeline im
Architektur-Projekt derzeit nicht existiert. Sobald sie besteht, ist ein Wechsel
möglich, da nur `tools/fetch-specs.mjs` betroffen wäre.

## Konsequenzen

### Positiv

- Deterministische Builds
- Nachvollziehbarer Stand der Spezifikation zu jedem Commit
- Klare Trennung zwischen fremden und eigenen Artefakten
- Wechsel der Bezugsquelle nur an einer Stelle nötig

### Negativ

- Aktualisierungen erfolgen manuell und können veralten
- Spezifikationen liegen redundant in zwei Repositories
- Zugriffsweg auf das Architektur-Repository muss noch geklärt werden
  (URL, Authentisierung, Tagging-Konvention)
