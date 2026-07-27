#!/bin/sh
# Tijdelijk diagnose-scriptje: logt ALLE com.lab126.powerd-events naar
# events.log, zodat we zonder KUAL-terminal kunnen zien welk event er echt
# afgaat bij het slapen/wekken van dit toestel. Los te starten via het
# KUAL-menu-item "Diagnose: log alle powerd-events" (zie menu.json).
#
# Gebruik: start dit item, koppel de Kindle daarna los van USB (dit moet
# los van de kabel getest worden -- aangesloten blijven voorkomt normaal
# slapen), laat 'm gewoon even normaal in slaap vallen en weer wekken, sluit
# daarna weer aan op USB zodat events.log uitgelezen kan worden.

WORKDIR="/mnt/us/extensions/kindle-dashboard"
LOG_PATH="$WORKDIR/events.log"

mkdir -p "$WORKDIR"
echo "$(date): diagnose gestart, logt alle com.lab126.powerd-events" >> "$LOG_PATH"
lipc-wait-event -mt "com.lab126.powerd" "*" >> "$LOG_PATH" 2>&1
