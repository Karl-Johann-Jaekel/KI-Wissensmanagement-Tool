# plan.md — NotebookLM-Klon ("Notebook")

Bewerbungsaufgabe · Zeitbox: 3 Tage · Abgabe: GitHub-Repo, Live-URL, Loom (≤ 10 min)

---

## 1. Ziel und Bewertungslogik

Was der Klon zeigen muss (Kern von NotebookLM):

1. Quellen hochladen → System versteht sie (Quellen-Guide)
2. Fragen stellen → Antworten **ausschließlich aus den Quellen**, mit **klickbaren Zitaten**
3. Antworten festhalten (Notizen)

Was die Prüfer zusätzlich sehen wollen: nachvollziehbares Vorgehen (Commit-Historie, Doku, AI-Tool-Nutzung), stabiler Live-Test.

Leitprinzip: **lieber 3 Features fehlerfrei als 8 halb.** Alles, was im Live-Test brechen kann, wird gestrichen oder bekommt einen Fallback.

---

## 2. Scope

### In Scope (Core-Loop)

| Feature | Beschreibung |
|---|---|
| Notebooks | Anlegen, umbenennen, löschen; ein Notebook = ein Quellen-Set |
| Quellen | Upload PDF, TXT, MD; URL-Import (Artikel-Text) |
| Quellen-Guide | Beim Upload automatisch: Zusammenfassung, 3–5 Kernthemen, 3 Fragevorschläge |
| Chat | Frage → Antwort mit Inline-Zitaten `[1]`, `[2]` … |
| Zitat-Viewer | Klick auf `[n]` öffnet die Originalpassage (Quelle, Seite, Chunk hervorgehoben) |
| Quellen-Filter | Checkboxen: welche Quellen in die Antwort einfließen |
| Notizen | Antwort als Notiz speichern; Notizen bearbeiten/löschen |
| Zugriffsschutz | Ein Access-Key (`.env`) für die Demo-Instanz |

### Out of Scope (bewusst, im Loom benennen)

Audio Overview, Mind Map, YouTube/Audio-Quellen, Google-Docs-Import, Multi-User/Sharing, Studio-Generatoren (FAQ, Timeline …). Falls Tag 3 Luft lässt: Briefing-Doc-Generator als einziger Bonus.

---

## 3. Architektur-Entscheidungen (Kurz-ADRs)

| # | Entscheidung | Begründung | Alternative verworfen |
|---|---|---|---|
| ADR-01 | FastAPI + React/Vite + Postgres/pgvector, ein Docker Compose | Bekannter Stack, keine Lernkurve, `docker compose up` = lokal = Produktion | Next.js/Supabase (neuer Stack, Zeitrisiko) |
| ADR-02 | Embeddings **lokal** auf CPU (`intfloat/multilingual-e5-small` via fastembed/ONNX) | Kein Rate-Limit, 0 €, DE/EN-Korpus, läuft auf kleinem VPS | mistral-embed (Free-Tier-Limits beim Bulk-Upload) |
| ADR-03 | Generierung: Mistral La Plateforme Free Tier (`mistral-small-latest`), Provider-Abstraktion mit `.env`-Switch | EU-Provider, DPA, kostenlos für Demo, später auf Paid/Ollama umschaltbar | OpenAI/Anthropic (US), Ollama (GPU nötig) |
| ADR-04 | Hybrid Retrieval: `tsvector` (BM25-ähnlich) + Vektor, Fusion per RRF | Robust bei Eigennamen/Fachbegriffen — fällt im Live-Test sonst auf | Vektor-only; Long-Context-Stuffing |
| ADR-05 | Zitate = Chunk-IDs; Modell antwortet mit `[n]`, Backend validiert und mappt | Verifizierbare Zitate, kein Halluzinieren von Quellen | Modell nennt Quellennamen frei |
| ADR-06 | Deployment auf bestehendem VPS unter `notebook.jaekel.dev` | Vorhandene Infra, Portfolio-Integration, EU | Railway/Vercel (zusätzliche Accounts, US) |
| ADR-07 | Kein Auth-System, nur Access-Key | Demo für 2–3 Personen; Keycloak wäre Overkill | Magic Link, Keycloak |

Hinweis Free Tier: Mistral Free Tier ist rate-limitiert und die Daten dürfen laut deren Bedingungen zur Modellverbesserung genutzt werden → Demo nur mit öffentlichen Dokumenten; im Loom als bewusste Entscheidung erwähnen ("für Produktivbetrieb: Paid Tier oder Ollama, Split-Deployment wie in meinem Hive-Mind-Projekt").

---

## 4. Systemaufbau

