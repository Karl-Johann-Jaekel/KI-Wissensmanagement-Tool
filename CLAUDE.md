# CLAUDE.md — Notebook (NotebookLM-Klon)

Bewerbungsprojekt. Gesamtplan und Phasen: [plan.md](plan.md). Entscheidungen: [docs/adr/](docs/adr/).

## Stack

- Backend: FastAPI (sync-Handler, Threadpool), SQLAlchemy 2 + psycopg 3, Alembic, Postgres 17 + pgvector
- Embeddings: fastembed, `intfloat/multilingual-e5-small` (384 d, lokal, CPU) — Präfixe `query:` / `passage:`
- LLM: Provider-Abstraktion `backend/app/llm/provider.py` (`mistral` | `ollama`), Wahl per `LLM_PROVIDER`
- Frontend: React + Vite + TypeScript + Tailwind v4, ausgeliefert über nginx (`/api` → backend)

## Befehle

```bash
cp .env.example .env                     # Werte setzen (MISTRAL_API_KEY, ACCESS_KEY)
docker compose up -d --build             # Dev: override-Datei mountet Code, Hot-Reload
docker compose exec backend pytest       # Tests (nutzen Fake-LLM + Fake-Embedder, eigene Test-DB)
docker compose exec backend ruff check . && docker compose exec backend ruff format --check .
docker compose exec backend mypy app
cd frontend && npm install && npm run build   # Typecheck + Build
cd frontend && npm run dev               # Vite auf :5173, Proxy /api → localhost:${BACKEND_PORT}
```

## Konventionen

- Code, Kommentare, Commit-Subjects englisch; Doku deutsch.
- Conventional Commits, ein Schritt pro Commit, Branch `feat/*`, Merge ohne Squash.
- **Keine neue Abhängigkeit ohne ADR** in `docs/adr/`.
- SQL nur als feste, parametrisierte Funktionen (`app/retrieval/search.py`, Router). Schemaänderung = Alembic-Migration.
- Neue Env-Variable → `app/config.py` **und** `.env.example` im selben Commit.
- Tests nie gegen echte externe APIs (Mistral, URLs) — Fakes in `backend/tests/fakes.py`.
- `.env` nicht lesen, nicht committen.

## Definition of Done

- `pytest`, `ruff check`, `ruff format --check`, `mypy app` grün; `npm run build` ohne Fehler
- Feature einmal real durchgeklickt bzw. per `curl` ausgeführt
- Status in `plan.md` §11 bei Phasenabschluss aktualisiert
