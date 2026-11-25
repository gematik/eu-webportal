# ADR-0001 Architekturansatz EU-Webportal

## Status

Accepted

## Datum

2026-08-27, updated 2026-10-06

## Kontext

Das EU-Webportal soll als Beispielimplementierung für ePeD-B entwickelt werden.

Gemäß Spezifikation wird das EU-Webportal als WebApp betrieben. Die fachliche Verarbeitung erfolgt clientseitig im Browser des Leistungserbringers.

Die Architektur soll zukünftige Anwendungsfälle wie:

- Patientenidentifikation
- Rezeptabruf
- Dispensierung
- ASL-Kommunikation

unterstützen.

Darüber hinaus soll die Lösung als Open-Source-Projekt veröffentlicht werden können.

## Entscheidung

Das EU-Webportal wird als Single Page Application (SPA) umgesetzt.

Die Anwendung wird in zwei Bereiche aufgeteilt:

### Shell

Verantwortlich für:

- Routing
- Navigation
- State Management
- API-Kommunikation
- Fehlerbehandlung

### Fachliche Komponenten

Fachliche UI-Bausteine werden als Web Components umgesetzt.

Beispiele:

- Country Selector
- Search Mask Renderer
- Patient Search
- Prescription List
- Dispensation Form

## Begründung

Die Aufteilung ermöglicht:

- klare Trennung zwischen Anwendung und Fachlogik
- Wiederverwendbarkeit fachlicher Komponenten
- mögliche Nachnutzung in anderen Umgebungen
- langfristige Wartbarkeit

## Konsequenzen

### Positiv

- Gute Modularisierung
- Wiederverwendbare Fachkomponenten
- Framework-unabhängige UI-Bausteine

### Negativ

- Zusätzlicher Integrationsaufwand zwischen Angular und Web Components
- Höhere technische Komplexität im Vergleich zu einer rein Angular-basierten Lösung