```
Browser ──> Caddy/Reverse Proxy (TLS) ──> frontend (nginx, React build)
                                      └──> backend  (FastAPI, uvicorn)
                                                 ├── postgres (pgvector)
                                                 ├── fastembed (lokal, CPU)
                                                 └── Mistral API (Generierung)
```

### Repo-Struktur

```
notebook-clone/
├── README.md              # Setup, Architektur-Skizze, Screenshots, Live-Link
├── plan.md                # diese Datei
├── CLAUDE.md              # Kontext für Claude Code (Stack, Konventionen, DoD)
├── docs/adr/              # ADR-01 … ADR-07 als je eine Datei
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py      # SQLAlchemy
│   │   ├── routers/       # notebooks, sources, chat, notes
│   │   ├── ingest/        # parsers (pdf, text, url), chunker
│   │   ├── retrieval/     # embed, hybrid_search, rrf
│   │   ├── llm/           # provider.py (Mistral | Ollama), prompts.py
│   │   └── citations.py   # [n]-Parsing + Validierung
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/    # SourcePanel, ChatPanel, NotesPanel, CitationDrawer
│   │   ├── api.ts
│   │   └── App.tsx        # 3-Spalten-Layout
│   └── Dockerfile
└── demo/                  # Fallback-Quellen für den Live-Test
```

### Datenmodell

```sql
notebooks(id, title, created_at)
sources(id, notebook_id, title, type[pdf|text|url], status[processing|ready|error],
        summary, key_topics jsonb, suggested_questions jsonb, page_count, created_at)
chunks(id, source_id, ordinal, page, content, tsv tsvector, embedding vector(384))
messages(id, notebook_id, role[user|assistant], content, citations jsonb, created_at)
notes(id, notebook_id, title, content, created_at, updated_at)

-- Indizes: GIN auf chunks.tsv; HNSW (cosine) auf chunks.embedding
```

### API

```
POST   /notebooks                       GET /notebooks          DELETE /notebooks/{id}
POST   /notebooks/{id}/sources          (multipart file | {url})
GET    /notebooks/{id}/sources          DELETE /sources/{id}
GET    /sources/{id}/chunks/{chunk_id}  (für Zitat-Viewer)
POST   /notebooks/{id}/chat             {question, source_ids[]} → {answer, citations[]}
GET    /notebooks/{id}/messages
POST   /notebooks/{id}/notes            PATCH /notes/{id}       DELETE /notes/{id}
GET    /health
```

Alle Routen hinter `X-Access-Key`-Header (Middleware).

---

## 5. Pipelines

### Ingestion (beim Upload)

1. Parsen: PDF → pypdf (Seitenzahlen behalten; statt PyMuPDF wegen Lizenz, siehe ADR-08); TXT/MD → direkt; URL → trafilatura
2. Chunking: ~500 Tokens, 80 Overlap, Absatzgrenzen bevorzugen; Seite pro Chunk mitführen
3. Embedding lokal (Batch), `tsvector` per DB-Trigger
4. Quellen-Guide: Map-Reduce-Summary (bei > 8 Chunks erst Chunk-Summaries, dann Gesamt) → JSON `{summary, key_topics[], suggested_questions[]}`
5. Status `ready`; Frontend pollt `/sources`

### Chat

1. Frage embedden; Kandidaten: Top-20 Vektor + Top-20 `ts_rank` (gefiltert auf `source_ids`)
2. RRF-Fusion → Top-8 Chunks
3. Prompt (System): "Antworte nur aus den nummerierten Passagen. Jede Aussage mit `[n]`. Wenn die Passagen die Frage nicht beantworten, sage das explizit." Passagen als `[1] (Quelle: …, S. x) …`
4. Antwort parsen: alle `[n]` extrahieren, gegen Kandidatenliste validieren, ungültige entfernen
5. Response: `{answer, citations: [{n, chunk_id, source_id, source_title, page, snippet}]}`
6. Frontend rendert `[n]` als Chip → Klick öffnet CitationDrawer mit Volltext des Chunks, Passage hervorgehoben

---

## 6. Phasenplan (3 Tage)

### Tag 1 — Backend-Kern und Ingestion

- Repo, CLAUDE.md, docker-compose (backend, frontend-stub, postgres/pgvector), `.env.example`
- Schema + Migration, SQLAlchemy-Modelle
- Ingestion-Pipeline komplett (PDF/TXT/MD/URL → Chunks → Embedding → Guide)
- LLM-Provider-Abstraktion (Mistral, Ollama-Stub)
- **DoD:** `curl`-Upload eines PDFs → Chunks mit Embeddings in DB, Quellen-Guide als JSON abrufbar; 2 Tests (Chunker, Zitat-Parser)

