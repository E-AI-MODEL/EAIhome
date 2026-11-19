# EAIhome

**Persoonlijke werkassistent, begonnen bij bronnen die je kunt controleren.**

De oorspronkelijke basis bevat een lokaal bronregister en een doorzoekbare SQLite-index. Deze ontwikkelbranch bevat daarnaast een **interactief canvas** met fictieve werkgegevens. De lege werkruimte krijgt vorm vanuit een vraag, zonder dat de bronstatus wordt herschreven.

## Werkt nu

- Originele bytes opslaan met SHA-256, bron-ID, herkomst, revisie en tijdvelden.
- Hetzelfde document meerdere keren registreren zonder duplicaten als onafhankelijke bronnen te tellen.
- CSV, Markdown, TXT, JSON en tekst uit EML lokaal verwerken.
- Alle documentversies doorzoeken met SQLite FTS5.
- Brongroepen filteren, integriteit controleren en de index opnieuw opbouwen.

## Proberen

Vereist Python 3.11+:

```bash
python -m pip install -e .
export EAIHOME_HOME="$HOME/.local/share/eaihome-demo"
eaihome init
eaihome add examples/ssov-v1.md --family voorbeeldkader --revision 1.0 --group owner
eaihome add examples/ssov-v2.md --family voorbeeldkader --revision 2.0 --group owner
eaihome index
eaihome versions voorbeeldkader
eaihome search "besluiten beoordelaars"
eaihome verify
```

Tests: `PYTHONPATH=src python -m unittest discover -s tests -v`.

## Grenzen

Nog geen PDF/DOCX-extractie, OCR, semantisch zoeken, AI-antwoorden, mail/agenda-sync, transcriptie, taakherkenning, dashboard of autorisatie van echte gebruikers. De zoekfunctie toont tekstfragmenten, geen bewezen uitspraken. Een toegangsgroep in de CLI is een testfilter, geen echte beveiliging.

**Let op: deze repo is openbaar.** Plaats nooit echte mails, leerlinggegevens, gespreksverslagen, bronbestanden of gegenereerde indexen in GitHub. Gebruik voor deze proef alleen fictieve gegevens.

Lees [het ontwerp](docs/ARCHITECTURE.md) en [de golden path](docs/GOLDEN-PATH.md).

## Fictieve mockupbestanden

Voor format- en importproeven staan 20 fictieve bestanden in [fixtures/mockups](fixtures/mockups). Bekijk de [formatmatrix](docs/MOCKUPS.md) voor de typen en de huidige importstatus.

## Werkcontinuïteit met fictieve gebeurtenissen

De eerste semantische proef reconstrueert een veranderende afspraak uit bronverwijzingen en expliciet geannoteerde gebeurtenissen. Probeer:

```bash
PYTHONPATH=src python -m eaihome work-demo --known-at 2026-11-19T11:00:00+01:00
```

Dit is **geen** automatische taakherkenning of echte gebruikersautorisatie. [Lees de proef en beperkingen](docs/WORK-CONTINUITY-V0.2.md).

## Correcties bewaren tijdens een fictieve proef

Met `work-correct` kun je een **fictieve** taak aannemen, afwijzen of afronden. `work-state` reconstrueert de werkstatus met de lokaal opgeslagen gebeurtenisgeschiedenis. De correcties blijven beschikbaar na herstart en na `index`.

Dit is nog geen gebruikersauthenticatie of automatische taakherkenning. [Probeer de lokale demo](docs/WORK-STORE-V0.3.md). Het bijbehorende SQLite-register blijft buiten GitHub.

## Live canvas: probeer eerst de HTML

**Zonder installatie:** download [EAIhome_live_canvas.html](demos/EAIhome_live_canvas.html) en open het bestand in een browser. Je begint op een zacht leeg canvas. Een vraag bouwt onderdelen op, zoals een tijdlijn, taken of een overlegvoorbereiding. Dit is een **vaste demomodus**, geen echte AI.

**Met een lokale LLM:** installeer Python 3.11+ en [Ollama](https://ollama.com/), en gebruik in deze branch:

```bash
python -m pip install -e .
ollama pull qwen3:4b
eaihome --home "$HOME/.local/share/eaihome-demo" work-canvas --model qwen3:4b
```

Open daarna `http://127.0.0.1:8765/` **op dezelfde computer**. Ollama kiest alleen welke vooraf toegestane onderdelen worden getoond. EAIhome vult die met fictieve, herleidbare gegevens; er worden geen echte bronnen of persoonsgegevens naar het model gestuurd. Zonder Ollama blijft de pagina in duidelijk gemarkeerde demomodus werken. Er is nog geen gebruikersautorisatie of productie-integratie.

[Volledige uitleg, grenzen en testaanpak](docs/LIVE-CANVAS-V0.5.md).
