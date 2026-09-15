# Notebook – ein NotebookLM-Klon

Quellen hochladen, Fragen stellen, Antworten **ausschließlich aus den Quellen** erhalten – jede
Aussage mit einem klickbaren Beleg, der die Originalpassage öffnet.

Entstanden als Bewerbungsaufgabe in einer 3-Tage-Zeitbox. Vorgehen und Status: [plan.md](plan.md),
Entscheidungen: [docs/adr/](docs/adr/README.md), Arbeit mit AI-Tools: [docs/prompts.md](docs/prompts.md).

![Notebook mit Quellen-Guide, Chat mit Belegen und gespeicherter Notiz](docs/screenshots/notebook.png)

<sub>Echter Durchlauf mit `ministral-14b-latest` und dem Paper „Attention Is All You Need“ (arXiv 1706.03762).</sub>

## Funktionen

| Bereich | Umfang |
|---|---|
| Notebooks | anlegen, umbenennen, löschen |
| Quellen | PDF (mit Textebene), TXT, Markdown, Webseiten-Import; Verarbeitung im Hintergrund mit Statusanzeige |
| Quellen-Guide | automatische Zusammenfassung, Kernthemen und drei Fragevorschläge je Quelle |
| Chat | Antworten nur aus den Quellen, Inline-Zitate `[1]`, expliziter Hinweis, wenn die Quellen nichts hergeben |
| Zitat-Viewer | Klick auf ein Zitat zeigt die Passage hervorgehoben, mit Quelle, Seite und Nachbarabschnitten |
| Quellen-Filter | pro Quelle wählbar, ob sie in Antworten einfließt |
| Notizen | Antwort als Notiz speichern (inkl. Quellenliste), eigene Notizen, bearbeiten, löschen |
| Zugang | ein gemeinsamer Access-Key für die Demo-Instanz |

Bewusst nicht enthalten: Audio Overview, Mind Map, YouTube/Audio-Quellen, Multi-User.

| Zitat-Viewer | Dunkelmodus | Mobil |
|---|---|---|
| ![Klick auf ein Zitat öffnet die hervorgehobene Passage](docs/screenshots/citation.png) | ![Dunkelmodus](docs/screenshots/dark.png) | <img src="docs/screenshots/mobile.png" alt="Mobile Ansicht mit Tabs" width="220"> |

## Architektur

```mermaid
flowchart LR
  B[Browser] --> N[nginx<br/>React-Build + /api-Proxy]
  N --> A[FastAPI]
  A --> P[(Postgres 17<br/>pgvector + Volltext)]
  A --> E[fastembed<br/>multilingual-e5-small, CPU]
  A --> L[LLM-Provider<br/>Mistral | Ollama]
```

**Ingestion** (Hintergrundjob): Parsen (pypdf / trafilatura) → Chunking an Absatzgrenzen, nie über
Seitengrenzen → lokale Embeddings → Speichern → Quelle ist chatbar → Quellen-Guide per LLM
(Map-Reduce bei langen Quellen, eigener Status, bei Fehler neu anstoßbar).

**Chat**: Frage einbetten → Top-20 Vektor + Top-20 Volltext, gefiltert auf die gewählten Quellen →
Reciprocal Rank Fusion → Top-8 nummerierte Passagen an das LLM → das Backend validiert jedes `[n]`,
entfernt erfundene Nummern, nummeriert neu und liefert Chunk-IDs für den Zitat-Viewer.

| Entscheidung | ADR |
|---|---|
| Hybrid Retrieval statt reiner Vektorsuche | [ADR-04](docs/adr/004-hybrid-retrieval-rrf.md) |
| Zitate als validierte Passagen-Nummern | [ADR-05](docs/adr/005-validated-citations.md) |
| Lokale Embeddings, EU-LLM mit Provider-Switch | [ADR-02](docs/adr/002-local-embeddings.md), [ADR-03](docs/adr/003-llm-provider-mistral.md) |
| Fallback auf zweites Mistral-Modell statt Ollama (mit Messung) | [ADR-09](docs/adr/009-llm-fallback.md) |

