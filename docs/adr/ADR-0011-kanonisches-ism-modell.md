# ADR-0011 Kanonisches ISM-Modell und vorab generierte HTML-Snippets

## Status

Proposed

## Kontext

Im NCPeH-/EU-Webportal-Umfeld beschreiben International Search Masks (ISM)
länderspezifische Suchmasken als XML. Daraus sollen HTML-Snippets entstehen,
die vorab in einer Build- oder Lieferpipeline erzeugt und anschließend an
einen Webportal-Anbieter ausgeliefert werden. Der Browser erzeugt keine
Suchmasken aus XML oder einem Formulardeskriptionsmodell.

Die XML-Strukturen sind verwandt, aber nicht vollständig einheitlich. Der
betrachtete Eingangsbestand kann unterschiedliche Root-Elemente,
Namespace-Verwendungen und länderspezifische Erweiterungen enthalten.
Fachliche Unterschiede betreffen insbesondere `patientSearch`,
`documentSearch`, `identifier`, `birthDate`, `media`, mehrere Suchvarianten
pro Land und optionale ePrescription-Suchparameter.

Das im Repository enthaltene eHDSI-Schema und die Beispiele aus AT und PL
bilden eine konkrete Ausgangsbasis, aber keinen Nachweis, dass sämtliche
zukünftigen Eingänge dieser Struktur entsprechen. Abweichungen sind durch
explizit unterstützte Eingangsprofile zu behandeln, nicht durch Vermutungen
über Elementnamen oder das pauschale Entfernen von Namespaces.

Die beteiligten Rollen bleiben organisatorisch getrennt:

| Rolle | Verantwortung |
|---|---|
| ISM-/NCPeH-Anbieter | Liefert versionierbare XML-Quellen einschließlich Herkunft, Änderungsinformationen und fachlicher Klärungen. |
| Generator-Anbieter | Normalisiert unterstützte XML-Profile, prüft das kanonische Modell und erzeugt vertragskonforme Lieferartefakte. |
| Webportal-Anbieter | Integriert freigegebene HTML-Snippets, verantwortet Portalgestaltung, Laufzeitinteraktion und Anbindung an Suchschnittstellen. |

Es wird nicht vorausgesetzt, dass diese Rollen durch dasselbe Unternehmen
wahrgenommen werden. Modell und Lieferkontrakt benötigen deshalb
organisationsübergreifende Abstimmung und dürfen kein internes Produktformat
eines einzelnen Anbieters voraussetzen.

ADR-0005 legt bisher Rendering im HTTP-Proxy zur Buildzeit fest. ADR-0008
beschreibt einen vom Bedarf der WebApp abgeleiteten HTML-Kontrakt.
Dieser Vorschlag erhält die Vorabgenerierung, löst jedoch die Generatorrolle
von einem konkreten Proxy und ergänzt eine eigenständige fachliche
Modellgrenze. Ein Proxy kann weiterhin technischer Ausführungsort sein.

Bei Annahme dieses ADR sind ADR-0005 und ADR-0008 entsprechend anzupassen:
Insbesondere sind eine gemeinsame Organisationszugehörigkeit und der
stillschweigende Wegfall benötigter Funktionen keine tragfähigen
Vertragsannahmen. Bis zur Annahme bleiben die bisherigen Vorschläge unverändert.

## Entscheidungsbedarf

Zu entscheiden ist, welche stabile Architekturgrenze die Unterschiede der
XML-Quellen kapselt und welche Artefakte organisationsübergreifend vereinbart
werden.

Insbesondere ist zu prüfen, ob ein **Canonical ISM Model** das eigentliche
fachliche Architekturartefakt sein soll und HTML lediglich ein daraus
generiertes Zielartefakt darstellt. Dabei müssen XML-Herkunft, Suchsemantik,
Validierungsregeln und regulatorisch relevante Änderungen nachvollziehbar
bleiben.

