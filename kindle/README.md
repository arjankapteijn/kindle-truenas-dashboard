# Kindle-kant: dashboard ophalen en tonen

Dit is de tegenhanger van de `kindle-truenas-dashboard`-app op TrueNAS: een
scriptlet die op de Kindle zelf draait, de laatste dashboard-PNG ophaalt en
als screensaver toont — geverst vlak vóór elke keer dat het toestel gaat
slapen (zie "Hoe de verversing werkt" hieronder).

**Status:** volledig geverifieerd op een jailbroken Kindle Voyage
(2026-07-27), inclusief het event-gedreven ophalen. Twee eerdere pogingen
faalden onderweg (zie "Hoe de verversing werkt" voor de volledige
geschiedenis): eerst een vaste 5-minuten-polling die urenlang stilviel
zodra het toestel écht sliep, daarna een event-filter
(`goingToScreenSaver` als los argument bij `lipc-wait-event`) dat om
onduidelijke reden nooit vuurde. Een losse diagnose-log
(`lipc-wait-event -mt "com.lab126.powerd" "*"`, zie `diagnose_events.sh`)
bevestigde dat het event er wél is en zelf filteren op de regel wél werkt
— dat is de uiteindelijke opzet hieronder.

## Vereisten (al aanwezig volgens jouw opzet)

