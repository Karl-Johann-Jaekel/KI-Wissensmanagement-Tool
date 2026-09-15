# ADR-02: Embeddings lokal auf CPU mit multilingual-e5-small

Status: angenommen

## Kontext

Beim Upload eines 50-seitigen PDFs entstehen ~100 Chunks, die sofort eingebettet werden müssen.
Quellen sind deutsch und englisch gemischt. Ziel-Hardware ist ein kleiner VPS ohne GPU.

## Entscheidung

- `intfloat/multilingual-e5-small` (384 Dimensionen) über **fastembed** (ONNX Runtime, CPU).
- fastembed 0.8 führt das Modell nicht in seiner Liste; es wird per
  `TextEmbedding.add_custom_model` mit dem offiziellen ONNX-Export aus dem Hugging-Face-Repo
  registriert (Mean-Pooling, L2-Normalisierung). Verifiziert: Query/Passage-Similarity plausibel.
- e5-Konvention: Passagen mit `passage: `, Suchanfragen mit `query: ` präfixen.
- Modell wird im Docker-Build heruntergeladen, damit der erste Start nicht blockiert.

## Konsequenzen

- Kein Rate-Limit und keine Kosten beim Bulk-Embedding; Quelleninhalte verlassen für das
  Embedding den Server nicht.
- Die ONNX-Datei ist ~470 MB (nicht ~120 MB wie ursprünglich geschätzt), RAM-Bedarf des
  Backends entsprechend ~0,7–1 GB. Für den VPS noch tragbar, Memory-Limit im Compose setzen.
- Dimension 384 ist im Schema fest; ein Modellwechsel erfordert Migration und Re-Embedding.

## Verworfene Alternativen

- `mistral-embed`: Free-Tier-Limits beim Bulk-Upload, zusätzlicher Netzwerk-Hop.
- `paraphrase-multilingual-MiniLM-L12-v2` (von fastembed nativ unterstützt): schwächer auf
  Retrieval-Benchmarks als e5-small; bleibt Fallback, falls der Custom-Export bricht.
- `multilingual-e5-large`: 1024 d, ~2,2 GB — zu schwer für CPU-Upload im Live-Test.