## Lokal starten

Voraussetzung: Docker mit Compose.

```bash
cp .env.example .env          # ACCESS_KEY, POSTGRES_PASSWORD und MISTRAL_API_KEY setzen
docker compose up -d --build  # erster Build lädt das Embedding-Modell (~470 MB)
open http://localhost:8080    # Windows: start http://localhost:8080
```

Das Frontend fragt nach dem `ACCESS_KEY` aus der `.env`. Ohne gültigen Mistral-Key funktionieren
Upload, Suche und Zitat-Viewer; Guide und Chat melden den Fehler sichtbar.

Demo-Notebook „KI im Unternehmen: Recht & Verträge“ (KI-Verordnung, DSK-Leitlinie zu RAG,
KI-Vertragsklauseln, Mustervertrag) anlegen und geprüfte Demo-Fragen: [demo/README.md](demo/README.md).

Frontend-Entwicklung mit Hot-Reload: `cd frontend && npm install && npm run dev` (Vite auf
Port 5173, `/api` wird an `BACKEND_PORT` weitergeleitet).

## Konfiguration

Alle Werte in [.env.example](.env.example). Die wichtigsten:

| Variable | Zweck |
|---|---|
| `ACCESS_KEY` | gemeinsamer Zugangsschlüssel, mindestens 12 Zeichen |
| `LLM_PROVIDER` | `mistral` (Standard) oder `ollama` |
| `MISTRAL_API_KEY`, `MISTRAL_MODEL` | La Plateforme, Standard `ministral-14b-latest` (Free-Tier-Kontingent ist pro Modell, siehe ADR-03) |
| `MISTRAL_FALLBACK_MODEL` | springt ein, wenn das Hauptmodell limitiert ist; Standard `ministral-8b-latest`, leer = aus ([ADR-09](docs/adr/009-llm-fallback.md)) |
| `FRONTEND_PORT` | Host-Port des Frontends, nur an `127.0.0.1` gebunden |
| `CHUNK_MAX_CHARS`, `RETRIEVAL_TOP_K` | Chunk-Größe und Anzahl Passagen pro Antwort |

## Tests

```bash
docker compose exec backend pytest                      # Fake-LLM + Fake-Embedder, eigene Test-DB
docker compose exec backend ruff check . && docker compose exec backend mypy app
cd frontend && npm run build && npm run lint
```

### Browser-E2E

Klickt den Kern-Workflow im echten Browser durch (Upload → Guide → Frage → Zitat → Notiz,
Quellenfilter, SSRF-Block, Dark Mode, Mobil-Layout) und schlägt bei jeder Console-Warnung fehl.
Ein Mock-LLM spricht die Mistral-API, es wird kein Kontingent verbraucht.

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml -f e2e/docker-compose.e2e.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.override.yml -f e2e/docker-compose.e2e.yml run --rm e2e
docker compose up -d --remove-orphans   # danach zurück zur normalen Konfiguration
```

Beim ersten Lauf wird das Transformer-Paper (arXiv 1706.03762) als Test-PDF geladen; Screenshots
liegen anschließend in `e2e/out/`. Mit `E2E_IMPORT_URL=https://…` wird zusätzlich der URL-Import
getestet.

## Projektstruktur

```
backend/app/
  ingest/      parsers.py, url.py (SSRF-Schutz), chunker.py, guide.py, pipeline.py
  retrieval/   embed.py, text_query.py, search.py, rrf.py
  llm/         provider.py (Mistral | Ollama, Retry), prompts.py
  routers/     notebooks, sources, chat, notes
  citations.py Parsing und Validierung der [n]-Marker
frontend/src/  App.tsx, api.ts, components/ (SourcePanel, ChatPanel, NotesPanel, CitationDrawer, …)
e2e/           Playwright-Test + Mock-LLM
demo/          Seed-Skript und Demo-Fragen
docs/adr/      Architekturentscheidungen
```
