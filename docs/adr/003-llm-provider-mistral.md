# ADR-03: Generierung über Mistral mit austauschbarem Provider

Status: angenommen

## Kontext

Für Quellen-Guide und Chat wird ein LLM gebraucht, das Deutsch gut beherrscht, JSON zuverlässig
ausgibt und für die Demo nichts kostet. Für einen späteren Produktivbetrieb soll ein Wechsel
(Paid-Tier, selbst gehostet) ohne Codeänderung möglich sein.

## Entscheidung

- Standard: Mistral La Plateforme, `mistral-small-latest`, Temperatur 0.2.
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

## Verworfene Alternativen

- OpenAI / Anthropic: US-Anbieter, für eine EU-Demo mit kostenlosem Zugang ungeeignet.
- Nur Ollama: ohne GPU zu langsam für einen flüssigen Live-Test.
- `mistralai`-SDK / LangChain: zusätzliche Abhängigkeiten ohne funktionalen Gewinn.
