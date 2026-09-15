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

## Verworfene Alternativen

- Nur Vektorsuche: schwach bei Eigennamen und Codes.
- Long-Context-Stuffing: Kosten/Rate-Limit, schlechtere Zitierbarkeit.
- Reranker (Cross-Encoder): bessere Qualität, aber zusätzliches Modell und CPU-Latenz im Live-Test.
