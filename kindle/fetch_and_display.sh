#!/bin/sh
# Haalt periodiek de dashboard-PNG op van de kindle-truenas-dashboard-app en
# zet 'm neer als Kindle-screensaver (via de linkss-hack, al via MRInstaller
# geïnstalleerd). Start dit script via het KUAL-menu (zie menu/config.xml).
#
# Dit script is een op zichzelf staande while-lus (geen crond nodig — die
# ontbreekt standaard op deze jailbreak) en draait door tot je 'm stopt
# (KUAL-app sluiten volstaat meestal niet voor een achtergrondproces; zie
# README.md in deze map voor hoe je 'm expliciet stopt).
#
# VOOR GEBRUIK AAN TE PASSEN:
#   1. DASHBOARD_URL  — IP/poort van de kindle-truenas-dashboard-app op je LAN.
#   2. SCREENSAVER_PATH — pad waar linkss z'n custom screensaver-image
#      verwacht. Dit verschilt per linkss-versie/instelling; controleer dit
#      op je eigen toestel (KUAL > linkss > instellingen) — dit script kon
#      niet op het fysieke toestel geverifieerd worden.

DASHBOARD_URL="http://192.168.1.10:8000/dashboard.png"
SCREENSAVER_PATH="/mnt/us/linkss/screensavers/bg_medium_ss00.png"
POLL_INTERVAL_SECONDS=300

WORKDIR="/mnt/us/extensions/kindle-dashboard"
TMP_PATH="$WORKDIR/dashboard.tmp.png"
LOG_PATH="$WORKDIR/fetch.log"

mkdir -p "$WORKDIR"

while true; do
    if wget -q -O "$TMP_PATH" "$DASHBOARD_URL"; then
        mv "$TMP_PATH" "$SCREENSAVER_PATH"
        # Forceert meteen een redraw als het toestel al slaapt, zodat je niet
        # per se hoeft te wekken+slapen voor de nieuwe stand zichtbaar wordt.
        # Verwijder deze blok als je liever op de eerstvolgende natuurlijke
        # sleep-cyclus wacht.
        if command -v fbink >/dev/null 2>&1; then
            fbink -g file="$SCREENSAVER_PATH" >/dev/null 2>&1
        fi
        echo "$(date): dashboard ververst" >> "$LOG_PATH"
    else
        echo "$(date): ophalen mislukt, sla deze ronde over" >> "$LOG_PATH"
    fi
    sleep "$POLL_INTERVAL_SECONDS"
done
