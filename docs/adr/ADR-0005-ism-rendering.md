# ADR-0005 Rendering von International Search Masks

## Status

Proposed

Überarbeitet am 2026-09-10. Die ursprüngliche Fassung sah ein Rendering zur
Laufzeit in der WebApp vor. Siehe Änderungshistorie am Ende.

Der ebenfalls vorgeschlagene [ADR-0011](ADR-0011-kanonisches-ism-modell.md)
ergänzt ein kanonisches ISM-Modell und eine organisatorisch unabhängige
Generatorrolle. Bei dessen Annahme ist die Festlegung auf den HTTP-Proxy
anzupassen; die Vorabgenerierung bleibt erhalten.

## Datum

2026-08-27, überarbeitet 2026-09-10

## Kontext

International Search Masks (ISM) werden durch Land A definiert. Sie liegen als
`Extension` in der SMP `ServiceMetadata` und folgen dem Schema
`specs/ism/schema/ehdsi-ism-2023.xsd`. Die Struktur variiert zwischen Ländern.

Das Sequenzdiagramm zum Use Case "ISM bereitstellen" und der Arazzo-Workflow
`wf-ism-bereitstellen.yaml` legen einen Ablauf fest, der von der ursprünglichen
Annahme abweicht:

1. Der NCPeH-FD stellt die ISM als FHIR-Bundle bereit (`GET /ismlist`).
2. Der HTTP-Proxy rendert daraus HTML (`POST /ism/render`).
3. Der Buildprozess ruft das Ergebnis ab (`GET /ism`) und bindet es zusammen mit
   den Flaggen in das Deployment-Artefakt der WebApp ein.
4. Die WebApp lädt zur Laufzeit nur noch statische HTML-Ressourcen.

Das Diagramm hält ausdrücklich fest: kein Lazyloading der ISM über die WebApp,
sondern statische Bereitstellung im WebApp-Deploymentartefakt.

Damit findet das Rendering nicht in der WebApp statt, sondern im Proxy zur
Buildzeit.

## Entscheidung

Das Rendering der Suchmasken erfolgt im HTTP-Proxy zur Buildzeit.

Die WebApp implementiert keinen ISM-Renderer und ruft zur Laufzeit keine
ISM-Schnittstelle auf. Sie zeigt die Länderübersicht an und lädt die zum
gewählten Land gehörende, vorgerenderte HTML-Ressource.

Es werden weiterhin keine fest implementierten Suchformulare pro Land erstellt.
Der datengetriebene Ansatz bleibt bestehen, verlagert sich aber vom Browser in
den Proxy.

Die Eingabevalidierung im Browser bleibt Aufgabe der WebApp. Die dafür nötigen
Regeln aus dem ISM, insbesondere `format` und `mandatory`, müssen das Rendering
überdauern.

## Begründung

- Das Sequenzdiagramm und der Arazzo-Workflow sind die verbindliche Vorgabe der
  Architektur.
- Ohne Laufzeitaufruf entfällt die Abhängigkeit der WebApp vom Proxy im
  Normalbetrieb.
- Die ISM ändert sich selten. Ein täglicher Abgleich mit anschließendem Build ist
  ausreichend.
- Die Auslieferung ist ohne Laufzeit-Cache reproduzierbar. Der Auslieferungsstand
  entspricht genau dem Build.

## Konsequenzen

### Positiv

- Einfachere WebApp, kein Renderer und kein Cache im Browser
- Deterministischer Auslieferungsstand
- Neue Länder ohne Codeänderung möglich

### Negativ

- Jede ISM-Änderung erfordert einen Build und ein Deployment
- Die Renderlogik liegt beim Proxy und damit außerhalb dieses Projekts
- Der Zeitraum zwischen Änderung und Wirksamkeit verlängert sich

### Auswirkungen auf MVP 1

Das Erfolgskriterium "ISM zwischenspeichern" aus `docs/architecture/mvp1.md`
entfällt. Stattdessen zeigt MVP 1 die bereitgestellte Suchmaske an und
ermöglicht das Ausfüllen sowie die Validierung der Eingaben anhand der
ISM-Regeln. Die Suchanfrage wird in MVP 1 nicht abgesendet.

## Offene Punkte

Die Punkte 1, 2 und 4 der ursprünglichen Fassung sind durch ADR-0008 aufgelöst.
Die Form des gerenderten HTML ist nicht extern vorgegeben, sondern wird vom
Bedarf der WebApp her festgelegt. Benötigte Angaben wie `format` und `mandatory`
werden mitgeliefert. Wird etwas nicht geliefert, entfällt die zugehörige
Funktion. Die Gestaltung verantwortet die WebApp.

Offen bleibt:

1. Die Verantwortung für Barrierefreiheit und Mehrsprachigkeit des gerenderten
   HTML ist nicht festgelegt.
2. Der in ADR-0008 beschriebene Kontrakt ist mit den Verantwortlichen des Proxys
   abzustimmen.

## Änderungshistorie

### 2026-09-10

Ursprüngliche Entscheidung: "Die WebApp rendert Suchmasken dynamisch aus den
gelieferten ISM-Daten."

Diese Fassung entstand vor Vorliegen des Sequenzdiagramms und des
Arazzo-Workflows. Beide Artefakte verlagern das Rendering in den Proxy und die
Buildzeit. Die Entscheidung wurde entsprechend angepasst.

Da die ADR den Status `Proposed` trug und nie in Kraft war, erfolgte die
Anpassung in diesem Dokument statt in einer Folge-ADR.
