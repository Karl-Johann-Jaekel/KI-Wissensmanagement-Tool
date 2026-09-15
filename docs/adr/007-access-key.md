# ADR-07: Access-Key statt Auth-System

Status: angenommen

## Kontext

Die Demo-Instanz wird von 2–3 Personen genutzt. Ohne Schutz könnte jeder das Free-Tier-Kontingent
verbrauchen oder beliebige Inhalte hochladen.

## Entscheidung

- Ein gemeinsamer Schlüssel `ACCESS_KEY` in `.env` (Pflichtfeld, mindestens 12 Zeichen).
- Middleware prüft den Header `X-Access-Key` mit konstantem Zeitvergleich für alle `/api`-Routen
  außer `/api/health`.
- Das Frontend fragt den Schlüssel einmal ab und hält ihn im `localStorage`.

## Konsequenzen

- Kein Nutzerkonzept: alle Berechtigten sehen dieselben Notebooks.
- Schlüsselwechsel = `.env` ändern, Container neu starten.
- URL-Import prüft zusätzlich, dass Ziel-Hosts nicht auf private/lokale Adressen auflösen (SSRF).

## Verworfene Alternativen

- Keycloak / OIDC: Overkill für die Demo.
- Magic Link per E-Mail: Mailversand als zusätzliche Fehlerquelle im Live-Test.
