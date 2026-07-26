# Kindle-kant: dashboard ophalen en tonen

Dit is de tegenhanger van de `kindle-truenas-dashboard`-app op TrueNAS: een
scriptlet die op de Kindle zelf draait, elke 5 minuten de laatste
dashboard-PNG ophaalt en als screensaver toont.

**Status:** volledig geïnstalleerd en werkend geverifieerd op een jailbroken
Kindle Voyage (2026-07-26) — inclusief linkss-installatie, KUAL-menu-integratie
en het daadwerkelijk tonen van het dashboard als screensaver.

## Vereisten (al aanwezig volgens jouw opzet)

- WinterBreak2-jailbreak + hotfix
- KUAL + MRInstaller ("MR Installer" v1.6, NiLuJe), werkend
- **linkss** ("K5 FW 5.x ScreenSavers Hack", v0.25.N) — zo niet:
  1. Download het pakket van de
     [Snapshots-thread](https://www.mobileread.com/forums/showthread.php?t=225030)
     (of de [hoofdthread](https://www.mobileread.com/forums/showthread.php?t=195474)).
  2. Pak het uit en zet **`Update_linkss_0.25.N_install_pw2_and_up.bin`**
     (dit is de variant voor de Kindle Voyage — linkss groepeert 'm bij
     "PW2 en nieuwer": PW2/KT2/KV/PW3/KOA/KT3/KOA2/PW4/KT4/KOA3/PW5; **niet**
     de `_install_touch_pw.bin`-variant, die is voor de originele Touch/PW1)
     in `/mnt/us/mrpackages/`.
  3. Eject & unplug de Kindle, open dan op het toestel zelf **KUAL → Helper →
     Install MR Packages** (dat is MRInstaller/MRPI).
  4. Na de herstart: zet de Kindle in slaap en controleer of er een
     bevestigings-screensaver verschijnt — dat betekent dat de installatie
     is gelukt.
  5. Verwijder de meegeleverde placeholder-afbeelding(en)
     (`00_you_can_delete_me*.png`) uit `/mnt/us/linkss/screensavers/` zodat
     straks alleen `dashboard.png` in die map staat (zie hieronder waarom).
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
   - `SCREENSAVER_PATH` — staat standaard op
     `/mnt/us/linkss/screensavers/dashboard.png`. Zolang dit het enige
     bestand in die map is (zie de placeholder-opruimstap hierboven), toont
     linkss altijd deze afbeelding.
3. Zorg dat het script uitvoerbaar is: `chmod +x fetch_and_display.sh`
   (via een KUAL-terminal, of via USB als je bestandsbeheer permissies
   behoudt).
4. Open KUAL op de Kindle → in het **hoofdmenu** (niet in een submenu) moet nu
   een nieuwe ingang **"TrueNAS-dashboard"** staan (uit `config.xml` +
   `menu.json`, die direct in `kindle-dashboard/` moeten staan — KUAL
   negeert deze extensie stilzwijgend als `config.xml` in een submap staat)
   → open die en kies **"Start TrueNAS-dashboard refresh-loop"**.
5. **Eenmalig na deze allereerste start:** wacht tot `fetch.log` een geslaagde
   ronde toont, en herstart daarna het linkss-framework via **KUAL → Screen
   Savers → Restart framework now**. Linkss neemt wijzigingen in de
   inhoud van `screensavers/` (zoals de placeholder die je net verwijderd
   hebt en het nieuwe `dashboard.png`) pas mee na zo'n herstart — zonder
   deze stap blijft gewoon de standaard-Kindle-screensaver zichtbaar, ook al
   ververst het script prima op de achtergrond. Zet de Kindle daarna in
   slaap om te controleren of het dashboard verschijnt. Dit hoef je **niet**
   te herhalen bij elke 5-minuten-ververing — het script overschrijft steeds
   dezelfde bestandsnaam, dus de bestandenlijst zelf verandert niet meer.

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

- **Menu-ingang "TrueNAS-dashboard" verschijnt niet in KUAL**: KUAL leest
  `config.xml` alleen als die direct in `/mnt/us/extensions/kindle-dashboard/`
  staat (niet in een submap) en de `<id>` daarin moet exact gelijk zijn aan
  de mapnaam (`kindle-dashboard`). Herstart KUAL (of het toestel) na het
  kopiëren — nieuwe extensies worden niet altijd meteen opgepikt.
- **Scherm ververst niet**: check `/mnt/us/extensions/kindle-dashboard/fetch.log`
  voor foutmeldingen van `wget` (bv. verkeerd IP/poort, of de TrueNAS-app
  staat niet aan).
- **Script ververst prima (`fetch.log` toont "dashboard ververst" en
  `dashboard.png` staat in `screensavers/`), maar het scherm toont nog
  gewoon de standaard-Kindle-screensaver**: dit is vrijwel altijd het
  gemiste "eenmalige herstart"-stapje hierboven — **KUAL → Screen Savers →
  Restart framework now**, dan opnieuw in slaap zetten.
- **Nog steeds geen dashboard na de framework-herstart**: heeft dit toestel
  "Special Offers" (advertenties op het vergrendelscherm)? Linkss kan dat
  niet overschrijven — dan zie je op het vergrendelscherm altijd een
  advertentie in plaats van de custom screensaver. Controleer via
  Instellingen → Mijn Account of "Special Offers" vermeld staat.
- Controleer anders in **KUAL → Screen Savers → Screen Savers Behavior** of
  "Image Cycle" is aangevinkt (niet "Cover" of "Last Screen" — dat gebruikt
  respectievelijk de laatst geopende boekomslag of het laatste scherm i.p.v.
  de map `screensavers/`).
- **Ghosting/nabeelden op het e-inktscherm**: dit is normaal bij herhaalde
  partial refreshes. Het script gebruikt fbink's standaardinstellingen; als
  dit hindert, kun je in het script een periodieke volledige flash-refresh
  toevoegen (bv. elke N ververingen `fbink -f`).
