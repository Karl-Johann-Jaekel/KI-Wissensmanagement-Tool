# ADR-13: Briefing-Doc als Kette gewöhnlicher, belegter Antworten

Status: angenommen

## Kontext

NotebookLMs Studio erzeugt aus den Quellen fertige Dokumente — Briefing-Doc, Study Guide, FAQ,
Timeline. `plan.md` hatte den Briefing-Doc-Generator als einzigen geplanten Bonus vorgesehen.

Der naheliegende Weg wäre ein zweiter Erzeugungspfad: viel Text ins Modell, ein langes Dokument
heraus. Damit stünde aber die Kernzusage des Projekts auf dem Spiel. Belege werden am fertigen
Text validiert ([ADR-05](005-validated-citations.md)); ein eigener Pfad hätte diese Prüfung
entweder verdoppelt oder umgangen.

## Entscheidung

Das Briefing ist **keine neue Art zu generieren, sondern eine Folge gewöhnlicher Antworten**. Für
jede Kernfrage des Notebooks ([ADR-12](012-notebook-overview.md)) läuft der normale Chat-Pfad:
Hybrid-Retrieval auf die ausgewählten Quellen, dasselbe System-Prompt, dieselbe Zitatprüfung. Die
Abschnitte werden zu einem Dokument zusammengesetzt und als Notiz gespeichert, deren Belege
klickbar bleiben ([ADR-11](011-note-citations.md)).

Jeder Abschnitt wird gegen seine eigenen Passagen geprüft und beginnt deshalb bei `[1]`. Beim
Zusammensetzen werden die Nummern auf eine dokumentweite Zählung umgeschrieben — eine Passage,
die in zwei Abschnitten zitiert wird, behält eine Nummer. Das Umschreiben passiert in einem
einzigen Durchlauf, damit sich vertauschte Nummern nicht gegenseitig überschreiben.

Fehlt der Überblick noch, dient je eine Fragevorschlag pro Quelle als Ersatz.

## Konsequenzen

- Das Briefing erbt alle Garantien des Chats: keine erfundenen Belege, keine Aussagen ohne
  Passage, sichtbarer Hinweis, wenn die Quellen nichts hergeben.
- Es erbt damit auch die Schwäche: taugt die Frage nicht, taugt der Abschnitt nicht. Der erste
  Lauf gegen die Demo-Quellen lieferte in drei von vier Abschnitten „Dazu enthalten die Quellen
  keine Angaben", weil der Überblick Synthesefragen gestellt hatte („Inwiefern unterscheiden sich
  …?"). Solche Fragen beantwortet keine einzelne Textstelle. Behoben wurde das dort, wo es
  entsteht — im Überblick-Prompt, der nun nach Fragen verlangt, die eine Quelle direkt
  beantwortet, verteilt über die Quellen statt in einer Frage gebündelt. Das hilft dem Chat
  genauso, weil dieselben Fragen dort als Einstieg angeboten werden.
- Jeder Abschnitt bekommt doppelt so viele Passagen wie ein Chat-Turn: ihm fehlt die Rückfrage,
  mit der ein Gespräch Lücken schließt.
- Es kostet eine LLM-Anfrage je Kernfrage, höchstens vier. Der Aufruf ist synchron und dauert
  etwa eine Minute; die Oberfläche sagt das vorher an, statt einen stummen Spinner zu zeigen.
- Das Dokument ist so strukturiert wie die Kernfragen. Eine freie Gliederung („Hintergrund,
  Risiken, Empfehlung") wäre dokumentartiger, hätte aber keine Grundlage in den Quellen.
- `retrieve_passages`, `build_answer_messages` und `validate_answer` sind aus dem Chat-Router
  heraus öffentlich, weil sie jetzt zwei Aufrufer haben.

## Verworfene Alternativen

- **Ein langer Prompt über alle Passagen:** ein Dokument aus einer Anfrage, aber die Zitatprüfung
  hätte über einen Text laufen müssen, dessen Passagenmenge nicht mehr zur einzelnen Aussage
  passt — und bei 666 Abschnitten passt ohnehin nicht alles ins Fenster.
- **Aus den Quellen-Guides schreiben statt aus Passagen:** billiger, aber dann verweisen die
  Belege auf Zusammenfassungen statt auf Originalstellen. Genau das war der Fehler, den
  [ADR-11](011-note-citations.md) behoben hat.
