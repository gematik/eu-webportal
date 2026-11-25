# ADR-0002 Technologieauswahl Frontend

## Status

Accepted

## Datum

2026-08-27, updated 2026-10-06

## Kontext

Für das EU-Webportal soll eine Technologie ausgewählt werden, die:

- für eine Beispielimplementierung geeignet ist
- den Browser als Ausführungsumgebung nutzt
- langfristig wartbar ist
- OpenAPI-basierte Entwicklung unterstützt

In der Evaluierung wurden betrachtet:

- Angular
- React
- Vue

## Entscheidung

Das EU-Webportal wird mit Angular entwickelt.

## Begründung

Angular bietet:

- integriertes Routing
- Dependency Injection
- TypeScript als Standard
- etablierte Enterprise-Strukturen
- gute Testbarkeit
- langfristige Wartbarkeit

Die Architektur der Anwendung besteht primär aus Formularen, Workflow-Schritten und API-Kommunikation und passt damit gut zu Angular.

## Konsequenzen

### Positiv

- Klare Projektstruktur
- Gute Skalierbarkeit
- Große Verbreitung im Enterprise-Umfeld

### Negativ

- Höhere Einstiegskomplexität
- Größere Build-Artefakte