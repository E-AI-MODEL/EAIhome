# EAIhome mockups

Alle bestanden zijn fictief. Het is een testset, geen echte werkadministratie.

De plaats is steeds `fixtures/mockups/<formaat>/EAIhome_mockup_<naam>.<extensie>`. De Word-test heet op verzoek `EAIhome_mockup_doc.docx`. Het is een echt modern Word-bestand, geen oud binair .doc-bestand.

Alle 20 bestanden verwijzen naar `EAIHOME-DEMO-001`, een verzonnen Project Atlas. Actie `ACT-001` staat nog open, `ACT-002` is afgerond. Het besluit is uitsluitend voorgesteld. Twee e-mails vormen een thread en de Markdown-bestanden vertegenwoordigen revisie 1 en 2.

| Format | Bestanden | Verwerking EAIhome v0.1 |
| --- | --- | --- |
| Word .docx | 1 | Nog niet ondersteund |
| Excel .xlsx | 1 | Nog niet ondersteund |
| PowerPoint .pptx | 1 | Nog niet ondersteund |
| PDF .pdf | 1 | Nog niet ondersteund |
| E-mail .eml | 2 (inkomend en antwoord) | Tekst wordt geïndexeerd |
| Kalender .ics | 1 | Nog niet ondersteund |
| Markdown .md | 2 (versies) | Tekst wordt geïndexeerd |
| TXT, CSV, JSON | 3 | Tekst wordt geïndexeerd |
| HTML, XML, YAML, vCard | 4 | Nog niet ondersteund |
| PNG, JPG | 2 | Nog niet ondersteund |
| WAV | 1 | Nog niet ondersteund; uitsluitend een toon, geen spraak |
| ZIP | 1 | Nog niet ondersteund |

De JSON in `manifest.json` bevat voor elk bestand de naam, bytes, SHA-256, case-ID en verwachte importstatus. De tests controleren echte bestandsheaders en Office-ZIP-structuur, de integriteit van alle bestanden, en of EAIhome onleesbare bestandstypen daadwerkelijk als niet ondersteund markeert.

## Opnieuw genereren

Installeer de hulpmiddelen en voer het Python-script uit vanaf de root:

```bash
python -m pip install -r tools/requirements-mockups.txt
npm install --prefix tools --no-save --no-package-lock pptxgenjs
python tools/generate_binary_mockups.py
PYTHONPATH=src python -m unittest discover -s tests -v
```

De generator gebruikt python-docx, openpyxl, ReportLab, Pillow en PptxGenJS. Alle brongegevens zijn fictief; een externe AI of live connector wordt niet aangeroepen.

*Opmerking:* de testgroepen in de huidige CLI zijn géén geauthenticeerde toegangscontrole. Bewaar geen echte persoonlijke bestanden in deze openbare repository.
