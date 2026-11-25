# ADR-0003 OpenAPI First

## Status

Accepted

## Datum

2026-08-27, updated 2026-10-06

## Kontext

Die Schnittstellen des NCPeH-Proxys sollen über OpenAPI beschrieben werden.

Mocks, Tests und Frontend-Clients sollen möglichst aus denselben Artefakten erzeugt werden oder darauf basieren.

## Entscheidung

Alle HTTP-Schnittstellen werden zunächst in OpenAPI beschrieben.

Implementierungen folgen der Spezifikation.

Nicht die Implementierung definiert die API, sondern die API definiert die Implementierung.

## Begründung

OpenAPI ermöglicht:

- gemeinsame Sprache zwischen Architektur und Entwicklung
- automatisierte Client-Generierung
- Mock-Generierung
- frühzeitige Validierung von Schnittstellen
- bessere Abstimmung mit DVKA und weiteren Beteiligten

## Konsequenzen

### Positiv

- Contract First Entwicklung
- Konsistente Schnittstellen
- Frühe Parallelisierung von Frontend- und Backend-Entwicklung

### Negativ

- Höherer Aufwand zu Beginn
- Pflege der OpenAPI-Dokumente erforderlich