Vorabgenerierung und Auslieferung von HTML sind feste Anforderungen.
Eine reine JSON-Lieferung mit anschließender Browsergenerierung erfüllt
diese Anforderungen nicht.

## Betrachtete Optionen

### Option A: Direkte XML-zu-HTML-Transformation

```text
ISM XML -> direkte Transformation -> HTML-Snippet
```

Beispielsweise verarbeitet XSLT oder ein direkter XML-Renderer die Quellen.
Ein gesonderter kanonischer Modellvertrag entfällt. Suchsemantik,
Quellvarianten und Darstellung werden unmittelbar in Transformationsregeln
abgebildet.

### Option B: Normalisierung über ein kanonisches Modell

```text
ISM XML -> Profiladapter -> Canonical ISM Model
        -> HTML-Generator -> HTML-Snippet -> Lieferung an Portal
```

Quellprofile werden auf ein technologieunabhängig definiertes Fachmodell
abgebildet. Der HTML-Generator verarbeitet ausschließlich dieses Modell.
Objektmodelle, JSON oder YAML sind mögliche Repräsentationen, nicht die
Architekturentscheidung selbst.

### Option C: Kanonisches JSON mit Rendering beim Portalanbieter

```text
ISM XML -> Canonical JSON -> Portal-Renderer -> HTML
```

Der Portalanbieter erhält das Modell und implementiert oder betreibt den
Renderer. Browsergenerierung widerspricht der Zielvorgabe. Rendering in
einer Pipeline des Portalanbieters wäre technisch vorab möglich, erfüllt
aber nicht die hier geforderte Lieferung bereits erzeugter HTML-Snippets.
Übernimmt der Portalanbieter ausdrücklich auch die getrennt vereinbarte
Generatorrolle, entspricht dies organisatorisch einer Ausprägung von B.

### Option D: Standardisiertes Formulardeskriptionsformat

```text
ISM XML -> Formulardeskription -> vereinbarter Renderer -> HTML-Snippet
```

Ein vorhandenes Format bildet die Austauschgrenze, etwa JSON Schema mit
UI-Ergänzungen, eine OpenAPI-artige Beschreibung oder ein proprietäres
Metamodell. Die Bewertung setzt Vorabgenerierung beim Generator-Anbieter
voraus; Browserrendering wäre ebenso wie bei C ausgeschlossen.

JSON Schema beschreibt vor allem Datenstrukturen und Validierung.
OpenAPI beschreibt primär API-Verträge. Beide definieren allein weder
vollständige Formularinteraktion noch sämtliche ISM-Fachsemantik.
Ein proprietäres Metamodell ist nicht automatisch ein Standard.

## Bewertung der Optionen

Die Bewertung bezieht sich auf den beschriebenen heterogenen Eingangsbestand,
nicht auf eine bereits empirisch geprüfte Implementierung.

