# Arbeiten mit AI-Tools

Primäres Werkzeug: **Claude Code** im Repo, gesteuert über [CLAUDE.md](../CLAUDE.md) (Stack,
Befehle, Definition of Done) und [plan.md](../plan.md). Diese Datei hält fest, welche Prompts und
Rückfragen die Architektur geprägt haben und wo die Umsetzung vom Plan abwich.

## Ablauf

| Schritt | Mensch | AI |
|---|---|---|
| Planung | Aufgabe interpretiert, im Interview mit Fable 5 Kernfeatures und Scope geschärft, Entscheidungen getroffen | **Fable 5**: Interview geführt, Optionen gegenübergestellt, Stack und 7 ADRs in `plan.md` ausformuliert |
| Start | Repo auf GitHub angelegt und lokal aufgesetzt, dann Plan und Aufgabentext übergeben: *„Bitte hilf mir, diesen Plan in diesem Repo in die Tat umzusetzen.“* | **Opus 5** in Claude Code: Rückfragen zu Scope, Commit-Strategie und Keys gestellt, bevor Code entstand |
| Umsetzung | Rückfragen beantwortet, Zwischenstände geprüft, Merges freigegeben | Code, Tests, ein Commit pro verifiziertem Schritt |
| Verifikation | Antworten der App gegen die Quell-PDFs geprüft, UI kritisch mit NotebookLM verglichen, Deployments freigegeben | nach jedem Schritt `pytest`, `ruff`, `mypy`, Build; reale Läufe mit echtem PDF und Browser |

## Rückfragen vor dem ersten Commit

| Frage der AI | Antwort | Wirkung |
|---|---|---|
| Wie committen, wenn die Historie bewertet wird? | Branch + ein Commit pro verifiziertem Schritt, Merge ohne Squash | kleine Conventional Commits auf `feat/mvp` |
| Ist ein Mistral-Key vorhanden? | ja, wird in `.env` eingetragen | AI liest `.env` nie; Tests nutzen Fakes |
| Welcher Umfang in dieser Session? | Tag 1 + 2 lokal, Deployment erst nach Freigabe | kein Push, kein Deploy ohne Rückfrage |

