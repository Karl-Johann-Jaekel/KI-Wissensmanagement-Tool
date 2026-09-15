# ADR-01: FastAPI + React/Vite + Postgres/pgvector in einem Docker Compose

Status: angenommen

## Kontext

Zeitbox 3 Tage. Der Klon braucht Datei-Upload, Hintergrundverarbeitung, Vektorsuche und eine
interaktive Oberfläche. Lokale Entwicklung und Produktion sollen sich nicht unterscheiden.

## Entscheidung

- Backend FastAPI mit **synchronen** Handlern (laufen im Threadpool, kein blockierender I/O im
  Event-Loop), SQLAlchemy 2 + psycopg 3, Schema über Alembic-Migrationen.
- Postgres 17 mit pgvector als einzige Datenhaltung (Metadaten, Volltextindex, Vektoren).
- Frontend React + Vite + TypeScript + Tailwind, im Container von nginx ausgeliefert; nginx
  proxied `/api` ans Backend → eine Origin, kein CORS.
- Ingestion läuft als FastAPI-`BackgroundTask` im Backend-Prozess. Beim Start werden hängen
  gebliebene `processing`-Quellen auf `error` gesetzt.
- `docker-compose.yml` beschreibt Produktion; `docker-compose.override.yml` ergänzt lokal
  Hot-Reload und Ports.

## Konsequenzen

- Ein `docker compose up` startet alles; keine externe Queue, kein separater Vektor-Store.
- In-Process-Hintergrundjobs gehen bei Neustart verloren (bewusst akzeptiert, Status wird sichtbar
  als Fehler markiert). Für Mehrbenutzerbetrieb wäre eine Queue (z. B. arq/Redis) nötig.

## Verworfene Alternativen

- Next.js + Supabase: neuer Stack, Lernkurve frisst Zeitbox.
- Separater Vektor-Store (Qdrant, Chroma): zweite Datenhaltung ohne Mehrwert bei Demo-Datenmengen.
- Celery/Redis-Queue: Betriebsaufwand für eine Demo mit 2–3 Nutzern nicht gerechtfertigt.
