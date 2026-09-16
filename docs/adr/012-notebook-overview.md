# ADR-12: Notebook-Überblick aus den Quellen-Guides, nicht aus dem Volltext

Status: angenommen

## Kontext

In NotebookLM ist das Erste, was man beim Öffnen eines Notebooks sieht, eine Zusammenfassung über
alle Quellen hinweg plus Fragen, die man stellen könnte. Dieser Klon hatte das nur je Quelle
([ADR-02](002-local-embeddings.md) liefert die Einbettungen, der Quellen-Guide die Zusammenfassung)
— was die Sammlung als Ganzes abdeckt, musste man sich selbst zusammenreimen.

## Entscheidung

`notebooks` bekommt `summary`, `key_questions`, `overview_status` und `overview_error`
(Migration 0004). Erzeugt wird der Überblick **aus den vorhandenen Quellen-Guides**: Titel,
Kernthemen und Zusammenfassung jeder fertigen Quelle gehen als Eingabe an das Modell, nicht der
Volltext.

Damit kostet der Überblick **eine kleine LLM-Anfrage, unabhängig von der Größe des Notebooks**.
Die Demo-Sammlung umfasst 666 Abschnitte; über den Volltext wäre das ein zweites Map-Reduce mit
entsprechend vielen Anfragen ans Free-Tier-Kontingent.

Der Überblick wird nach jedem fertigen Quellen-Guide und nach dem Löschen einer Quelle neu
gebaut. Er beschreibt damit nie einen Quellenbestand, den es nicht mehr gibt. Ohne fertige Quelle
fällt er auf `pending` zurück, und das Notebook zeigt wieder seinen leeren Zustand.

## Konsequenzen

- Der Überblick ist so gut wie die Quellen-Guides. Scheitert ein Guide am Rate-Limit, fehlt diese
  Quelle im Überblick — sichtbar, weil die Quelle im UI ihren Fehlerzustand zeigt und der Guide
  einzeln neu angestoßen werden kann.
- Jede hinzugefügte Quelle kostet eine zusätzliche Anfrage für den neuen Überblick. Bei vier
  Demo-Quellen sind das vier statt einer — vertretbar, weil die Alternative ein veralteter
  Überblick wäre.
- Die quellenübergreifenden Fragen sind der natürliche Einstieg in den Chat und werden im leeren
  Chat vor den Fragen der einzelnen Quellen angeboten.

## Verworfene Alternativen

- **Über den Volltext zusammenfassen:** genauer, aber teuer und langsam, und die Guides haben
  denselben Text bereits verdichtet.
- **Nur auf Knopfdruck erzeugen:** billiger, aber dann ist der Überblick beim Öffnen leer — genau
  die Stelle, an der NotebookLM etwas zeigt.