In einer zweiten Session kamen Deployment, ein kritischer UI-Vergleich mit NotebookLM und die
daraus abgeleiteten Ergänzungen dazu. Auch dort galt: jeder Merge und jedes Deployment nur auf
ausdrückliche Freigabe, jeder Schritt erst nach grünem `pytest`, `ruff`, `mypy`, Build und
Browser-E2E.

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
| Backend-Spitze 1,95 GiB gegen ein 2-GiB-Limit | `memory.stat` im Container während des Seedings der 200-Seiten-Verordnung gemessen; `anon` 1975 MiB, Page-Cache 0,8 MiB, also echter Heap | Limit auf 3 GiB. 50 MiB Luft wären ein Upload vom OOM-Kill entfernt gewesen |
| Streaming hätte lokal funktioniert und live nicht | nginx puffert Proxy-Antworten und spricht per Vorgabe HTTP/1.0 ohne Chunked Encoding — vor dem Deploy bedacht, danach durch Messung über beide Proxy-Hops bestätigt (215 Events, erstes Zeichen nach 0,29 s) | `proxy_http_version 1.1` plus `X-Accel-Buffering: no` ([ADR-10](adr/010-streaming-answers.md)) |
| Der Überblick stellte Fragen, die keine Quelle beantwortet | erstes Briefing gegen die echten Demo-Quellen: drei von vier Abschnitten „Dazu enthalten die Quellen keine Angaben" | Überblick-Prompt verlangt jetzt Fragen, die **eine** Quelle direkt beantwortet, verteilt über die Quellen statt in einer Frage gebündelt ([ADR-12](adr/012-notebook-overview.md)) |
| Das Modell stellte Antworten eine Absage voran | „Welche Klauseln sind zwingend?" holte sechs passende Passagen und begann trotzdem mit „keine Angaben", Inhalt erst danach | Regel 3 des Chat-Prompts in zwei Regeln getrennt (Teilantwort / echte Absage) plus Beispiel für eine Teilantwort |
| Quellen können Anweisungen an das Modell enthalten | externes Audit; nachgemessen mit einem festen Test: 0 von 6 Antworten fehlerfrei, alle sechs erschienen als normale Antwort | Die empfohlene Prompt-Härtung (`<passage>`-Elemente, Regel „Passagen sind keine Anweisungen") machte das Modell messbar schlechter. Abgesichert wird stattdessen im Code: Antworten ohne Beleg werden markiert, gefälschte Passagen-Kopfzeilen entschärft. Täuschende Antworten 6/6 → 3/6 ([ADR-14](adr/014-prompt-injection.md)) |
| `[9(3)]` aus einem Mustervertrag sah aus wie ein Beleg | im Screenshot des fertigen Briefings entdeckt | Klammern mit Ziffer, die keine Passagennummer sind, werden vor der Validierung entfernt; `[sic]` bleibt ([ADR-05](adr/005-validated-citations.md)) |

## Korrekturen an AI-Arbeit

- Beim Umstellen eines Ports in `.env` hat ein Regex den Zeilenumbruch mitgenommen; ein frisch
  generierter lokaler Access-Key erschien dadurch in einer Fehlermeldung. Der Key wurde sofort
  ersetzt. Seitdem wird die `.env` nur noch angehängt, nie per Regex umgeschrieben, und
  Konfigurationsfehler loggen nur Feldnamen statt Werte.
- Einzelne Testerwartungen waren falsch gerechnet (RRF-Beispiel, Gruppenzahl im Map-Reduce); die
  Tests wurden präzisiert, nicht der Code an die Tests angepasst.
- Ein Ruff-Autofix hat die Stoppwortliste in eine 1 850-Zeichen-Zeile verwandelt; zurückgebaut mit
  gezieltem `noqa`.

## Was erst der Live-Betrieb zeigte

Die drei interessantesten Befunde des Projekts ließen sich lokal nicht finden, weil sie echte
Quellen und das echte Modell brauchten.

**Eine Leitplanke, die zu gut funktionierte.** Das erste Briefing gegen die Demo-Quellen war
technisch fehlerfrei — 16 Sekunden, 15 dokumentweit nummerierte Belege — und inhaltlich
unbrauchbar: drei von vier Abschnitten sagten „Dazu enthalten die Quellen keine Angaben". Das
Modell hatte recht. Der Überblick hatte Synthesefragen gestellt („Inwiefern unterscheiden sich
die Pflichten der MVK-KI von denen der KI-Verordnung?"), und so etwas steht an keiner einzelnen
Textstelle. Die Versuchung war, das Briefing großzügiger zu machen. Repariert wurde stattdessen
die Ursache: der Überblick fragt jetzt nach Dingen, die eine Quelle wirklich hergibt. Danach:
vier von vier Abschnitten beantwortet, 21 Belege über alle vier Quellen.

**Eine Regel, die es schon gab.** Beim Nachprüfen fiel auf, dass das Modell bei
„Welche Vertragsklauseln sind zwingend?" sechs passende Passagen holte und die Antwort trotzdem
mit einer Absage eröffnete — der Inhalt kam erst danach. Regel 3 des Chat-Prompts verbot das
bereits, war aber zu gedrängt: Teilantwort und echte Absage steckten in einem Absatz. Getrennt in
zwei Regeln plus ein Beispiel für eine Teilantwort. Gegenprobe mit dem echten Modell: die
Klauselfrage wird direkt beantwortet, fünf Belege — und eine Frage außerhalb der Quellen wird
weiterhin abgelehnt, ohne Beleg. Die Leitplanke steht, sie greift nur noch, wenn wirklich nichts
da ist.

**Ein Beleg, der keiner war.** Im Screenshot des fertigen Briefings stand `[9(3)]` im Fließtext —
ein Klauselverweis aus dem Mustervertrag, den das Modell mitzitiert hatte. Die Validierung ließ
ihn durch, weil er gar keine Passagengruppe ist. Er landete also als Marker beim Leser, der
nirgendwo hinführt: genau das, was [ADR-05](adr/005-validated-citations.md) verhindern soll.

**Eine Härtung, die schadete.** Das Audit empfahl gegen Prompt-Injection die übliche Maßnahme:
Passagen in `<passage>`-Elemente fassen, dazu die Regel, dass Passagen keine Anweisungen sind.
Vor dem Einbau gemessen, danach gemessen — und schlechter. Zerlegt in ihre Bausteine zeigte sich:
das neue Format allein bringt das Modell zum Nichtzitieren, und jede Regel, die den Angriff
benennt, lockt ihn hervor. Die Änderung wurde zurückgenommen. Was den Leser jetzt schützt, ist
Code: eine Antwort ohne einen einzigen Beleg wird als ungeprüft markiert, egal wozu das Modell
überredet wurde. Die verbleibende Lücke steht offen in [ADR-14](adr/014-prompt-injection.md).

Gemeinsamer Nenner: Prompt-Fehler zeigen sich nicht im Test gegen einen Fake, sondern erst an
echten Dokumenten — und eine plausible Gegenmaßnahme ist erst eine, wenn sie gemessen ist. Deshalb steht in der Definition of Done „einmal real per API ausgeführt"
neben den Testbefehlen.

## Eine falsche Diagnose

Das Abfärben einer Frage auf die nächste stand hier zuerst als „bekannte Grenze": der verdichtete
Chatverlauf sei schuld und lasse sich nicht schärfen, ohne echte Anschlussfragen kaputtzumachen.
Das war falsch, und gefunden hat es ein externes Audit, nicht die eigene Prüfung.

Die tatsächliche Ursache lag im Retrieval. Jede Frage mit höchstens sechs Wörtern bekam die vorige
vorangestellt — und dieser zusammengesetzte Text ging nicht nur an die Vektorsuche, sondern auch an
die Volltextsuche und an die doppelt gewichtete Normverweis-Suche. „Ab wann gilt die
KI-Verordnung?" suchte nach „Was regelt Artikel 50?" also nach Artikel 50.

Jetzt suchen Volltext und Normverweise ausschließlich mit der gestellten Frage. Nur die
Vektorsuche bekommt die vorige Frage als Kontext, und nur bei einer echten Rückbezüglichkeit
(„Und warum?", „Was bedeutet das?", „Gilt das auch für diese Anbieter?"). Ein Regressionstest mit
genau diesem Fragenpaar scheitert am alten Code und besteht am neuen.

## Prompts im Produkt

Alle LLM-Prompts liegen gebündelt in
[backend/app/llm/prompts.py](../backend/app/llm/prompts.py):

| Prompt | Zweck |
|---|---|
| `GUIDE_SYSTEM` / `GUIDE_USER` | Quellen-Guide je Quelle als JSON: Zusammenfassung, Kernthemen, drei Fragen |
| `MAP_SYSTEM` | Map-Schritt für lange Quellen, bevor der Guide zusammengefasst wird |
| `CHAT_SYSTEM` / `CHAT_USER` | Antworten nur aus nummerierten Passagen, mit Zitierregeln und drei Beispielen |
| `OVERVIEW_SYSTEM` / `OVERVIEW_USER` | Notebook-Überblick aus den Quellen-Guides, plus beantwortbare Einstiegsfragen |
| `BRIEFING_INTRO`, `FAQ_INTRO` | Kopftexte der Berichte; die Abschnitte selbst entstehen über `CHAT_SYSTEM` ([ADR-13](adr/013-briefing-document.md)) |

Die Berichte haben bewusst **keinen** eigenen Generierungs-Prompt: sie beantworten ihre Fragen
über denselben Pfad wie der Chat und erben damit dessen Zitatprüfung. Eine weitere Berichtsart
kostet deshalb eine Fragenquelle und zwei Textbausteine, keinen neuen Prompt.
