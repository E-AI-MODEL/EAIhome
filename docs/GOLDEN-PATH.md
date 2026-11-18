# Golden path v0.1

Het eerste bewijs moet technisch en herhaalbaar zijn. Geen grote interface voordat de bronnen betrouwbaar worden verwerkt.

**Invoer:** kies een lokaal bestand, vul familie en revisie in en eventueel herkomst, datum en groepslabel. De importer schrijft een bronrecord en bewaart de originele bytes onder SHA-256.

**Verwerking:** lokale extractie van UTF-8 Markdown, tekst, CSV, JSON en tekst uit EML. PDF/DOCX, afbeeldingen en audio worden vooralsnog `unsupported_format` en niet geïndexeerd.

**Index:** bouw SQLite FTS5 opnieuw op na een controle van alle bron-hashes. Alle revisies blijven aanwezig.

**Retrieval:** zoek een fragment. Toon herkomst, familie, versie, bronhash en tekst. Dedupliceer gelijke bytes zonder extra onafhankelijk bewijs te claimen.

**Toets:** tests controleren verschillen tussen revisies, toegangsgroepen, duplicaten, manipulatie van originelen, niet ondersteunde formaten en herstel na verwijderen van de index.

## Hierna

1. Vast broncontract voor M365, mail, agenda, documenten en transcripties, inclusief wijziging/intrekking.
2. Bewezen identiteit, persoonlijke autorisatie, privacycontrole, bewaartermijnen en verwijdering.
3. Gebeurtenis- en relatieverwerking, statusregels van EAIwork en entiteitsherkenning.
4. Mogelijke taken signaleren, laten bevestigen en pas daarna uitvoeren.
5. Een dashboard en bronbewuste documentproductie.

Dagelijkse route: `bron -> controle -> mogelijk open punt -> voorstel -> menselijke toestemming -> uitvoering -> audit`. Er komt geen automatische externe actie zonder toestemming.
