#!/bin/sh
# Ververst de Kindle-screensaver met de laatste dashboard-PNG van de
# kindle-truenas-dashboard-app (via de linkss-hack, al via MRInstaller
# geïnstalleerd). Start dit script via het KUAL-menu (zie config.xml/menu.json).
#
# Waarom event-gedreven i.p.v. een vaste 5-min-polling-lus: op een echt
# slapende Kindle wordt WiFi (en waarschijnlijk dit proces zelf) uitgezet om
# batterij te sparen, waardoor een "sleep 300"-lus in de praktijk uren kan
# overslaan (geverifieerd op dit toestel: gaten van 1,5-2,5 uur i.p.v. 5
# minuten in fetch.log). We wachten daarom op het `goingToScreenSaver`-IPC-
# event van com.lab126.powerd (bevestigd via community-voorbeelden, zie
# README.md) en ververen precies op het moment dat het toestel gaat slapen
# -- exact het moment dat er toch al een screensaver getoond gaat worden.
#
# VOOR GEBRUIK AAN TE PASSEN:
#   1. DASHBOARD_URL  — IP/poort van de kindle-truenas-dashboard-app op je LAN.
#   2. SCREENSAVER_PATH — standaard `linkss/screensavers/`-map (aangemaakt
#      door de linkss-hack zelf). Zorg dat dit bestand daar het ENIGE PNG-
#      bestand is (verwijder de meegeleverde `00_you_can_delete_me*.png`-
#      placeholder(s)), anders wisselt linkss af tussen beide afbeeldingen.

DASHBOARD_URL="http://truenas.arjankapteijn.nl:8000/dashboard.png"
# linkss toont alles in deze map (willekeurig/op volgorde als er meerdere
# bestanden in staan) -- verwijder de meegeleverde placeholder-afbeelding(en)
# zodat dit bestand het enige is en dus altijd getoond wordt.
SCREENSAVER_PATH="/mnt/us/linkss/screensavers/dashboard.png"
# Alleen gebruikt als lipc-wait-event ontbreekt (zie hieronder).
FALLBACK_POLL_INTERVAL_SECONDS=300

WORKDIR="/mnt/us/extensions/kindle-dashboard"
TMP_PATH="$WORKDIR/dashboard.tmp.png"
LOG_PATH="$WORKDIR/fetch.log"

mkdir -p "$WORKDIR"

fetch_once() {
    # Korte timeout (8s, 1 poging): dit draait vlak voor het toestel gaat
    # slapen, dus een tragere/afwezige verbinding mag de sleep-overgang niet
    # merkbaar ophouden -- dan liever het vorige plaatje laten staan.
    if wget -q -T 8 -t 1 -O "$TMP_PATH" "$DASHBOARD_URL"; then
        mv "$TMP_PATH" "$SCREENSAVER_PATH"
        # Vangnet voor het geval linkss net iets eerder dan wij de
        # screensaver samenstelde: dwing alsnog een redraw af.
        if command -v fbink >/dev/null 2>&1; then
            fbink -g file="$SCREENSAVER_PATH" >/dev/null 2>&1
        fi
        echo "$(date): dashboard ververst" >> "$LOG_PATH"
    else
        echo "$(date): ophalen mislukt, sla deze ronde over" >> "$LOG_PATH"
    fi
}

if command -v lipc-wait-event >/dev/null 2>&1; then
    echo "$(date): gestart, wacht op goingToScreenSaver-events" >> "$LOG_PATH"
    while true; do
        lipc-wait-event -m com.lab126.powerd goingToScreenSaver
        fetch_once
    done
else
    # lipc-wait-event hoort standaard op elke K5-firmware te staan; als het
    # toch ontbreekt, terugvallen op de oude vaste interval-polling in
    # plaats van helemaal niets te doen.
    echo "$(date): lipc-wait-event niet gevonden, terugval op vaste interval van ${FALLBACK_POLL_INTERVAL_SECONDS}s" >> "$LOG_PATH"
    while true; do
        fetch_once
        sleep "$FALLBACK_POLL_INTERVAL_SECONDS"
    done
fi
