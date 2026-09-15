# ADR-06: Deployment auf bestehendem VPS hinter Caddy

Status: angenommen

## Kontext

Das Ergebnis muss öffentlich erreichbar sein. Es existiert bereits ein EU-VPS mit Docker und
Caddy (automatisches TLS), auf dem weitere Portfolio-Projekte laufen.

## Entscheidung

- Derselbe `docker-compose.yml` wie lokal, ohne Override-Datei.
- Nur der Frontend-Container (nginx) wird an `127.0.0.1` gebunden; Caddy proxied die Subdomain
  darauf. Backend und Postgres sind nur im Compose-Netz erreichbar.
- Keine zusätzlichen offenen Ports, keine manuellen Zertifikate.

## Konsequenzen

- Keine zusätzlichen Accounts oder Kosten; Daten bleiben in der EU.
- Verfügbarkeit hängt am eigenen VPS — für eine Demo akzeptabel.

## Verworfene Alternativen

- Railway / Vercel / Fly.io: zusätzliche Accounts, US-Hosting, pgvector + 500-MB-Modell passen
  schlecht in Free-Tiers.
