# Arbeiten mit AI-Tools

Primäres Werkzeug: **Claude Code** im Repo, gesteuert über [CLAUDE.md](../CLAUDE.md) (Stack,
Befehle, Definition of Done) und [plan.md](../plan.md). Diese Datei hält fest, welche Prompts und
Rückfragen die Architektur geprägt haben und wo die Umsetzung vom Plan abwich.

## Ablauf

| Schritt | Mensch | AI |
|---|---|---|
| Planung | Aufgabe interpretiert, Scope, Stack und 7 ADRs in `plan.md` festgelegt | – |
| Start | Prompt: *„Bitte hilf mir, diesen Plan in diesem Repo in die Tat umzusetzen.“* (plus Aufgabentext und `plan.md`) | Rückfragen gestellt, bevor Code entstand |
| Umsetzung | Entscheidungen beantwortet, Zwischenstände geprüft | Code, Tests, Commits pro Schritt |
| Verifikation | – | nach jedem Schritt `pytest`, `ruff`, `mypy`, Build; reale Läufe mit echtem PDF und Browser |

## Rückfragen vor dem ersten Commit

| Frage der AI | Antwort | Wirkung |
|---|---|---|
| Wie committen, wenn die Historie bewertet wird? | Branch + ein Commit pro verifiziertem Schritt, Merge ohne Squash | kleine Conventional Commits auf `feat/mvp` |
| Ist ein Mistral-Key vorhanden? | ja, wird in `.env` eingetragen | AI liest `.env` nie; Tests nutzen Fakes |
| Welcher Umfang in dieser Session? | Tag 1 + 2 lokal, Deployment erst nach Freigabe | kein Push, kein Deploy ohne Rückfrage |

## Befunde, die den Plan verändert haben

| Befund | Wie entdeckt | Entscheidung |
|---|---|---|
| fastembed 0.8 kennt `multilingual-e5-small` nicht | Modellliste im Container abgefragt, bevor ADR-02 geschrieben wurde | als Custom-Model registriert, Similarity-Test; Modell ist ~470 MB statt geschätzter 120 MB ([ADR-02](adr/002-local-embeddings.md)) |
| PyMuPDF ist AGPL, Repo ist MIT | Lizenzprüfung vor dem Pinnen der Abhängigkeiten | pypdf ([ADR-08](adr/008-pdf-parsing-pypdf.md)) |
| Mistral lieferte für `mistral-small` 0 Requests/Minute | Header `x-ratelimit-limit-req-minute: 0`; Probe über alle Chat-Modelle zeigte: Kontingent ist pro Modell vergeben | Provider bricht bei Kontingent 0 sofort mit klarer Meldung ab; Quelle bleibt ohne Guide nutzbar (Migration 0002); Standardmodell nach Qualitätstest `ministral-14b-latest` ([ADR-03](adr/003-llm-provider-mistral.md)) |
| Frage des Nutzers: „Ollama-Fallback einsetzen – oder eher ungünstig?“ | Benchmark lokaler Modelle mit dem echten RAG-Prompt, GPU vs. CPU | Ollama auf CPU 42–118 s pro Antwort und unzuverlässige Zitate → Fallback auf zweites Mistral-Modell, Ollama bleibt manueller Schalter ([ADR-09](adr/009-llm-fallback.md)) |
| EUR-Lex liefert automatisierten Abrufen eine AWS-WAF-Challenge | Test der Demo-Quellen mit dem App-Importer (HTTP 202, leerer Body) | klare Fehlermeldung „Datei herunterladen und hochladen“; Demo nutzt die Amtsblatt-Kopie der IHK |
| „Was regelt Artikel 50?“ → „keine Angaben“ | Demo-Fragen gegen die 200-seitige KI-Verordnung | Normverweise als dritte, doppelt gewichtete Ranking-Liste ([ADR-04](adr/004-hybrid-retrieval-rrf.md)) |
| Modell schrieb `[8a]` und `[4, lit. e]` | Demo-Fragen | Parser normalisiert Unterglieder auf die Passagennummer |
| Eine ausführliche Antwort machte alle folgenden ausführlich, mit Trennlinien und „Keine Angaben zu …“-Blöcken | Vergleich derselben Frage mit und ohne Chatverlauf | Verlauf geht nur noch verdichtet (400 Zeichen, ohne Markdown) an das Modell |
| Ministral 14B hängte alle acht Nummern an „keine Angaben“ | Qualitätstest mit echten Antworten | Prompt mit Negativbeispiel geschärft, Zitat-Parser verwirft Folgen von mehr als drei Belegen |
| nginx lieferte 502 nach Neuerstellung des Backend-Containers | Browser-E2E | Upstream wird zur Laufzeit über Docker-DNS aufgelöst |
| Aus Papern kopierte Literaturverweise wie `[2, 19]` sehen aus wie Zitate | Überlegung beim Zitat-Parser, Test mit dem Transformer-Paper | Klammergruppen mit einer ungültigen Nummer werden komplett verworfen |

## Korrekturen an AI-Arbeit

- Beim Umstellen eines Ports in `.env` hat ein Regex den Zeilenumbruch mitgenommen; ein frisch
  generierter lokaler Access-Key erschien dadurch in einer Fehlermeldung. Der Key wurde sofort
  ersetzt. Seitdem wird die `.env` nur noch angehängt, nie per Regex umgeschrieben, und
  Konfigurationsfehler loggen nur Feldnamen statt Werte.
- Einzelne Testerwartungen waren falsch gerechnet (RRF-Beispiel, Gruppenzahl im Map-Reduce); die
  Tests wurden präzisiert, nicht der Code an die Tests angepasst.
- Ein Ruff-Autofix hat die Stoppwortliste in eine 1 850-Zeichen-Zeile verwandelt; zurückgebaut mit
  gezieltem `noqa`.

## Prompts im Produkt

Alle LLM-Prompts liegen gebündelt in
[backend/app/llm/prompts.py](../backend/app/llm/prompts.py): Quellen-Guide (JSON), Map-Schritt für
lange Quellen, Chat-System-Prompt mit Zitierregeln und Beispiel.
