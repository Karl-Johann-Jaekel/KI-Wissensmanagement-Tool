# Demo-Notebook „KI im Unternehmen: Recht & Verträge“

Vorindiziertes Notebook für den Live-Test: öffentliche, deutschsprachige Dokumente rund um den
Einsatz von KI – ein Gesetz, eine Aufsichtsbehörden-Leitlinie, Vertragsklauseln und ein
Mustervertrag. Die Mischung zeigt Suche über lange Rechtstexte, Querbezüge zwischen Quellen und
das Verhalten bei Fragen, die die Quellen nicht beantworten.

## Quellen

| Titel | Herausgeber | Umfang | Abruf |
|---|---|---|---|
| KI-Verordnung (EU) 2024/1689 | Amtsblatt der EU (PDF-Kopie der IHK) | 200 S. | [PDF](https://www.ihk.de/blueprint/servlet/resource/blob/6203774/d2e3f88248a0a4951beb9eb8c3050d51/eu-ki-verordnung-data.pdf) |
| Orientierungshilfe generative KI mit RAG (2025) | Datenschutzkonferenz (DSK) | 18 S. | [PDF](https://www.datenschutzkonferenz-online.de/media/oh/DSK_OH_RAG.pdf) |
| EU-Mustervertragsklauseln für KI-Beschaffung (MVK-KI) – Kommentar | Community of Practice Public Procurement of AI, EU-Kommission | 17 S. | [PDF](https://public-buyers-community.ec.europa.eu/sites/default/files/2025-06/GROW-2025-00573-02-01-DE-TRA-00.pdf) |
| Mustervertrag Auftragsverarbeitung nach Art. 28 DSGVO | Wirtschaftskammer Österreich (WKO) | 8 S. | [PDF](https://www.wko.at/oe/datenschutz/eu-dsgvo-mustervertrag-vereinbarung-auftragsverarbeitung.pdf) |

Die Dateien werden nicht im Repo abgelegt, sondern beim Seeden direkt von den Herausgebern
geladen. Hinweise:

- **EUR-Lex** beantwortet automatisierte Abrufe mit einer Bot-Challenge; deshalb die IHK-Kopie
  des Amtsblatts. Ein URL-Import von EUR-Lex zeigt in der App einen entsprechenden Hinweis.
- Die MVK-KI-Klauseln selbst gibt es nur als DOCX (nicht unterstützt); der Kommentar erläutert sie
  Klausel für Klausel.
- Der WKO-Mustervertrag ist auf österreichisches Recht zugeschnitten, folgt aber Art. 28 DSGVO.

## Anlegen

```bash
# lokal, im Backend-Container (ACCESS_KEY ist dort gesetzt)
docker compose cp demo/seed.py backend:/tmp/seed.py
docker compose exec backend python /tmp/seed.py --base-url http://localhost:8000

# oder von außen gegen eine laufende Instanz
ACCESS_KEY=... python demo/seed.py --base-url https://notebook.example.org
```

Das Skript ist idempotent (vorhandene Quellen werden übersprungen, fehlgeschlagene neu
importiert) und importiert nacheinander, um die Free-Tier-Limits zu schonen.

Gemessen lokal (Ryzen 7 5800H, `ministral-14b-latest`): KI-Verordnung 162 s (578 Abschnitte,
Guide per Map-Reduce), die anderen Quellen 12–30 s. Das Backend brauchte dabei in der Spitze
1,65 GiB RAM (Limit im Compose: 2 GiB).

## Demo-Fragen

Mit echtem Modell geprüft, nacheinander im selben Chat. Antworten variieren im Wortlaut, Inhalt
und Belege waren stabil.

| # | Frage | Beleg | Zeigt |
|---|---|---|---|
| 1 | Ab wann gilt die KI-Verordnung? | KI-VO S. 71 | Stufen 2. Feb. 2025 / 2. Aug. 2025 / 2. Aug. 2026 aus Erwägungsgrund 179 |
| 2 | Was regelt Artikel 50 der KI-Verordnung? | KI-VO S. 123 | Suche nach Normverweisen (Artikelnummern findet reine Vektorsuche nicht) |
| 3 | Welche KI-Praktiken sind nach der KI-Verordnung verboten? | KI-VO S. 80 | Art. 5 in einem 200-Seiten-Dokument |
| 4 | Was muss der Auftragsverarbeiter tun, bevor er einen weiteren Auftragsverarbeiter einsetzt? | WKO-Vertrag S. 5 | Vertragsklausel: Anzeige an den Auftraggeber, Vereinbarung nach Art. 28 Abs. 4 |
| 5 | Welche datenschutzrechtlichen Risiken nennt die DSK bei RAG-Systemen? | DSK S. 3, 11, 13, 14 | Mehrere Belege aus einer Quelle – und die App ist selbst ein RAG-System |
| 6 | Welche Protokollierungspflichten gelten für Hochrisiko-KI und wie greifen die Mustervertragsklauseln das auf? | KI-VO S. 32, 95; MVK-KI S. 7, 9 | Antwort über zwei Quellen hinweg |
| 7 | Wie hoch ist der gesetzliche Mindestlohn in Deutschland? | – | „Dazu enthalten die Quellen keine Angaben.“, kein Beleg |

Für den Quellenfilter: alle Quellen außer dem WKO-Vertrag abwählen und Frage 4 stellen – die
Belege kommen dann nur noch aus dem Vertrag; mit nur der KI-Verordnung ausgewählt gibt es dazu
keine Angaben.