| Kriterium | A: Direkt | B: Kanonisches ISM-Modell | C: JSON an Portal | D: Formulardeskription |
|---|---|---|---|---|
| Wartbarkeit | Anfangs einfach; Quell- und HTML-Regeln eng gekoppelt. | Gut durch getrennte Adapter, Modell und Renderer. | Gute Datengrenze; zusätzliche Rendererpflege beim Portal. | Gut bei passendem Format; Erweiterungsregeln können dominieren. |
| Erweiterbarkeit | Weitere Transformationszweige je Variante. | Neue Profile meist über Adapter; neue Semantik über Modellversion. | Modell erweiterbar; jede Portalimplementierung muss nachziehen. | Abhängig von Ausdrucksstärke und Erweiterungsmechanismen. |
| Organisatorische Entkopplung | HTML entkoppelt Portal; Generator bleibt an XML-Varianten gebunden. | Explizite Verträge für Quellen, Modell und HTML; unabhängige Anbieter möglich. | Datenaustausch entkoppelt, Renderingpflicht verbleibt beim Portal. | Gute Entkopplung bei offenem, gemeinsam interpretiertem Vertrag. |
| Langfristige Architekturqualität | Bei wachsender Variantenvielfalt begrenzt. | Fachsemantik unabhängig von Quelle und Ausgabe. | Fachmodell stabil; Darstellung verteilt auf Portalrenderer. | Hoch bei fachlicher Eignung, schwächer bei zahlreichen Sondererweiterungen. |
| Testbarkeit | End-to-End- und Transformationsprüfungen; Semantik schwerer isolierbar. | Adapter-, Modell-, Renderer- und Vertragstests getrennt möglich. | Modelltests plus Konformität jedes Portalrenderers nötig. | Schema- und Renderertests; Fachsemantik separat prüfen. |
| CI/CD-Betrieb | Einfacher Transformationsschritt. | Mehr Prüfschritte, aber klar getrennte und reproduzierbare Stufen. | Zusätzliche Renderingpipeline beim Portal erforderlich. | Gut bei offline verfügbarem Renderer und Schema. |
| Versionierbarkeit | XML-, Transformations- und HTML-Versionen; keine eigene Fachmodellversion. | Unabhängige Modell-, Adapter-, Generator- und HTML-Vertragsversionen. | Modellversion plus Kompatibilität sämtlicher Portalrenderer. | Formatversion, Erweiterungsversionen und Rendererprofil. |
| Regulatorische Nachvollziehbarkeit | Quell-/HTML-Diffs vorhanden; fachliche Wirkung aufwendiger erkennbar. | Quelldiff, semantischer Modelldiff und Zielartefakt zuordenbar. | Modelldiff möglich; konkrete Darstellung zusätzlich beim Portal nachweisen. | Abhängig von ISM-Abbildung und Herkunftsmetadaten. |
| Zukünftige Länder | Neue Regeln können bestehende Transformationen beeinflussen. | Adapter kapseln Unterschiede; unbekannte Semantik braucht bewusste Erweiterung. | Neue Datenprofile möglich; Unterstützung aller Portalrenderer erforderlich. | Gut, soweit Ländersemantik bereits ausdrückbar ist. |
| Implementierungskomplexität | Niedrig zu Beginn, mit Sonderfällen zunehmend. | Mittlerer Anfangsaufwand für Modell und Verträge. | Mittlerer Gesamtaufwand, auf Generator und Portal verteilt. | Potenziell geringer mit geeignetem Standard, hoch bei eigenen Erweiterungen. |
| Vendor Lock-in | XSLT ist offen; spezielle Transformationskonventionen können binden. | Gering bei offenem Modell, dokumentierten Verträgen und Konformitätstests. | Gering beim Datenformat; Bindung an Portalrenderer möglich. | Gering bei offenen Profilen; hoch bei proprietären Metamodellen oder Renderern. |

B bietet für dieses Ziel den besten Ausgleich zwischen langfristiger
Entkopplung und kontrollierbarer Umsetzungskomplexität. A bleibt für eng
begrenzte, stabile Profile eine plausible einfachere Lösung. D kann B
unterstützen, ersetzt aber ohne Eignungsnachweis kein ISM-Fachmodell.

## Entscheidung

Vorgeschlagen wird **Option B**.

Das **Canonical ISM Model ist das zentrale fachliche Architekturartefakt**.
Es beschreibt die für unterstützte Suchmasken erforderliche Semantik
unabhängig von XML-Layout, Programmiersprache und Portalframework.
HTML ist ein versioniertes, daraus generiertes Zielartefakt.
Das Original-XML bleibt die maßgebliche Quelle der vom Herkunftsland
gelieferten Regeln; das Modell ersetzt weder diese Quelle noch deren
fachliche oder regulatorische Autorität.

Das Modell enthält mindestens:

