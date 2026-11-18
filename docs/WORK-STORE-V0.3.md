# EAIhome: correcties onthouden na een herstart

**Status:** lokale fictieve ontwikkelproef, niet geschikt voor persoonsgegevens.  
**Gebaseerd op:** [ADR-0001](adr/ADR-0001-semantic-work-continuity.md) en de [eerste werkcasus](WORK-CONTINUITY-V0.2.md).  
**Geen werkende identiteit, takenherkenning, externe berichten, AI-provider of productieautorisatie.**

## Wat is nu anders?

Een gebruiker kan in de fictieve casus expliciet vastleggen dat een voorgestelde taak geen taak was, een taak accepteren of als afgerond markeren, of een gerapporteerde toezegging bevestigen of intrekken. De oorspronkelijke mail of het document wordt niet gewijzigd.

De nieuwe lokale gebeurtenissen staan in **`work-events.sqlite3`**, los van de wegwerpbare `index.sqlite3`. Daardoor blijven ze beschikbaar na het opnieuw bouwen van de zoekindex en na een herstart van het programma. Het programma berekent de zichtbare werkstatus steeds opnieuw uit oorspronkelijke, gecontroleerde demo-gebeurtenissen en de toegevoegde correcties.

Een lokale correctie wordt geregistreerd als `unverified_local_operator_note`. Het veld `actor_ref` is uitsluitend een zelf ingevuld label, **geen gecontroleerde identiteit of bevoegdheid**. De status mag dus niet worden gebruikt als echt administratief bewijs.

## Zelf uitproberen

Gebruik Python 3.11+ in de repository en uitsluitend de meegeleverde fictieve gegevens:

```bash
export PYTHONPATH=src
export EAIHOME_HOME="$PWD/.eaihome"

# Eerst zijn beide taken alleen voorgesteld.
python -m eaihome work-state --known-at 2026-11-18T15:00:00+01:00

# Leg vast: de vraag uit een e-mail was geen opdracht.
python -m eaihome work-correct \
  --subject task_demo_a \
  --event task.dismissed \
  --actor lokale-testgebruiker \
  --reason "De vraag was geen aanvaarde opdracht" \
  --expected-revision 1 \
  --request-id atlas-review-0001

# Ook na een nieuwe aanroep wordt de correctie teruggevonden.
python -m eaihome work-state --known-at 2099-01-01T00:00:00+00:00

# Index opnieuw opbouwen: eerdere correctie blijft bewaard.
python -m eaihome index
python -m eaihome work-state --known-at 2099-01-01T00:00:00+00:00

# Dezelfde aanvraag opnieuw versturen mag niet een tweede correctie maken.
python -m eaihome work-correct \
  --subject task_demo_a \
  --event task.dismissed \
  --actor lokale-testgebruiker \
  --reason "De vraag was geen aanvaarde opdracht" \
  --expected-revision 1 \
  --request-id atlas-review-0001
```

Bij die laatste aanvraag verschijnt `"replayed": true`. Een verzoek met dezelfde ID maar andere inhoud wordt geweigerd. Gebruik voor een **nieuwe** wijziging een **nieuwe** `request-id` en de actuele `revision` van de betrokken taak.

Wil je liever beide voorgestelde taken behouden en alleen een taak accepteren? Gebruik een aparte datamap en `task.accepted` op `task_demo_a`. Na die acceptatie kan `task.completed` met `--expected-revision 2` worden vastgelegd. De toestand vóór de bevestiging blijft historisch opvraagbaar.

## Tijden en revisies

Twee vragen blijven gescheiden:

- `known_at`: welke gebeurtenissen waren op dat moment al geregistreerd?
- `effective_at`: welke gebeurtenissen waren volgens hun opgegeven ingangsdatum van toepassing?

Een correctie die om 17.00 uur is ingevoerd maar om 16.00 uur geldt, verschijnt niet in een overzicht van wat om 16.30 uur al bekend was. De tekst uit het bronbestand mag die tijdstippen niet zelf voorschrijven.

