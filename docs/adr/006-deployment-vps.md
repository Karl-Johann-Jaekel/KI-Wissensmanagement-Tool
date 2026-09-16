# ADR-06: Deployment auf bestehendem VPS hinter Caddy

Status: angenommen (Nachtrag beim Deployment, siehe unten)

## Kontext

Das Ergebnis muss öffentlich erreichbar sein. Es existiert bereits ein EU-VPS mit Docker und
Caddy (automatisches TLS), auf dem weitere Portfolio-Projekte laufen.

## Entscheidung

- Derselbe `docker-compose.yml` wie lokal, ohne Override-Datei.
- Nur der Frontend-Container (nginx) ist von außen erreichbar; Caddy proxied die Subdomain
  darauf. Backend und Postgres bleiben im Compose-Netz.
- Keine zusätzlichen offenen Ports, keine manuellen Zertifikate.

## Nachtrag: Anbindung über das Docker-Netz statt über 127.0.0.1

Ursprünglich war vorgesehen, das Frontend an `127.0.0.1:${FRONTEND_PORT}` zu binden und Caddy
darauf zu proxien. Auf dem Zielserver läuft Caddy selbst als Container und erreicht den
Host-Localhost nicht. Das etablierte Muster der Maschine: Caddy hängt im externen Docker-Netz
`web`, jeder Dienst tritt diesem Netz mit einem eigenen Alias bei und wird unter diesem Namen
proxied.

Deshalb entfällt produktiv die Host-Bindung ganz. Eine serverseitige Overlay-Datei
`docker-compose.mainserver.yml` (nicht im Repo, damit ein frischer Klon eigenständig lauffähig
bleibt) entfernt die Ports und hängt das Frontend zusätzlich ins Netz `web`:

```yaml
services:
  frontend:
    ports: !reset []          # "ports: []" leert in Compose v5 nichts — Listen werden gemerged
    networks:
      default: {}
      web:
        aliases: [notebook-web]

networks:
  web:
    external: true
```

Caddy proxied `notebook.jaekel.dev` auf `notebook-web:80`. Ergebnis ist strenger als geplant:
das Frontend hat produktiv gar keinen Host-Port mehr, nur Caddy erreicht es.

## Konsequenzen

- Keine zusätzlichen Accounts oder Kosten; Daten bleiben in der EU.
- Verfügbarkeit hängt am eigenen VPS — für eine Demo akzeptabel.
- Produktion und lokale Entwicklung unterscheiden sich um genau eine Overlay-Datei; der
  Anwendungs-Stack selbst ist identisch.

## Verworfene Alternativen

- Railway / Vercel / Fly.io: zusätzliche Accounts, US-Hosting, pgvector + 500-MB-Modell passen
  schlecht in Free-Tiers.
- `host.docker.internal` im Caddy-Container statt gemeinsamem Netz: hängt an einer
  Docker-Sonderkonfiguration und träfe für jedes weitere Projekt auf der Maschine erneut zu.