- WinterBreak2-jailbreak + hotfix
- KUAL + MRInstaller ("MR Installer" v1.6, NiLuJe), werkend
- **linkss** ("K5 FW 5.x ScreenSavers Hack", v0.25.N) — zo niet:
  1. Het volledige installatiearchief staat al in deze repo:
     [`vendor/kindle-linkss-0.25.N-r18981.tar.xz`](vendor/kindle-linkss-0.25.N-r18981.tar.xz)
     (oorspronkelijk gedownload van de
     [Snapshots-thread](https://www.mobileread.com/forums/showthread.php?t=225030),
     zie de [hoofdthread](https://www.mobileread.com/forums/showthread.php?t=195474)
     voor de volledige discussie/herkomst — bewaard zodat een verdwenen
     forumlink dit niet blokkeert).
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
   slaap om te controleren of het dashboard verschijnt (**met de USB-kabel
   los** — aan USB hangend doorloopt een Kindle de normale
   slaap/screensaver-flow niet, je ziet dan hooguit het scherm dimmen).
   Dit hoef je **niet** te herhalen bij elke ververing — het script
   overschrijft steeds dezelfde bestandsnaam, dus de bestandenlijst zelf
   verandert niet meer.

   **Waarschuwing:** gebruik "Restart framework now" ná deze allereerste
   keer **niet** meer als troubleshooting-stap. Linkss' `shuffless`
   hernoemt/bevriest bij elke restart de op dat moment aanwezige
   `dashboard.png` naar zijn eigen `bg_ssNN.png`-schema — je krijgt dan
   twee bestanden in `screensavers/` (het bevroren oude en het door het
   script ververste nieuwe), die linkss om-en-om blijft tonen. Zag je dit
   toch gebeuren (een `bg_ss00.png` naast `dashboard.png`)? Verwijder
   gewoon het `bg_ss*.png`-bestand, `dashboard.png` blijft dan het enige.

## Hoe de verversing werkt

Het script blijft op de achtergrond draaien, maar polt niet blind op een
vaste interval. In plaats daarvan monitort het **alle**
`com.lab126.powerd`-events via `lipc-wait-event -mt "com.lab126.powerd" "*"`
en filtert zelf (met een `case`-statement) op de regels die
`goingToScreenSaver` bevatten — op dát moment haalt het **meteen** de
laatste dashboard-PNG op, precies vlak voordat linkss de screensaver
samenstelt, dus de data is zo vers als redelijkerwijs mogelijk.

**Twee doodlopende paden onderweg, voor de volgende keer dat dit iets
soortgelijks nodig heeft:**
- `goingToSleep` als event-naam: bestaat niet binnen `com.lab126.powerd`,
  vuurde dus nooit.
- `lipc-wait-event -m com.lab126.powerd goingToScreenSaver` (event-naam als
  los argument): de event-náám bleek wel te kloppen — bevestigd via
  [deze blogpost over Kindle-huisautomatisering](https://blog.davidv.dev/posts/integrating-a-kindle-into-house-automation/)
  én via onze eigen `diagnose_events.sh`-log op dit toestel — maar deze
  manier van filteren gaf op dit toestel, ook na een hele nacht echte
  sleep-cycli, geen enkele hit. Vermoedelijk ongeldige/andere syntax voor
  het event-argument op deze firmware; niet verder uitgezocht omdat de
  wildcard-vorm hieronder gewoon werkt.
- **Wat wel werkt** (bevestigd via `diagnose_events.sh`, dat exact
  `lipc-wait-event -mt "com.lab126.powerd" "*"` gebruikt en alle events
  blijft loggen): alles monitoren en zelf op de tekst `goingToScreenSaver`
  matchen, zoals het script nu doet.
- **Nog een addertje na dat alles**: zodra het event goed binnenkwam, faalde
  `wget` alsnog een paar keer op rij (geverifieerd in `fetch.log`: "ophalen
  mislukt" direct na een echte, losgekoppelde sleep-cyclus). WiFi staat op
  dit toestel namelijk na wat inactiviteit al uit, óók als het toestel zelf
  nog niet slaapt — het `goingToScreenSaver`-event zet dat niet vanzelf
  weer aan. `fetch_once()` doet daarom eerst
  `lipc-set-prop com.lab126.cmd wirelessEnable 1` en probeert de download
  vervolgens tot 5x met een korte timeout, in plaats van na één mislukte
  poging al op te geven. In het slechtste geval (WiFi komt niet op tijd
  omhoog) duurt dat ~25 seconden voor het opgeeft en de vorige afbeelding
  laat staan.

Waarom niet gewoon elke 5 minuten pollen? Dat was de oorspronkelijke opzet,
maar op dit toestel bleek `fetch.log` gaten van 1,5 tot 2,5 uur te tonen
in plaats van 5 minuten: een Kindle die écht slaapt, zet WiFi (en
waarschijnlijk het achtergrondproces zelf) uit om batterij te sparen,
waardoor de lus alleen draait als het toestel toevallig om een andere
reden wakker is. Event-gedreven ophalen lost dat op zonder dat we iets aan
het systeem zelf hoeven te wijzigen.

Als `lipc-wait-event` onverwacht ontbreekt op jouw firmware, valt het
script automatisch terug op de oude vaste-interval-polling (elke 5
minuten) — check `fetch.log` om te zien welke modus actief is.

Je hebt zelf gekozen voor **handmatig starten via KUAL** i.p.v. automatisch
bij boot — dat betekent: na een herstart of USB-verbinding moet je de loop
opnieuw starten via hetzelfde KUAL-menu.

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
- **Scherm ververst niet, of ververst maar met grote tussenpozen (uren
  i.p.v. bij elke sleep)**: check `/mnt/us/extensions/kindle-dashboard/fetch.log`.
  - Staat er "lipc-wait-event niet gevonden, terugval op vaste interval"?
    Dan draait het script in de oude polling-modus, die op dit toestel
    aantoonbaar urenlang stilviel zodra het écht sliep (WiFi gaat dan uit).
    Dat is de kernreden voor het event-gedreven ontwerp — als
    `lipc-wait-event` op jouw firmware ontbreekt, is verder uitzoeken nodig
    waarom (mogelijk een andere padnaam of firmwareversie).
  - Staat er wel "wacht op goingToScreenSaver-events" maar komen er geen
    nieuwe regels bij na een echte sleep-cyclus (aan/uit-knop kort
    ingedrukt, niet alleen het scherm laten dimmen)? Gebruik dan het
    **tweede KUAL-menu-item "Diagnose: log alle powerd-events"**
    (`diagnose_events.sh`) — geen terminal nodig. Dat logt élk
    `com.lab126.powerd`-event naar `events.log`, dus je ziet zwart-op-wit
    of en welke events er echt langskomen bij het slapen gaan.
  - Foutmeldingen van `wget` zelf (verkeerd IP/poort, TrueNAS-app staat
    niet aan) staan er ook gewoon tussen.
- **Script ververst prima (`fetch.log` toont "dashboard ververst" en
  `dashboard.png` staat in `screensavers/`), maar het scherm toont nog
  gewoon de standaard-Kindle-screensaver of alleen een oude stand**:
  - Test je met de USB-kabel nog aangesloten? Ontkoppel 'm eerst — aan USB
    hangend doorloopt een Kindle de normale slaap/screensaver-flow niet.
  - Staat er een `bg_ss*.png` náást `dashboard.png` in `screensavers/`?
    Dan is ooit "Restart framework now" gebruikt ná de allereerste
    installatiestap, wat de toenmalige `dashboard.png` bevroor onder een
    andere naam (zie de waarschuwing bij stap 5 hierboven). Verwijder dat
    `bg_ss*.png`-bestand — niet opnieuw op "Restart framework now" drukken,
    dat bevriest gewoon de volgende ronde weer.
  - Heb je de allereerste installatiestap (stap 5) nog nooit gedaan? Doe
    die eenmalig.
- **Nog steeds geen dashboard na het opruimen hierboven**: heeft dit toestel
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
