# EAIhome: het canvas ontstaat vanuit je vraag

**Status:** eerste interactieve proef, uitsluitend met fictieve Project Atlas-gegevens. Deze versie vervangt de eerder voorgestelde vaste `Vandaag`-interface als richting voor de gebruikersomgeving. De semantische bron- en correctielogica uit de eerdere stappen blijft bruikbaar.

## Probeer meteen de vormgeving

Open `demos/EAIhome_live_canvas.html` rechtstreeks als HTML-bestand in een browser. Daarvoor heb je geen Python, account, Terminal of internet nodig. Je begint met een bijna leeg canvas. Stel een vraag, gebruik een voorbeeldvraag of schrijf: `Laat de tijdlijn zien`. Het canvas bouwt passende onderdelen op. Je kunt de bronfragmenten openklappen, onderdelen vastzetten, verbergen en weer een leeg canvas maken.

**Duidelijke beperking:** dit losse HTML-bestand gebruikt vaste demoregels. Het is geen echte LLM en kent je echte documenten niet. Die beperking staat ook zichtbaar in de interface.

## Met een lokale LLM

De Python-app kan daarnaast een lokaal draaiend model in **Ollama** gebruiken. De app roept uitsluitend `http://127.0.0.1:11434` aan. Er is geen ChatGPT-, Claude- of andere cloudverbinding.

De LLM kiest **alleen de samenstelling** van de werkruimte. Het model krijgt je vraag en een beperkte lijst component-ID's:

`overview`, `tasks`, `timeline`, `sources`, `prep`, `document`.

Het model stuurt een JSON-object terug, bijvoorbeeld `{"panels":["timeline","sources"]}`. Het mag geen nieuwe feiten, namen, statussen, besluiten, HTML, scripts of externe acties toevoegen. Alleen de vooraf bepaalde componenten worden getekend en gevuld met gecontroleerde fictieve brongegevens uit `CorrectionStore`.

De indelingsopdracht zelf kan nog wel een gevoelige vraag bevatten. Gebruik daarom ook voor de lokale proef geen vertrouwelijke persoonsgegevens. Het systeem koppelt in deze fase geen echte bronnen aan een model.

### Starten op een Mac

Voor de lokale LLM-route heb je Python 3.11+ en een geïnstalleerde en gestarte Ollama nodig. Installeer vanuit de juiste EAIhome-repositorybranch in een virtuele omgeving en voer uit:

```bash
python -m pip install -e .
ollama pull qwen3:4b
eaihome --home "$HOME/.local/share/eaihome-demo" work-canvas --model qwen3:4b
```

Open daarna op dezelfde Mac `http://127.0.0.1:8765/`. Het lokale model moet in Ollama al beschikbaar zijn. Een download vindt alleen plaats via de expliciete `ollama pull`-opdracht, nooit automatisch vanuit EAIhome.

Een ander reeds geïnstalleerd model kiezen kan met `--model MODELNAAM`. EAIhome vraagt via Ollama `GET /api/tags` of het model bestaat en gebruikt `POST /api/generate` voor JSON-output.

Zonder Ollama blijft dezelfde lokale pagina bruikbaar met **demoregels**. Dat wordt expliciet gemeld; we doen niet alsof een lokaal model heeft geantwoord.

## Wat deze proef nog niet kan

- Je eigen bestanden, mailbox, agenda, Teams of SharePoint lezen.
- Nieuwe taken of besluiten zelfstandig herkennen en als geldig vastleggen.
- Een echte gebruikersidentiteit of rechten voor meerdere personen controleren.
- De inhoud van een document inhoudelijk laten beoordelen door het model.
- Externe acties uitvoeren of bestanden versturen.
- Een model zonder aparte lokale installatie vanuit het losse HTML-bestand draaien.

De `work-correct`- en `work-state`-functies blijven afzonderlijk beschikbaar. De nieuwe canvasproef verandert geen werkstatus of bronbestanden. Vaste, fictieve data dienen als toegestane eerste proef voordat echte bronnen en bevoegdheden worden toegevoegd.

## Waarom dit ontwerp

De gebruiker hoeft geen dashboard te beheren. Een vraag bepaalt wat verschijnt. De oorspronkelijke bron, bekende status en eerder vastgelegde correcties blijven onder de vormgeving beschikbaar. Het canvas kan andere vormen aannemen zonder dat het systeem feiten gaat verzinnen of de gebruiker ongemerkt handelingen laat uitvoeren.

De stijl gebruikt een zachte lichte achtergrond, ruim wit, dunne lijnen, rustige typografie en subtiele beweging. Geen vaste sidebar, geen reeks standaardbeheerkaarten bij het openen. De visuele opbouw is gebaseerd op de door de gebruiker beschreven *Wonderful AI Heaven*-scène uit de ZAAM-voorbereiding; het oorspronkelijke ZAAM-HTML-bestand dient als ontwerpverwijzing, niet als code-afhankelijkheid.

## Testen

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

De tests controleren de server, lokale bronafbakening, modelplanning, HTTP-verzoeken en het weigeren van onbekende componenten of ongewenste requests. De losstaande HTML is ook visueel en interactief gecontroleerd op desktop en mobiel met een headless Chromium-proef; dat is geen praktijkproef op de Mac of iPhone van de gebruiker.