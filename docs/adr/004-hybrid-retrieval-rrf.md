# ADR-04: Hybrid Retrieval (Volltext + Vektor) mit RRF

Status: angenommen

## Kontext

Reine Vektorsuche verfehlt oft exakte Begriffe: Eigennamen, Paragraphen, Produktcodes,
Abkürzungen. Genau solche Fragen stellen Prüfer im Live-Test gern. Long-Context-Stuffing
(alle Quellen in den Prompt) sprengt bei mehreren PDFs das Free-Tier-Budget.

## Entscheidung

- Zwei Kandidatenlisten pro Frage, jeweils gefiltert auf die ausgewählten Quellen:
  - Vektor: Top-20 per Cosine-Distanz (HNSW-Index, `hnsw.iterative_scan` gegen
    Unterfüllung bei Filterung).
  - Volltext: Top-20 per `ts_rank_cd` auf einer generierten `tsvector`-Spalte.
- Textsuchkonfiguration `simple` (kein Stemming), weil Quellen DE/EN gemischt sind. Die Anfrage
  wird zu einer ODER-Verknüpfung der Terme; eine kleine DE/EN-Stoppwortliste verhindert, dass
  Füllwörter das Ranking dominieren.
- Fusion per Reciprocal Rank Fusion (`k = 60`), Top-8 Chunks gehen in den Prompt.
- `tsvector` als `GENERATED ALWAYS … STORED`-Spalte statt Trigger: gleiche Wirkung, weniger Code.

## Konsequenzen

- Exakte Begriffe werden gefunden, semantische Umschreibungen ebenfalls.
- `simple` ohne Stemming findet keine Flexionsformen („Verträge“ ≠ „Vertrag“) — die Vektorsuche
  gleicht das aus.
- RRF ist parameterarm und braucht keine Score-Normalisierung.

## Nachtrag: Normverweise als dritte Liste

Test mit der KI-Verordnung (200 Seiten, 578 Abschnitte): „Was regelt Artikel 50?“ ergab „keine
Angaben“. Die Phrase kommt in fünf Abschnitten vor, aber die ODER-Suche bewertet sie nicht höher
als hunderte Abschnitte mit „Artikel“, und Embeddings unterscheiden Artikelnummern nicht.

- Fragen werden auf Verweise geprüft (`Artikel|Art.|Article`, `§|Paragraph`, `Anhang|Annex` +
  Nummer). Treffer bilden eine dritte Liste, in der RRF doppelt gewichtet.
- Innerhalb der Liste steht zuerst der **definierende** Abschnitt – Verweis gefolgt von einem
  Titel („Artikel 50 Transparenzpflichten …“) statt „Artikel 50 Absatz 2“ oder „Artikel 50;“ –,
  direkt danach dessen Folgeabschnitt mit dem eigentlichen Normtext, dann bloße Querverweise.
- Ergebnis: Antwort mit Beleg auf S. 123 (Art. 50 Abs. 1 und 2).

## Nachtrag: gemessen

Nachträglich mit 17 Fragen gegen das Demo-Notebook gemessen, die erwarteten Seiten in den
gespeicherten Abschnitten nachgeschlagen
([README → Retrieval-Qualität](../../README.md#retrieval-qualität)):

| Rangliste | hit@8 | MRR@8 |
|---|---|---|
| Vektor | 71 % | 0,53 |
| Volltext | 59 % | 0,26 |
| Normverweis (3 Fragen mit Artikelnummer) | 100 % | 0,47 |
| RRF | **94 %** | **0,59** |

Die Entscheidung trägt: die Fusion schlägt die beste Einzelliste um 23 Prozentpunkte. Die
Volltextsuche ist allein die schwächste Liste, rettet aber zwei Fragen, an denen die Vektorsuche
scheitert. Offener Fehlschlag: die Bußgeldbeträge (S. 168/169) erreicht keine Liste.

Die Normverweis-Liste hängt von der Instanz ab: lokal liegt ihre MRR bei 0,72 statt 0,47. Die
Überschriften-Erkennung hält jedes großgeschriebene Wort nach der Nummer für einen Titel, im Deutschen
also auch Substantive („von Artikel 4 Gebrauch zu machen"). Gibt es mehrere solche Treffer, entscheidet
die zufällige UUID der Quelle über die Reihenfolge. Details im
[README](../../README.md#retrieval-qualität); bewusst nicht vor der Abgabe umgebaut, weil jede
inhaltliche Sortierung neu gemessen werden müsste.

## Verworfene Alternativen

- Nur Vektorsuche: schwach bei Eigennamen und Codes.
- Phrasen-Operator (`artikel <-> 50`) in der ODER-Anfrage: findet die Abschnitte, `ts_rank_cd`
  kennt aber keine Termseltenheit und rankt sie nicht nach oben.
- Long-Context-Stuffing: Kosten/Rate-Limit, schlechtere Zitierbarkeit.
- Reranker (Cross-Encoder): bessere Qualität, aber zusätzliches Modell und CPU-Latenz im Live-Test.
