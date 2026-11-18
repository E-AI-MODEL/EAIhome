# EAIhome architectuur v0.1

## Doel

Een persoonlijke werkassistent met controleerbare bronverwijzingen. Dit bouwblok is een lokale technische proef, geen productieassistent.

`bron -> SHA-256-object -> manifest.jsonl -> lokale extractie -> SQLite FTS5 -> tekstfragment met herkomst`

- **Bronnen:** originele bytes per SHA-256. Afzonderlijke imports blijven zichtbaar, gelijke bytes worden niet als onafhankelijk bewijs beschouwd.
- **Register:** append-only manifest, met bron-ID, familie, revisie, herkomst, tijdstippen en toegangsgroepen.
- **Zoekindex:** wegwerpbare SQLite FTS5-index, volledig herstelbaar uit origineel + register.
- **Revisies:** alle versies worden standaard gevonden; de code kiest niet automatisch de nieuwste of meest gezaghebbende bron.
- **Toegang:** groepen worden in de SQL-query gefilterd voor rangschikking. De CLI-groepsnaam is geen geauthenticeerde identiteit.

## Ontwerpregels

Bron, claim, taak en beslissing zijn aparte gegevensobjecten. Alleen `source` is nu geïmplementeerd. De overige types zijn geplande interfaces:

| Object | Status / regels |
| --- | --- |
| source | ontvangen, verwerkt, niet ondersteund; SHA-256, familie, herkomst |
| claim | EAIwork: unknown, assumption, claim, observed, checked, proven. Een taalmodel mag zijn eigen beweringen niet promoveren |
| task | voorgesteld, open, afgerond, verlopen; mens keurt acties goed |
| decision | voorgesteld, besproken, besloten, vastgelegd; menselijke verantwoordelijkheid |

De tijdvelden `source_updated_at`, `occurred_at` en `ingested_at` zijn niet uitwisselbaar. De revisie is een opgegeven label, geen automatisch geldigheidsoordeel.

## Hergebruik bestaande repositories

- [EAIwork-](https://github.com/E-AI-MODEL/EAIwork-): eventlog, bevoegdheden, bewijsstatussen en toestemming voor acties.
- [-rag-eat-starter-kit](https://github.com/E-AI-MODEL/-rag-eat-starter-kit): zoeken en EAT. De bestaande `family`-filter naar één recente versie nemen we bewust niet over.
- [project-pim](https://github.com/E-AI-MODEL/project-pim): inspectie en uitgaande privacycontrole; browsercode moet nog veilig aangepast worden.
- [EAT-inline](https://github.com/E-AI-MODEL/EAT-inline): tekstuele verwijzingen, niet een volledig persoonsregister.
- [shadowseed-pro](https://github.com/E-AI-MODEL/shadowseed-pro): verkennen van kandidaten en herkomst, niet het bronarchief.

## Veiligheid

**Geen vertrouwelijke schoolbestanden gebruiken in v0.1.** De repository is openbaar, maar de corpusbestanden, originele bytes en zoekindex horen uitsluitend lokaal. De huidige CLI heeft geen authenticatie, encryptie-at-rest, server-side PIM, volledige bewaartermijnen of intrekkingsverwerking. Echte persoonsgegevens mogen niet in broncode, CI-logs, issues of commits terechtkomen.

Extern versturen of uitvoeren is geen functie van deze versie. Bij de latere assistant-laag gelden bronfragmenten uitsluitend als data, niet als opdrachten. Het bevestigen van een actie maakt een inhoudelijke bewering niet automatisch bewezen.