### Tag 2 — Chat, Zitate, UI

- Hybrid Retrieval + RRF, Chat-Endpoint, Zitat-Validierung
- React: 3-Spalten-Layout (Quellen | Chat | Notizen), Upload-Dialog mit Status, Quellen-Guide-Karte, Chat mit Zitat-Chips, CitationDrawer, Notizen-CRUD, Quellen-Checkboxen
- **DoD:** End-to-End lokal: Upload → Frage → Antwort mit klickbaren Zitaten → Notiz gespeichert. Kein Console-Error.

### Tag 3 — Deployment, Absicherung, Abgabe

- Vormittag: Deployment auf VPS (`notebook.jaekel.dev`), Reverse-Proxy-Eintrag, TLS, Access-Key, Smoke-Test
- Mittag: `demo/`-Notebook mit 3 öffentlichen Quellen vorindiziert (Fallback); README mit Architektur-Skizze, Screenshots, Live-Link; ADRs finalisieren; Repo aufräumen (Squash nur, wenn Historie unleserlich — sonst behalten, sie ist Teil der Bewertung)
- Nachmittag: Loom aufnehmen (max. 2 Takes), E-Mail schicken
- **DoD:** Live-URL funktioniert aus fremdem Netz, Loom < 10 min, Mail raus

Puffer: Wenn Tag 2 überläuft, fällt der Quellen-Filter (Checkboxen) zuerst, dann Notizen-Bearbeitung. Zitate fallen nie.

---

## 7. Vorgehen mit AI-Tools (Teil der Bewertung)

- Claude Code als primäres Werkzeug; CLAUDE.md enthält Stack, Konventionen, DoD pro Phase, "no new dependencies without ADR"
- Ein Commit pro abgeschlossenem Schritt, Conventional Commits (`feat(ingest): pdf parser with page tracking`)
- Jede nicht-triviale Entscheidung als ADR — auch die, die gegen etwas entscheiden
- Prompts, die Architektur geprägt haben, in `docs/prompts.md` festhalten (kurz) → im Loom zeigbar
- Review-Regel: kein AI-generierter Code ohne Ausführung + Lesen; Tests für Chunker und Zitat-Parser sind Pflicht

---

## 8. Risiken und Fallbacks

| Risiko | Wahrscheinlichkeit | Gegenmaßnahme |
|---|---|---|
| Mistral Free-Tier Rate-Limit während Live-Demo | mittel | Retry mit Backoff; Paid-Key als `.env`-Fallback bereithalten (Wechsel = Neustart Container) |
| Modell zitiert falsch/erfindet `[n]` | mittel | Validierung entfernt ungültige Marker; Prompt mit Beispiel; Temperatur 0.2 |
| PDF-Parsing bei gescannten/komplexen PDFs | mittel | Nur Text-PDFs; Fehlerstatus sauber anzeigen; Demo-Quellen vorab getestet |
| Embedding-Modell-Download beim ersten Start zu langsam | niedrig | Im Docker-Build vorladen |
| VPS-Ressourcen (RAM) mit fastembed + Postgres | niedrig | e5-small ist ~120 MB; Compose-Memory-Limits setzen |
| Upload im Live-Test dauert zu lang | mittel | Kleines PDF (5–10 Seiten) hochladen, parallel im vorindizierten Notebook zeigen |
| Loom zu lang | hoch | Skript mit Zeitmarken, Timer sichtbar |

---

## 9. Loom-Skript (Ziel 8 min)

| Zeit | Inhalt |
|---|---|
| 0:00–1:00 | Aufgabe, meine Interpretation: Kern = grounded Q&A mit verifizierbaren Zitaten; bewusster Scope |
| 1:00–3:00 | Vorgehen: plan.md → ADRs → Claude Code mit CLAUDE.md → Commits; kurz Repo und Commit-Historie zeigen |
| 3:00–4:00 | Architektur (README-Skizze): Ingestion, Hybrid Retrieval, Zitat-Validierung, Provider-Switch |
| 4:00–7:30 | **Live-Test**: Notebook anlegen → PDF hochladen → Guide erscheint → Frage stellen → Zitat anklicken → Frage außerhalb der Quellen (zeigt "nicht in den Quellen") → Notiz speichern |
| 7:30–8:30 | Was ich weggelassen habe und warum; was ich als Nächstes bauen würde (Audio Overview, Split-Deployment mit Ollama, Multi-User) |
| 8:30–9:00 | Learnings, Danke |

Vorbereitung: Browser-Tab mit vorindiziertem Demo-Notebook offen, zweiter Tab leer für den Live-Upload, Terminal mit `git log --oneline`.

---

## 10. Abgabe-Checkliste