- Land, Suchart, Scope und stabile Identitäten von Suchvarianten.
- Felder, fachliche Feldbedeutung, Datentyp und Identifikator-Domain.
- Gruppen, Alternativen und bedingte Pflichtfeldregeln, insbesondere `CHOICE`.
- Originale Validierungsangaben einschließlich bekannter Syntax beziehungsweise
  ausdrücklich unbekannter Syntax.
- Beschriftungen, Übersetzungsschlüssel und Hilfetexte mit Sprachangaben,
  soweit durch Quellen oder vereinbarte Regeln belegbar.
- Medienreferenzen samt erforderlichen Metadaten und kontrollierte,
  namensraumbezogene Erweiterungen.
- Modellversion und Herkunftsreferenzen zu XML-Quelle, Profil und Elementen.

Stabile Feldidentitäten werden nach dokumentierten Regeln vergeben;
`label` oder die OID allein reichen dafür nicht aus. Normalisierung muss
die unterstützte Fachsemantik erhalten, aber nicht sämtliche syntaktischen
XML-Eigenschaften verlustfrei nachbilden.

Unbekannte, möglicherweise verhaltensrelevante Elemente und nicht
abbildbare Regeln erzeugen explizite Diagnosen und verhindern eine Freigabe
des betroffenen Lieferumfangs. Ein freigegebenes Profil darf rein
informative Erweiterungen ausdrücklich als solche klassifizieren.
Regeln werden weder stillschweigend verworfen noch fachlich „korrigiert“.

Das Modell erhält eine offene, maschinenprüfbare Austauschrepräsentation,
vorzugsweise JSON mit versioniertem Schema. Ein internes Objektmodell oder
YAML als Autorenformat bleibt möglich. Schema-Prüfung und zusätzliche
semantische Prüfungen ergänzen einander; das Schema allein reicht nicht.
JSON Schema kann hierfür eingesetzt werden, ohne selbst das ISM-Modell
oder eine vollständige UI-Spezifikation zu ersetzen.

Die reguläre Portallieferung enthält HTML-Snippets, erforderliche Medien
und ein Manifest. Das kanonische Modell wird als Prüf- und
Nachvollziehbarkeitsartefakt archiviert und kann zusätzlich mitgeliefert
werden. Das Portal benötigt es nicht zur Formularerzeugung.

Der HTML-Kontrakt wird gemeinsam mit den beteiligten Rollen vereinbart.
Er definiert erlaubte Struktur, Feld-/Variantenidentitäten, Validierungs-
und Interaktionsmetadaten sowie deren Zuordnung zu Suchparametern.
Die WebApp übernimmt Gestaltung und vereinbarte Interaktionen,
beispielsweise die Aktivierung einer bereits gerenderten Auswahlgruppe.
Dies ist keine Laufzeitgenerierung aus dem kanonischen Modell.
Serverseitige Suchvalidierung bleibt davon unberührt.

## Begründung

Eine reine XML-zu-HTML-Transformation vermischt zwei unterschiedliche
Änderungsachsen: neue Eingangsprofile und neue Darstellungsanforderungen.
Eine eigene Modellgrenze verhindert, dass jede Portaländerung alle
XML-Adapter oder jede neue XML-Variante den Renderer betrifft.

Ein ISM-spezifisches Fachmodell erhält Suchvarianten, bedingte
Pflichtfelder, Domains und Scope explizit. Ein generisches Formularformat
kann diese Bedeutung andernfalls in unvereinbarten Erweiterungen verstecken.
Das Modell soll deshalb fachlich minimal bleiben, nicht zu einem
universellen Formularframework wachsen.

HTML bleibt für die Lieferung zweckmäßig, weil der Portalanbieter keinen
ISM-Parser oder Modellrenderer betreiben muss. Trotzdem bleibt auch HTML
eine Vertragsgrenze: Das kanonische Modell allein garantiert weder
Portabilität noch korrekte Portalinteraktion.