Elk werkobject heeft een revisienummer: het aantal oorspronkelijke en latere gebeurtenissen dat ervoor is vastgelegd. Een wijziging vereist `expected_revision`. Een andere bewerker die eerst heeft geschreven, verhoogt de revisie. De volgende aanvraag met de oude revisie wordt in één SQLite-transactie geweigerd. Dit beschermt ook tegen een tussentijdse statuswijziging die later weer wordt teruggedraaid.

## Wat is opgeslagen?

In één lokale database staat één vast fictief scenario met:

- case-ID, context-ID en SHA-256 van het scenario;
- een append-only tabel met getypeerde correctiegebeurtenissen;
- oorspronkelijke verzoek-ID, reden, actorlabel, registratietijd, ingangsdatum, verwachte revisie en werkelijk toegekende revisie;
- een hashketen over de exacte JSON van iedere opgeslagen gebeurtenis.

De hashketen detecteert onbedoelde of eenvoudige handmatige wijzigingen aan een rij. **Ze bewijst niet wie iets heeft geschreven** en beschermt niet tegen iemand die de hele database en alle hashes kan herschrijven. Er is nog geen externe ondertekening of recoverydienst.

SQLite verzorgt de lokale transactie. Eén nieuw werkpunt tegelijk wordt opgeschreven; concurrente writes gebruiken `BEGIN IMMEDIATE`. Er is geen synchronisatie tussen apparaten of meerdere installaties.

De opgegeven `--scenario` wordt op basis van de SHA-256 vastgezet. Een gewijzigde scenario-inhoud of andere context kan niet stilzwijgend met oude correcties worden gecombineerd. Daarvoor is later een expliciete migratie nodig.

## Begrensde overgangsregels

| Bronstatus | Gebeurtenis | Nieuwe status |
| --- | --- | --- |
| `proposed` taak | `task.accepted` | `accepted` |
| `proposed` of `accepted` taak | `task.dismissed` | `dismissed` |
| `accepted` taak | `task.completed` | `completed` |
| `reported` toezegging | `commitment.confirmed` | `confirmed` |
| `reported` of `confirmed` toezegging | `commitment.cancelled` | `cancelled` |

Formele besluitvorming ontbreekt bewust: `decision.decided`, rechtenverlening, verzending en wijziging van echte bronsystemen zijn in deze demo niet beschikbaar.

## Wat moet nog worden gebouwd?

- Server-side gebruikersidentiteit en gecontroleerde bevoegdheden. De CLI mag niet als productieautorisatie worden gebruikt.
- Een echt eventregister met bron- en annotatie-ID's, JSON Schema-versies, contextscheiding voor meerdere dossiers en bewaartermijnen.
- Correcties bij wijzigingen in echte documenten, bronrechten, herkomst, revisie en verwijdering.
- Bronankers voor PDF, DOCX, Excel, PowerPoint en agenda-items in plaats van uitsluitend demo-tekstbestanden.
- Automatische **kandidaat**-extractie, gevolgd door afzonderlijke inhoudelijke beoordeling. Een model mag niet zelfstandig taakacceptatie of formele besluiten vastleggen.
- Een eerste scherm **Vandaag** waarop een correctie zichtbaar kan worden aangebracht en de voorgeschiedenis kan worden gecontroleerd.

## Testen

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

De tests gebruiken alleen fictieve bestanden en tijdelijke datamappen. Ze toetsen onder andere herstart, historische tijdsbeelden, herindexering, dubbele aanvragen, version-conflicten, ongeldige statusovergangen, herkomstverwisseling en wijziging van lokaal opgeslagen eventbytes.

**Belangrijk:** de echte corpusbestanden en de lokale database horen niet in de openbare GitHub-repository. `.eaihome/` en `*.sqlite3` worden door `.gitignore` uitgesloten.
