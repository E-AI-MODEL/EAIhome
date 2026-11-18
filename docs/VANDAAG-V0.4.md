# Vandaag: de eerste bruikbare werkweergave

**Status:** fictieve, lokale browserproef. Geen live mail, agenda, documenten, geauthenticeerde gebruiker of gedeelde werkomgeving.

## Wat kun je nu doen?

Open het scherm **Vandaag**. Je ziet apart:

- **Openstaand:** aangenomen taken. Een vraag in een mail hoort hier niet vanzelf thuis.
- **Nog te beoordelen:** mogelijke taken uit de fictieve Project Atlas-casus. Een voorstel is geen opdracht.
- **Afgerond of afgewezen:** eerdere taken en correcties blijven zichtbaar.
- **Andere ontwikkelingen:** een gerapporteerde toezegging of een voorgesteld besluit verschijnt niet als gewone taak.

Open bij een onderwerp **Bekijk bronnen en voorgeschiedenis**. De pagina toont het brondocument, een exact citaat, de SHA-256 en de gebeurtenistijd. Bij een correctie staat ook de opgegeven toelichting, uitdrukkelijk gemarkeerd als *niet door een identiteit gecontroleerd*.

Bij een **voorgestelde taak** kun je kiezen voor **Aannemen** of **Geen taak**. Bij een **aangenomen taak** kun je **Afronden** of **Niet van toepassing** kiezen. Geef in het formulier een reden op. De nieuwe toestand verschijnt direct na verzending. Na een herstart blijft de wijziging staan.

Je kunt ook de stand op eerdere testdatums bekijken. Deze historische weergave is bewust alleen-lezen. De tijdlijn vertelt wat op het gekozen moment bekend was, en verandert niets aan de huidige registratie.

## Starten op een Mac

De browserproef staat nog op branch `feat/today-local-ui-v0.4`, niet op `main`. Je moet de repository eerst op je Mac ophalen. Vereist: Git en Python 3.11 of nieuwer.

Open **Terminal** en voer het volgende complete blok uit. De map `~/Downloads/EAIhome-vandaag` mag nog niet bestaan.

```bash
cd ~/Downloads
git clone --branch feat/today-local-ui-v0.4 --single-branch https://github.com/E-AI-MODEL/EAIhome.git EAIhome-vandaag
cd EAIhome-vandaag
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
eaihome --home "$HOME/.local/share/eaihome-demo" work-ui
```

`python3 --version` moet 3.11 of hoger tonen. Stop bij een foutmelding en los die eerst op. Een oudere Python-versie vereist een nieuwe Python-installatie en een nieuwe `.venv`.

Bij een volgende keer: open Terminal, ga naar `~/Downloads/EAIhome-vandaag`, voer `source .venv/bin/activate` uit en start `eaihome --home "$HOME/.local/share/eaihome-demo" work-ui` opnieuw.

De lokale server blijft draaien zolang Terminal openstaat. Hij is niet bereikbaar als openbare website.

Open daarna in dezelfde computer:

**http://127.0.0.1:8765/**

Gebruik **Ctrl+C** om de lokale server te stoppen.

Het programma gebruikt uitsluitend `fixtures/scenarios/EAIhome_mockup_corrections.json` en de bijbehorende fictieve tekstbestanden. Er worden geen externe bestanden, fonts, scripts, beelden of AI-diensten geladen.

De opslag staat in `$HOME/.local/share/eaihome-demo/work-events.sqlite3`, **niet** in GitHub. Gebruik een nieuwe lege datamap als je opnieuw wilt beginnen. Geef de lokale datamap nooit mee aan een publieke commit of issue.

## Een oefening

1. Open **Vandaag**. Er staan twee voorgestelde taken en nog geen aangenomen open taken.
2. Open bij *Agenda controleren* de voorgeschiedenis. Je ziet de vraag uit de fictieve e-mail.
3. Kies **Status aanpassen** en daarna **Aannemen**. Vul een korte reden in.
4. Het werkpunt verschijnt onder **Openstaand**. Herlaad de pagina: de wijziging blijft.
5. Open het werkpunt opnieuw, kies **Afronden** en schrijf waarom.
6. Het werkpunt verschijnt onder **Afgerond of afgewezen**, met de volledige gebeurtenisgeschiedenis.
7. Stop de server en start hem opnieuw. Het resultaat blijft bewaard.
8. Kies een eerdere stand. Daar zie je de informatie zoals die toen geregistreerd was; de latere correctie wordt niet naar het verleden verplaatst.

## Waarom lokaal, en waarom fictief?

Er is nog geen echte authenticatie of autorisatie. Een ingevulde actornaam is **geen identiteitsbewijs**. De server draait uitsluitend op `127.0.0.1`, controleert het formulier en gebruikt een tijdelijke anti-CSRF-code. Dat zijn beschermingen voor een lokale **demo**, geen veilige basis voor persoonsgegevens of een online dienst.

Een bericht kan niet zelfstandig iets goedkeuren, taken op naam zetten of formele besluiten nemen. De lokale correctie wordt technisch als gebeurtenis opgeslagen, maar heeft geen bestuurlijke geldigheid. Er is geen koppeling met Outlook, SharePoint, Teams of andere werkomgevingen.

Ook een getoond citaat is niet automatisch voldoende bewijs voor de betekenis die eraan wordt gegeven. De bron moet inhoudelijk worden beoordeeld.

## Controle

De tests controleren HTTP-pagina's, echte lokale correcties, herstart, dubbele formulieren, verouderde revisies, historische alleen-lezen-weergave, HTML-escaping, onjuiste hostnamen, formulierherkomst en anti-CSRF. De overige eerdere corpus- en gebeurtenistests blijven draaien op Python 3.11, 3.12 en 3.13.

Deze tests zijn niet hetzelfde als een volledige gebruikstest op mobiel of met echte werkdocumenten. Een geautomatiseerde Chrome-/screenshotcontrole op de uiteindelijke gebruikersinterface moet nog worden toegevoegd.

## Ontwerpkeuze

We gebruiken een rustige pagina met dunne lijnen, gewone tekst en vier herkenbare secties. De meeste broninformatie staat achter **Bekijk bronnen en voorgeschiedenis**. Dat houdt het overzicht leesbaar zonder informatie te verbergen die nodig is om een correctie te beoordelen.

De volgende stap is de overgang van één fictief scenario naar meerdere rechtmatig gescheiden werkonderwerpen, met expliciete bron- en correctierechten. Daarna pas kan een dagelijkse weergave met echte informatie worden onderzocht.

Zie ook [ADR-0001](adr/ADR-0001-semantic-work-continuity.md), [werkcontinuïteit v0.2](WORK-CONTINUITY-V0.2.md) en [correcties bewaren v0.3](WORK-STORE-V0.3.md).
