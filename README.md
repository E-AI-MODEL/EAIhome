# EAIhome

**Persoonlijke werkassistent, begonnen bij bronnen die je kunt controleren.**

Deze repository bevat v0.1: een lokaal bronregister, versiebeheer en een doorzoekbare SQLite-index. Het is nog geen AI-assistent en nog geen dashboard.

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
