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
| Mistral-Workspace hatte 0 Requests/Minute | Header `x-ratelimit-limit-req-minute: 0` bei einer Test-Anfrage | Provider bricht sofort mit klarer Meldung ab statt viermal zu wiederholen; Quelle bleibt ohne Guide nutzbar (Migration 0002) |
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
