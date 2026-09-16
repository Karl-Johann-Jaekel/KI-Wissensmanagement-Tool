# Architecture Decision Records

Kurze ADRs nach dem Schema Kontext → Entscheidung → Konsequenzen → verworfene Alternativen.

| # | Titel | Status |
|---|---|---|
| [ADR-01](001-stack-fastapi-react-postgres.md) | FastAPI + React/Vite + Postgres/pgvector in einem Docker Compose | angenommen |
| [ADR-02](002-local-embeddings.md) | Embeddings lokal auf CPU mit multilingual-e5-small | angenommen |
| [ADR-03](003-llm-provider-mistral.md) | Generierung über Mistral mit austauschbarem Provider | angenommen |
| [ADR-04](004-hybrid-retrieval-rrf.md) | Hybrid Retrieval (Volltext + Vektor) mit RRF | angenommen |
| [ADR-05](005-validated-citations.md) | Zitate als validierte Passagen-Nummern | angenommen |
| [ADR-06](006-deployment-vps.md) | Deployment auf bestehendem VPS hinter Caddy | angenommen |
| [ADR-07](007-access-key.md) | Access-Key statt Auth-System | angenommen |
| [ADR-08](008-pdf-parsing-pypdf.md) | PDF-Parsing mit pypdf statt PyMuPDF | angenommen |
| [ADR-09](009-llm-fallback.md) | LLM-Fallback innerhalb von Mistral statt Ollama | angenommen |
| [ADR-10](010-streaming-answers.md) | Antworten streamen, Zitate weiterhin am Ende validieren | angenommen |
| [ADR-11](011-note-citations.md) | Notizen behalten die Belege der gespeicherten Antwort | angenommen |
| [ADR-12](012-notebook-overview.md) | Notebook-Überblick aus den Quellen-Guides, nicht aus dem Volltext | angenommen |
| [ADR-13](013-briefing-document.md) | Berichte als Kette gewöhnlicher, belegter Antworten | angenommen |