- [ ] Repo public, README mit Live-Link, Setup in 3 Befehlen, Architektur-Skizze, Screenshots
- [ ] `.env.example` vollständig, keine Secrets im Repo (`git log -p | grep -i key` prüfen)
- [ ] Live-URL aus Mobilfunknetz getestet, Access-Key in der Mail
- [ ] `docs/adr/` mit 7 ADRs, `plan.md`, `CLAUDE.md` im Repo
- [ ] Tests grün (`pytest`), Frontend-Build ohne Warnungen
- [ ] Loom < 10 min, Link geprüft (öffentlich/mit Link zugänglich)
- [ ] Antwort-Mail: Repo-Link, Live-Link + Access-Key, Loom-Link, 3 Sätze zu Scope-Entscheidung

---

## 11. Status

| Phase | Stand |
|---|---|
| Tag 1 — Backend-Kern und Ingestion | erledigt: 15-seitiges PDF → 34 Chunks mit Embeddings (~12 s); Tests für Chunker, Parser, Zitat-Parser, Provider, API. Offen: Guide mit echtem Mistral (Workspace-Kontingent war 0 req/min, Fallback greift). Abweichungen: pypdf (ADR-08), Guide-Status separat (Migration 0002), URL-Import als eigener Endpoint `POST /notebooks/{id}/sources/url` |
| Tag 2 — Chat, Zitate, UI | erledigt: Hybrid Retrieval + RRF, Chat mit Zitat-Validierung, 3-Spalten-UI (mobil als Tabs, Hell/Dunkel), Zitat-Viewer, Quellenfilter, Notizen. 81 Backend-Tests; Browser-E2E des gesamten Core-Loops ohne Console-Fehler (mit Mock-LLM). Nachtrag: Browser-Durchlauf mit echtem Mistral (`ministral-14b-latest`) grün – PDF nach ~13 s bereit, Guide nach ~29 s, Fakten und Seiten korrekt, Frage außerhalb der Quellen ohne Belege; dabei Zitat-Dumping und Markdown im Guide gefunden und behoben. README-Screenshots aus diesem Lauf |
| Tag 3 — Deployment, Abgabe | teilweise: Demo-Notebook „KI im Unternehmen: Recht & Verträge“ per `demo/seed.py` (4 öffentliche Quellen), LLM-Fallback auf zweites Mistral-Modell nach Ollama-Benchmark (ADR-09), Quellen umbenennbar. Deployment live unter https://notebook.jaekel.dev: gemeinsamer Caddy übernimmt TLS, kein Container hat einen Host-Port (ADR-06 im Nachtrag korrigiert). Gegen die Live-Instanz geprüft: Upload → Guide → Frage mit Beleg → Zitat-Viewer, Frage außerhalb der Quellen ohne Beleg, 401 ohne Access-Key. Demo-Notebook auf Prod geseedet (293 s, 666 Abschnitte). Dabei gefunden: Backend-Peak 1,95 GiB gegen 2-GiB-Limit → Limit auf 3 GiB. Offen: Loom, Abgabe-Mail |
| Nachgelegt — UI-Feinschliff | Streaming der Antworten per SSE (ADR-10; erstes Zeichen nach 0,29 s statt 5–15 s, über nginx gemessen), native Browserdialoge durch eigene ersetzt, Vorschaukarte beim Überfahren eines Belegs, Fragevorschläge reihum über alle Quellen statt drei aus der ersten, Antwort kopierbar. 116 Backend-Tests, Browser-E2E grün inklusive Wächter gegen native Dialoge |
| Nachgelegt — Überblick und Briefing | Notebook-Überblick über alle Quellen (ADR-12, Migration 0004): eine LLM-Anfrage über die vorhandenen Quellen-Guides, unabhängig von der Notebook-Größe, wird nach jedem Guide und nach jedem Löschen neu gebaut. Briefing-Doc (ADR-13) — der in §2 vorgesehene Bonus: beantwortet die Kernfragen über den normalen Chat-Pfad und legt das Ergebnis als belegte Notiz ab, mit dokumentweiter Zitat-Nummerierung. 126 Backend-Tests, Browser-E2E 19 Schritte grün |
| Nachgelegt — Guide und Notizen | Quellen-Guide öffnet in der Hauptspalte statt die 18-rem-Seitenspalte zu füllen; die Liste bleibt kompakt, der Chat bleibt dabei montiert (laufende Antwort überlebt den Blick in eine Quelle). Notizen behalten die Belege der gespeicherten Antwort (ADR-11, Migration 0003); der Zitat-Viewer erklärt auf Deutsch, wenn die Quelle inzwischen gelöscht wurde. 119 Backend-Tests, Browser-E2E grün |
