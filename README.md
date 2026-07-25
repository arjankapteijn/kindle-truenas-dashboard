# kindle-truenas-dashboard

Een statusdashboard van een TrueNAS SCALE-server (CPU, geheugen/ZFS ARC,
disks/SMART-gerelateerde alerts, pool-status/scrub, netwerk, apps, actieve
meldingen), gerenderd als PNG en getoond op een jailbroken Kindle Voyage als
vervangende screensaver.

```
┌─────────────────────┐  websocket   ┌──────────────────────────┐   HTTP GET   ┌────────────┐
│   TrueNAS SCALE      │◄────JSON-RPC─┤ deze app (TrueNAS custom │◄─────────────┤   Kindle    │
│   (25.10 "Goldeye")  │              │ app, self-scheduling)    │  elke 5 min  │   Voyage    │
└─────────────────────┘              │ schrijft dashboard.png    │              │ (linkss     │
                                       │ naar /data + serveert    │              │ screensaver)│
                                       │ 't over :8000            │              └────────────┘
                                       └──────────────────────────┘
```

Anders dan [lovebox](https://github.com/arjankapteijn/lovebox) (dat dagelijks
een afbeelding *pusht* naar een extern apparaat) is dit een **pull-model**:
de container ververst zelf periodiek en houdt de laatste PNG klaar op een
vast HTTP-endpoint; de Kindle haalt 'm zelf op wanneer het uitkomt.

## Snelstart

1. **API-key aanmaken** in de TrueNAS-UI: gebruikersmenu (rechtsboven) →
   *My API Keys* → *Add API Key*. Overweeg een aparte, minder bevoorrechte
   gebruiker specifiek voor deze key (een API-key erft de rol van de
   gekoppelde gebruiker — er is geen aparte read-only scoping in de UI).
2. Kopieer `.env.example` naar `.env` en vul `KD_TRUENAS_URL` en
   `KD_TRUENAS_API_KEY` in (zie `.env.example` voor uitleg per variabele).
3. **Deploy als TrueNAS custom app**: gebruik `docker-compose.yml` in de
   TrueNAS-UI (Apps → Discover Apps → Custom App → Install via YAML), met
   `env_file` op een **absoluut pad** (bv. `/mnt/apps/kindle-dashboard/.env`
   — een relatief pad wordt door TrueNAS naar `/tmp/.env` herschreven en
   faalt dan stil).
4. Zet de Kindle-kant op — zie [`kindle/README.md`](kindle/README.md) voor
   de volledige installatie (linkss-screensaver, KUAL-scriptlet, fbink).

## Lokaal ontwikkelen

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest

# Layout visueel checken zonder TrueNAS-verbinding:
python scripts/render_preview.py preview.png

# Eén keer live tegen je TrueNAS-server renderen (i.p.v. de scheduler+server):
KD_TRUENAS_URL=ws://172.16.0.1:8080/api/current \
KD_TRUENAS_API_KEY=1-... \
KD_RUN_ONCE=true KD_DATA_DIR=/tmp \
  python -m kindle_dashboard.main
```

## TrueNAS API — belangrijke kanttekeningen

Deze app praat met TrueNAS via **JSON-RPC 2.0 over websocket**
(`/api/current`), niet via de oudere REST-API (`/api/v2.0/...`) — die is in
25.10 al deprecated en verdwijnt in v26. Twee dingen die niet vanzelfsprekend
uit de officiële docs bleken (geverifieerd tegen een live 25.10.4-server):

- **`truenas_api_client` staat niet op PyPI.** Het wordt geïnstalleerd via
  `pip install git+https://github.com/truenas/api_client.git@TS-25.10.4` —
  gepind op de tag die overeenkomt met je TrueNAS-versie (zie
  [tags](https://github.com/truenas/api_client/tags)). Bij een TrueNAS-
  upgrade: werk deze pin in `pyproject.toml` bij.
- **`auth.login_with_api_key`** (de simpele "alleen API-key"-login,
  gebruikt in `truenas_client.py`) is in 25.10 al deprecated en wordt in
  **v27 verwijderd**. Bij een toekomstige upgrade naar v27+ moet dit
  overstappen op `auth.login_ex` met
  `{"mechanism": "API_KEY_PLAIN", "username": ..., "api_key": ...}` — dat
  vereist de gebruikersnaam van de key-eigenaar als extra configuratie.
- **ZFS ARC-hitrate** (`arcrate`/`arcactualrate`/`arcresult`) bleek op de
  geteste server geen geldige netdata-metriek te zijn (server-side
  `KeyError`) — alleen `arcsize` is betrouwbaar beschikbaar, dus alleen de
  ARC-grootte wordt getoond, geen hitrate.
- **SMART-status** komt niet als los veld uit `disk.query`/`disk.details` —
  die info zit in het **alert-systeem** (`alert.list`), samen met
  pool-degraded-meldingen e.d. Vandaar de "Actieve meldingen"-sectie
  bovenaan i.p.v. een aparte SMART-kolom.
- **Rate limiting**: TrueNAS staat max. 20 auth-pogingen/60s toe, met een
  10 minuten cooldown erna. Bij een `KD_POLL_INTERVAL_SECONDS` van 300s
  (standaard) met één websocket-sessie per ronde kom je daar in de verste
  verte niet bij in de buurt, maar vermijd korte polling-intervallen bij
  het debuggen.

## Wat het dashboard toont

CPU (gebruik totaal + per core, temperatuur, load average, uur-sparkline),
geheugen- en ZFS ARC-gebruik, storage pools (status, scrub/resilver,
gebruikte/vrije ruimte), disks (temperatuur, grootte, pool), netwerk
(doorvoer per interface), apps (draaiend/gestopt) en actieve TrueNAS-alerts.
Secties met een variabele hoeveelheid content (disks, apps, netwerk, pools)
zijn begrensd op de beschikbare ruimte op het 1072×1448-scherm: bij te veel
content wordt "+N meer" getoond, of wordt een hele sectie overgeslagen (met
een vermelding in de voettekst) in plaats van tekst te laten overlappen.

## Herkomst / hergebruikte patronen

Rendering-aanpak (Pillow, font-fallback, thema-constanten), hardening
(non-root, read-only rootfs, cap_drop, named volume voor schrijfbare data,
heartbeat-gebaseerde healthcheck) en CI/CD-scaffolding (ruff + pytest +
conventional-commit-gebaseerde ghcr.io-publish + Dependabot) zijn
overgenomen van [lovebox](https://github.com/arjankapteijn/lovebox). De
self-scheduling loop is aangepast van "dagelijks op een vast tijdstip
versturen" naar "elke N seconden opnieuw renderen en lokaal serveren",
passend bij het pull-model hier.
