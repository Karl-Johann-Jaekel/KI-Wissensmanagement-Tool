# ADR-03: Generierung über Mistral mit austauschbarem Provider

Status: angenommen

## Kontext

Für Quellen-Guide und Chat wird ein LLM gebraucht, das Deutsch gut beherrscht, JSON zuverlässig
ausgibt und für die Demo nichts kostet. Für einen späteren Produktivbetrieb soll ein Wechsel
(Paid-Tier, selbst gehostet) ohne Codeänderung möglich sein.

## Entscheidung

- Standard: Mistral La Plateforme, `ministral-14b-latest`, Temperatur 0.2 (ursprünglich
  `mistral-small-latest`, siehe Nachtrag).
- Schmale Schnittstelle `LLMProvider.complete(messages, json_mode, ...)` mit zwei
  Implementierungen: `MistralProvider` und `OllamaProvider`. Auswahl per `LLM_PROVIDER` in `.env`.
- HTTP direkt über `httpx` (bereits vorhanden) statt Hersteller-SDK — eine Abhängigkeit weniger,
  beide APIs sind simple JSON-Endpunkte.
- Retry mit exponentiellem Backoff bei 429 und 5xx, `Retry-After` wird respektiert.

## Konsequenzen

- Free Tier ist rate-limitiert und Mistral darf Eingaben dort zur Modellverbesserung nutzen →
  Demo ausschließlich mit öffentlichen Dokumenten.
- Für Produktivbetrieb: Paid-Tier-Key oder Ollama auf GPU-Host (Wechsel = `.env` ändern und
  Container neu starten).
- Tests nutzen einen Fake-Provider; kein Test ruft die echte API.

## Nachtrag: Modellwahl im Free-Tier

Das Kontingent ist pro Modell vergeben. Im Demo-Workspace lieferten `mistral-small-latest`,
`mistral-medium-latest` und `magistral-*` `x-ratelimit-limit-req-minute: 0`,
`mistral-large-latest` war nicht im Tarif. Kontingent hatten Ministral 3B/8B/14B und Codestral.

Qualitätstest mit dem Transformer-Paper (Guide, 3 Sachfragen, 3 Fragen außerhalb der Quellen):

| Modell | Sachfragen | Außerhalb der Quellen | Limit |
|---|---|---|---|
| `ministral-14b-latest` | alle korrekt, Seiten stimmen, nennt Details (Adam-Parameter) | nach Prompt-Schärfung ohne Zitatnummern | 30 req/min |
| `ministral-8b-latest` | korrekt, etwas knapper | korrekt | 188 req/min |

Entscheidung: `ministral-14b-latest`. 30 Anfragen/Minute reichen für eine Demo (ein Aufruf pro
Antwort, höchstens neun pro Quellen-Guide). Beim Test hängte 14B vor der Prompt-Schärfung alle
acht Nummern an „keine Angaben“; der Zitat-Parser verwirft deshalb zusätzlich Folgen von mehr als
drei Belegen an einer Stelle ([ADR-05](005-validated-citations.md)).

## Verworfene Alternativen

- OpenAI / Anthropic: US-Anbieter, für eine EU-Demo mit kostenlosem Zugang ungeeignet.
- Nur Ollama: ohne GPU zu langsam für einen flüssigen Live-Test.
- `mistralai`-SDK / LangChain: zusätzliche Abhängigkeiten ohne funktionalen Gewinn.