Offene Verträge, gemeinsam nutzbare Referenzfälle und automatisierte
Konformitätsprüfungen ermöglichen Anbieterwechsel. JSON allein würde
diesen Effekt ohne dokumentierte Semantik nicht gewährleisten.

## Konsequenzen

### Positive Konsequenzen

- XML-Profile und HTML-Darstellung können unabhängig weiterentwickelt werden.
- Anbieterrollen bleiben unabhängig von Unternehmen und Laufzeitplattform.
- Neue Länder mit bekannter Semantik benötigen überwiegend neue Adapterdaten
  oder Profiladapter, nicht neue Portalformulare.
- Fachliche Unterschiede können vor dem Rendering geprüft werden.
- Quelldateien, Modellstände und Lieferartefakte bleiben eindeutig zuordenbar.
- Weitere Zielartefakte sind später ohne erneute XML-Auswertung möglich.

### Negative Konsequenzen

- Modell, Herkunftsabbildung und zwei Vertragsgrenzen erhöhen Anfangsaufwand.
- Fachlich neue Länderanforderungen können Modell und Renderer ändern;
  Erweiterungen sind nicht grundsätzlich codefrei.
- Modellmigrationen und kompatible Vertragsversionen benötigen Governance.
- ISM-Änderungen werden erst mit erneuter Generierung und Portalauslieferung
  wirksam; Aktualisierungsfristen sind organisatorisch abzusichern.
- Statisches HTML löst bedingte Interaktion, Barrierefreiheit und
  Suchparameterzuordnung nicht automatisch.

### Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| Normalisierung verliert Suchsemantik. | Quellenbezogene Mappingregeln, Herkunftsreferenzen und fachlich freigegebene Referenzfälle für alle unterstützten Profile. |
| Modell wird zu allgemein oder anbieterspezifisch. | Nur belegte ISM-Anforderungen aufnehmen; Erweiterungen dokumentieren und gemeinsam versionieren. |
| ISM-Regex passt nicht zur HTML-`pattern`-Syntax. | Originalregel erhalten; Übertragbarkeit explizit prüfen. Unvereinbare Regeln blockieren Freigabe, bis eine abgestimmte Umsetzung existiert. |
| Fremdes XML oder Medien erzeugen unsichere Inhalte. | Externe XML-Entitäten und unkontrollierte Nachladezugriffe verhindern; Werte escapen, Medien prüfen und aktive Inhalte im Lieferkontrakt ausschließen. |
| HTML-Vertrag wird unterschiedlich interpretiert. | Struktur- und Verhaltenstests beim Generator sowie Integrationsprüfungen im Portalbuild; keine rein visuellen Snapshots als Nachweis. |
| Regulatorische Änderungen werden verspätet oder falsch übernommen. | Änderungsereignisse, fachlicher Modelldiff, dokumentierte Freigabe und vereinbarte Lieferfristen; automatischer Diff ersetzt keine fachliche Bewertung. |
| Builds sind nicht reproduzierbar. | Eingaben, Profile, Generator, Vorlagen, Übersetzungen und Verträge fest versionieren; Netzwerkabhängigkeiten während der Generierung ausschließen. |

Ein Liefermanifest ordnet mindestens Quellhashes, Eingangsprofile,
Modellversion, Adapter-/Generatorstand, Vorlagen-/Übersetzungsstand,
HTML-Vertragsversion und Artefakthashes zu. Erzeugungszeitpunkt und
Freigabereferenz ergänzen den Auditnachweis; variable Auditmetadaten werden
von deterministisch erzeugten Inhaltsartefakten getrennt.

Die Lieferpipeline prüft Quellen, Modell und Ausgabe vor Veröffentlichung.
Bei Fehlern wird kein scheinbar erfolgreicher neuer Stand ausgeliefert.
Ein vorheriger freigegebener Stand darf nur nach vereinbarter
Aktualitäts- und Rückfallregel weiterverwendet werden.

