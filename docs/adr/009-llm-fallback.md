# ADR-09: LLM-Fallback innerhalb von Mistral statt Ollama

Status: angenommen

## Kontext

Größtes Risiko im Live-Test ist ein Rate-Limit oder Ausfall des Sprachmodells. Naheliegend wäre
ein automatischer Fallback auf ein lokales Modell über Ollama. Der Demo-VPS hat keine GPU.

## Messung

Gleicher RAG-Prompt wie in Produktion (8 Passagen aus dem Transformer-Paper, ~3 000–4 600 Tokens),
Frage nach Attention-Heads (Antwort steht auf S. 5) und eine Frage außerhalb der Quellen.
Hardware: Laptop mit Ryzen 7 5800H (16 Threads) und RTX 3070; „CPU“ = `num_gpu: 0`.

| Modell | Hardware | Antwortzeit | Zitate |
|---|---|---|---|
| `qwen2.5:3b` | GPU | 1,2–1,5 s | keine `[n]` gesetzt |
| `qwen2.5:3b` | CPU | 42–56 s | keine `[n]` gesetzt |
| `qwen2.5` (7B) | GPU | 2,3–3,0 s | gesetzt, aber auf falsche Passagen (S. 2/3) |
| `qwen2.5` (7B) | CPU | 91–118 s | gesetzt, aber auf falsche Passagen (S. 2/9) |
| `ministral-14b-latest` | Mistral API | 0,5–2,5 s | korrekt (S. 5) |
| `ministral-8b-latest` | Mistral API | 0,5–1,4 s | korrekt (S. 5) |

Alle Modelle erkannten die Frage außerhalb der Quellen.

## Entscheidung

- Automatischer Fallback innerhalb von Mistral: `MISTRAL_MODEL` (Standard `ministral-14b-latest`)
  → `MISTRAL_FALLBACK_MODEL` (Standard `ministral-8b-latest`, leer = aus).
- Das Primärmodell bekommt dann nur 2 Versuche mit maximal 3 s Wartezeit, damit der Fallback
  schnell greift; das Ersatzmodell behält die normalen 4 Versuche.
- `FallbackProvider` ist generisch (Liste von Providern) und protokolliert jeden Wechsel.
- Ollama bleibt ein **manueller** Schalter (`LLM_PROVIDER=ollama`) für Umgebungen mit GPU oder
  Daten, die das Haus nicht verlassen dürfen – nicht als automatischer Fallback.

## Konsequenzen

- Das Ersatzmodell hat ein eigenes Kontingent (im Demo-Workspace 188 statt 30 Anfragen/Minute)
  und braucht keine zusätzliche Infrastruktur.
- Fällt die Mistral-API komplett aus, hilft der Fallback nicht; die UI zeigt dann den Fehler mit
  „Erneut senden“. Das ist für eine Demo akzeptabel.
- Auf dem VPS ohne GPU würde ein lokales Modell eine Antwort erst nach 1–2 Minuten liefern und
  Zitate unzuverlässig setzen – im Live-Test schlechter als eine klare Fehlermeldung.

## Verworfene Alternativen

- Ollama als automatischer Fallback auf dem VPS: zu langsam auf CPU, schwache Zitierdisziplin,
  zusätzlich 2–5 GB RAM neben Postgres und Embedding-Modell.
- Ollama auf einem separaten GPU-Server (Split-Deployment): sinnvoll für Produktivbetrieb mit
  sensiblen Daten, für die Demo zu viel Betriebsaufwand.
