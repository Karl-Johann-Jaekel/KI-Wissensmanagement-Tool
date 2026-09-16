# ADR-05: Zitate als validierte Passagen-Nummern

Status: angenommen

## Kontext

Kern von NotebookLM ist Vertrauen: Jede Aussage muss auf eine konkrete Stelle zurückführbar sein.
Lässt man das Modell Quellen frei benennen, erfindet es Titel oder Seitenzahlen.

## Entscheidung

- Die Top-8-Chunks gehen nummeriert (`[1]` … `[8]`) mit Quelle und Seite in den Prompt.
- Das Modell zitiert ausschließlich mit `[n]`. Das Backend (`app/citations.py`):
  1. extrahiert alle Marker, auch Varianten wie `[1, 3]` oder `[2][4]`,
  2. verwirft Nummern, die nicht in der Kandidatenliste stehen, sowie Folgen von mehr als drei
     Belegen an einer Stelle (Modelle hängen sonst alle Passagen an „keine Angaben“),
  2a. entfernt Klammern mit Ziffern, die keine Passagennummer sind — `[9(3)]`, `[Anhang 2]`,
     aus dem Quelltext übernommene Verweise. Sie sehen wie ein Beleg aus, führen aber nirgendwo
     hin. Klammern ohne Ziffer (`[sic]`) bleiben,
  3. nummeriert die gültigen in Reihenfolge des ersten Auftretens neu (`[1]`, `[2]`, …),
  4. liefert `citations[]` mit `chunk_id`, `source_id`, Titel, Seite und Snippet.
- Liefert die Suche keine Passagen, antwortet das Backend ohne LLM-Aufruf mit einem
  festen „nicht in den Quellen“-Hinweis.

## Konsequenzen

- Jedes angezeigte Zitat verweist garantiert auf einen existierenden Chunk; der Zitat-Viewer
  lädt ihn über seine ID.
- Das Modell kann einen gültigen Marker an eine falsche Aussage hängen — Validierung prüft
  Existenz, nicht inhaltliche Korrektheit. Gegenmaßnahme: Prompt mit Beispiel, niedrige Temperatur.

## Verworfene Alternativen

- Freie Quellenangaben durch das Modell: nicht verifizierbar.
- Satzweises Nachträglich-Matching (Embedding-Ähnlichkeit Satz ↔ Chunk): aufwendiger, fehleranfällig.
