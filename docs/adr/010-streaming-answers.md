# ADR-10: Antworten streamen, Zitate weiterhin am Ende validieren

Status: angenommen

## Kontext

Eine Antwort braucht mit `ministral-14b-latest` 5–15 Sekunden. Die Oberfläche konnte diese Zeit
nur mit einem Spinner füllen; im Live-Test summiert sich das über mehrere Fragen zu einer Minute
Stillstand. NotebookLM streamt.

Das Streamen kollidiert scheinbar mit [ADR-05](005-validated-citations.md): Belege werden geprüft
und neu nummeriert, und das geht erst, wenn der Text vollständig ist. Ein Marker `[7]`, den das
Modell erfunden hat, lässt sich nicht entfernen, während er schon auf dem Bildschirm steht.

## Entscheidung

Ein zweiter Endpunkt `POST /notebooks/{id}/chat/stream` liefert Server-Sent Events:

| Event | Inhalt |
|---|---|
| `passages` | Anzahl gefundener Passagen und Quellen — Retrieval ist fertig, Generierung beginnt |
| `delta` | Rohtext des Modells, Stück für Stück |
| `done` | die geprüfte, neu nummerierte Antwort samt Belegen, wie sie gespeichert wurde |
| `error` | Fehlertext, falls die Generierung scheitert |

Die Validierung bleibt unverändert und läuft auf dem fertigen Text. Die `delta`-Events zeigen
also die Rohfassung, das `done`-Event ersetzt sie. In der Praxis fällt der Austausch nicht auf:
er betrifft nur ungültige Marker und deren Nummerierung.

Der bestehende Endpunkt bleibt. Öffnet der Stream nicht — ein Proxy, der `text/event-stream`
puffert oder blockt —, fragt das Frontend einmal über den alten Weg nach.

**Wiederholungen enden beim ersten Zeichen.** `_stream_post` und `FallbackProvider` versuchen es
erneut, solange nichts beim Aufrufer angekommen ist; danach schlägt der Fehler durch. Ein Retry
oder ein zweites Modell würde eine Antwort neu beginnen, die der Leser schon zur Hälfte gelesen
hat.

## Konsequenzen

- Das erste Zeichen steht nach etwa 0,3 s statt nach 5–15 s; gemessen über nginx: 32 Events,
  erstes `delta` nach 0,29 s.
- nginx puffert Proxy-Antworten und spricht per Vorgabe HTTP/1.0 ohne Chunked Encoding. Beides
  ist in `frontend/nginx.conf` abgestellt, zusätzlich sendet das Backend `X-Accel-Buffering: no`.
- Zwei Endpunkte für dieselbe Sache. Sie teilen sich Retrieval, Validierung und Speicherung;
  unterschiedlich ist nur die Auslieferung.
- Ein Fehler nach dem HTTP-Header kann keinen Statuscode mehr setzen und reist als `error`-Event.

## Verworfene Alternativen

- **Zitate live validieren, Marker unterdrücken bis geprüft:** hätte den Text während des
  Schreibens verändert und bei Bereichen wie `[2–4]` auf Bruchstücke reagieren müssen.
- **Nur eine Fortschrittsanzeige statt Streaming:** billiger, aber die Wartezeit bleibt Wartezeit.
- **WebSocket:** eine Verbindung pro Antwort, in eine Richtung — SSE kann genau das, über
  gewöhnliches HTTP und ohne Zusatzabhängigkeit.