## Offene Punkte

1. Wer verantwortet Modell, Profilkatalog und HTML-Kontrakt gemeinsam,
   und wer genehmigt fachliche Mappingänderungen?
2. Welche realen Länderdateien und XML-Profile bilden den verbindlichen
   Unterstützungsumfang, einschließlich `nextOfKinSearch` und ePrescription?
3. Welche Semantik haben Scope, Suchvarianten, Datumsangaben und Regex
   außerhalb der vorhandenen Beispiele?
4. Wie werden stabile Identitäten, Extension-Namensräume, Breaking Changes
   und Übergangszeiträume verbindlich definiert?
5. Welche HTML-Struktur und Interaktionsmetadaten akzeptieren die
   Portalanbieter, insbesondere für Auswahlgruppen und Suchparameter?
6. Wer pflegt Übersetzungen, prüft Medienrechte und verantwortet
   Barrierefreiheit sowie deren Abnahme?
7. Welche Lieferform, Integritätsnachweise, Aufbewahrungsfristen und
   Aktualisierungs-/Rückfallregeln sind erforderlich?
8. Bietet ein vorhandenes offenes Formulardeskriptionsprofil genügend
   ISM-Semantik, um Teile des Modells ohne Sonderkonventionen abzubilden?

## Empfehlung für den ersten Prototyp

Ein kleiner, technologieunabhängig abgegrenzter vertikaler Schnitt soll
Option B überprüfen. Die Umsetzung kann beispielsweise mit XSLT plus
Modellserialisierung oder mit XML-Bibliotheken und Templates in Python,
Java oder .NET erfolgen. Die konkrete Sprache ist nicht entscheidend.

Der Prototyp verwendet die vorhandenen AT-/PL-Beispiele und zusätzliche
vereinbarte Referenzfälle für abweichende Root-/Namespace-Profile,
mehrere Suchvarianten und bisher nicht abgedeckte Erweiterungen.
Künstliche Fälle sind als solche zu kennzeichnen.

Er umfasst einen minimalen Modellvertrag, passende Profiladapter, einen
separaten HTML-Generator und ein Liefermanifest. Unterstützt werden
`patientSearch`, `documentSearch`, optionale ePrescription-Felder,
`NORMAL`/`CHOICE`, Pflichtfelder, `birthDate`, Domains und Medien.
Nicht unterstützte Semantik muss explizit fehlschlagen.

Die Abnahme weist Folgendes nach:

- Für jeden Referenzfall entsprechen Varianten, Gruppen, Feldzuordnung und
  Pflichtfeldbedingungen dem fachlich geprüften Erwartungsmodell.
- Unbekannte Profile, nicht abbildbare Erweiterungen und unvereinbare
  Validierungsregeln verhindern eine neue Lieferung.
- Identische versionierte Eingaben erzeugen bytegleiche Modell- und
  HTML-Inhaltsartefakte, getrennt von variablen Auditmetadaten.
- Ein Portal-Test integriert ausschließlich vorab erzeugte Snippets und
  prüft Auswahlinteraktion, Eingabevalidierung und Suchparameterzuordnung.
- Eine Quelländerung ist über Modelldiff und Manifest bis zum geänderten
  HTML-Artefakt nachvollziehbar.
- Mindestens ein zusätzlicher Fall mit bereits unterstützter Fachsemantik
  lässt sich ohne Änderung des Renderers integrieren.

Erst danach wird entschieden, ob das Modell ausreichend klein und stabil
ist und ob Bestandteile von Option D Wiederverwendung ermöglichen.
Der Prototyp rechtfertigt noch keine vollständige Länderabdeckung.

Verwandtes Dokument: [ADR-0005](ADR-0005-ism-rendering.md). Detaillierte
ISM-Datenanalysen aus realen Länderdaten sind im gefilterten öffentlichen Export
nicht enthalten.
