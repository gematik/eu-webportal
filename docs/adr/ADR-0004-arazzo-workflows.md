# ADR-0004 Workflow First mit Arazzo

## Status

Accepted

## Datum

2026-08-27, updated 2026-10-06

## Kontext

Fachliche Abläufe sollen nicht ausschließlich textuell dokumentiert werden.

Für zentrale Use Cases sollen maschinenlesbare Workflow-Beschreibungen entstehen.

## Entscheidung

Geschäftsprozesse werden zusätzlich als Arazzo Workflows beschrieben.

Beispiele:

- ISM abrufen
- Patient identifizieren
- Rezept abrufen
- Dispensierung durchführen

## Begründung

Arazzo ermöglicht:

- ausführbare Prozessdokumentation
- Mock-Generierung
- Testautomatisierung
- Nachvollziehbarkeit der Fachlogik

## Konsequenzen

### Positiv

- Verbindung von Spezifikation und Implementierung
- Wiederverwendbare Workflow-Beschreibungen

### Negativ

- Zusätzliche Artefakte müssen gepflegt werden
- Einarbeitung in Arazzo notwendig