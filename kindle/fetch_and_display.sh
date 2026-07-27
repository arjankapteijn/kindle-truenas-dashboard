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
# WiFi staat dan vaak al uit (los van het slapen gaan, na wat inactiviteit),
# dus fetch_once() zet 'm expliciet aan en probeert een paar keer kort --
# in het slechtste geval (geen WiFi bereikbaar) duurt dat ~25s voordat het
# opgeeft en de vorige afbeelding laat staan.
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
    # WiFi staat op dit toestel na wat inactiviteit uit, los van het
    # slapen gaan -- het goingToScreenSaver-event alleen betekent dus niet
    # dat er al netwerk is. Zet 'm expliciet aan (bekend patroon uit de
    # Kindle-jailbreak-community) en probeer een paar keer kort, in plaats
    # van in één keer op te geven.
    lipc-set-prop com.lab126.cmd wirelessEnable 1 2>/dev/null

    attempt=0
    while [ "$attempt" -lt 5 ]; do
        if wget -q -T 4 -t 1 -O "$TMP_PATH" "$DASHBOARD_URL"; then
            mv "$TMP_PATH" "$SCREENSAVER_PATH"
            # Vangnet voor het geval linkss net iets eerder dan wij de
            # screensaver samenstelde: dwing alsnog een redraw af.
            if command -v fbink >/dev/null 2>&1; then
                fbink -g file="$SCREENSAVER_PATH" >/dev/null 2>&1
            fi
            echo "$(date): dashboard ververst (poging $((attempt + 1)))" >> "$LOG_PATH"
            return
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    echo "$(date): ophalen mislukt na ${attempt} pogingen (WiFi kwam mogelijk niet op tijd omhoog), sla deze ronde over" >> "$LOG_PATH"
}

if command -v lipc-wait-event >/dev/null 2>&1; then
    echo "$(date): gestart, wacht op goingToScreenSaver-events" >> "$LOG_PATH"
    # NB: filteren via een event-naam als los argument (bv.
    # "lipc-wait-event -m com.lab126.powerd goingToScreenSaver") bleek op dit
    # toestel nooit iets op te leveren, ook niet na een hele nacht echte
    # sleep-cycli -- vermoedelijk ongeldige/onduidelijke syntax voor deze
    # firmware. De wildcard-vorm ("*") is wel bevestigd te werken (elk
    # com.lab126.powerd-event kwam meteen binnen), dus we monitoren alles en
    # filteren zelf op de regel.
    # Buitenste lus als vangnet: mocht lipc-wait-event ooit stoppen/crashen,
    # dan herstart het monitoren zichzelf i.p.v. het script stil te laten
    # doodlopen.
    while true; do
        lipc-wait-event -mt "com.lab126.powerd" "*" | while read -r event_line; do
            case "$event_line" in
                *goingToScreenSaver*)
                    fetch_once
                    ;;
            esac
        done
        echo "$(date): lipc-wait-event gestopt, herstart monitoring" >> "$LOG_PATH"
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
