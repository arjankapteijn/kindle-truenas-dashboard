# Kindle-kant: dashboard ophalen en tonen

Dit is de tegenhanger van de `kindle-truenas-dashboard`-app op TrueNAS: een
scriptlet die op de Kindle zelf draait, elke 5 minuten de laatste
dashboard-PNG ophaalt en als screensaver toont.

**Belangrijk voorbehoud:** dit is opgezet op basis van gedocumenteerde,
gangbare community-patronen (MobileRead / linkss / fbink) en lokaal
getest op de renderer-kant, maar **niet op het fysieke toestel** — er was in
deze sessie geen toegang tot de Kindle zelf. Controleer de punten hieronder
op je eigen Voyage voordat je het script laat draaien.

## Vereisten (al aanwezig volgens jouw opzet)

- WinterBreak2-jailbreak + hotfix
- KUAL + MRInstaller, werkend
- **linkss** ("K5 FW 5.x ScreenSavers Hack") — zo niet: installeer via
  MRInstaller (`Update_linkss_*_install_touch_pw.bin` in `/mnt/us/mrpackages/`)
- **fbink** — wordt door de meeste NiLuJe-pakketten al meegeleverd; check met
  `which fbink` in een KUAL-terminal. Zo niet, dan werkt het script ook
  zonder (het slaat de fbink-stap dan gewoon over en je ziet de nieuwe
  afbeelding pas bij de eerstvolgende natuurlijke sleep/wake).

## Installatie

1. Kopieer de map `kindle/` uit deze repo naar het toestel als
   `/mnt/us/extensions/kindle-dashboard/` (bv. via USB-verbinding).
2. Open `fetch_and_display.sh` en pas bovenin aan:
   - `DASHBOARD_URL` — het IP-adres + poort van de TrueNAS-app, bv.
     `http://172.16.0.1:8000/dashboard.png` (intern app-netwerkadres) of het
     LAN-IP van je TrueNAS-server op poort 8000. **Gebruik platte HTTP**,
     geen HTTPS — de ingebouwde busybox-`wget` op deze firmware kan geen
     moderne TLS afhandelen.
   - `SCREENSAVER_PATH` — controleer in linkss' eigen instellingenmenu
     (KUAL > linkss) welk bestand/pad de actieve "custom screensaver" is;
     pas dit aan als het afwijkt van het voorbeeld in het script.
3. Zorg dat het script uitvoerbaar is: `chmod +x fetch_and_display.sh`
   (via een KUAL-terminal, of via USB als je bestandsbeheer permissies
   behoudt).
4. Open KUAL op de Kindle → de nieuwe menu-ingang "TrueNAS-dashboard" moet
   verschijnen (uit `menu/config.xml`) → kies **"Start TrueNAS-dashboard
   refresh-loop"**.

Het script blijft op de achtergrond draaien (`while true; do ... sleep 300;
done`) en ververst elke 5 minuten. Je hebt zelf gekozen voor **handmatig
starten via KUAL** i.p.v. automatisch bij boot — dat betekent: na een
herstart of USB-verbinding moet je de loop opnieuw starten via hetzelfde
KUAL-menu.

## Stoppen

Een achtergrond-`while`-lus sluit niet vanzelf als je KUAL sluit. De
eenvoudigste manier om te stoppen is het toestel te herstarten. Wil je 'm
actief kunnen stoppen zonder herstart, dan kun je in een KUAL-terminal het
proces opzoeken (`ps | grep fetch_and_display`) en met `kill <pid>`
beëindigen.

## Problemen oplossen

- **Scherm ververst niet**: check `/mnt/us/extensions/kindle-dashboard/fetch.log`
  voor foutmeldingen van `wget` (bv. verkeerd IP/poort, of de TrueNAS-app
  staat niet aan).
- **Afbeelding verschijnt niet als screensaver**: het `SCREENSAVER_PATH` komt
  waarschijnlijk niet overeen met wat linkss verwacht — dit is de stap die
  het meest jouw eigen linkss-configuratie nodig heeft.
- **Ghosting/nabeelden op het e-inktscherm**: dit is normaal bij herhaalde
  partial refreshes. Het script gebruikt fbink's standaardinstellingen; als
  dit hindert, kun je in het script een periodieke volledige flash-refresh
  toevoegen (bv. elke N ververingen `fbink -f`).
