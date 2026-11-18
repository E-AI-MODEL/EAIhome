# Werkcontinuiteit: eerste fictieve proef

Deze proef laat voor Project Atlas zien hoe EAIhome uit een **handmatig beoordeelde gebeurtenislijst** de stand van werk kan reconstrueren. De annotaties staan in een JSON-scenario, met broncitaten en SHA-256 van de echte mockupbestanden. Er draait geen taalmodel. Actornamen in het scenario zijn niet geauthenticeerd.

**Waarom dit eerst:** een mailvraag mag geen aanvaarde taak worden; een toezegging is niet hetzelfde als uitvoering; de annulering van een overleg trekt een afzonderlijke toezegging niet automatisch in; een besproken voorstel is geen vastgesteld besluit.

## Proberen

Start vanuit de repository met Python 3.11 of nieuwer:

```bash
PYTHONPATH=src python -m eaihome work-demo --known-at 2026-11-18T11:10:00+01:00
PYTHONPATH=src python -m eaihome work-demo --known-at 2026-11-19T11:00:00+01:00
PYTHONPATH=src python -m eaihome work-demo --known-at 2026-11-20T11:00:00+01:00
PYTHONPATH=src python -m eaihome work-demo --known-at 2026-11-20T13:00:00+01:00 --effective-at 2026-11-20T11:00:00+01:00
```

Op 18 november is ACT-001 alleen voorgesteld. Op 19 november staat de taak na de fictieve handmatige bevestiging open. Op 20 november om 11.00 uur was de afronding volgens de registratie nog niet bekend; om 13.00 uur is die wel bekend en geldt deze met ingang van 10.00 uur. Het besluit blijft `discussed`. De agenda-annulering verandert de taakstatus niet. ACT-002 wordt na een fictieve correctie als `dismissed` weergegeven.

## Grenzen

- **Geen automatische taakherkenning:** alle gebeurtenistypen zijn vooraf in `fixtures/scenarios/EAIhome_mockup_work_scenario.json` geannoteerd.
- **Geen betrouwbare menselijke identiteit of autorisatie:** de demo controleert wel toegestane actorsoorten bij statusovergangen, maar een vermelding `person` in JSON is geen identiteitsbewijs. `decision.decided` is om die reden niet beschikbaar.
- **Geen echte corpusintegratie:** de verwijzingen richten zich op gecontroleerde fictieve bronbestanden, niet op een productie-index of live mail/agenda.
- **Geen semantisch bewijs:** een exact citaat met een juiste SHA-256 bevestigt de vindplaats, niet de interpretatie.
- **Geen opslag of externe acties:** de tijdlijn wordt tijdens een CLI-aanroep berekend, zonder documenten of agenda-items te veranderen.
- **Geen productie-bitemporaliteit:** twee tijdassen werken voor deze vastgelegde voorbeeldtijdlijn; retroactieve conflicten, verschoven rechten en gesynchroniseerde providers vragen aparte tests.

De negatieve tests controleren onder meer verkeerde bronhashes en citaten, contextvermenging, onbevoegde modelovergangen, dubbele event-ID's, ongeldige tijden en onmogelijke statusovergangen.

**Vervolg:** echte JSON-schema's en een eventstore waarin herkomst, versies, menselijke correcties en rechten worden vastgelegd. Pas na die stap bouwen we de eerste weergave **Vandaag**.
