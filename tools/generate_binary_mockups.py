#!/usr/bin/env python3
"""Build real, fictional mockup files. Do not use personal data."""
from __future__ import annotations
import hashlib, json, math, struct, subprocess, wave, zipfile
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "mockups"
CASE = "EAIHOME-DEMO-001"

def out(kind, name):
    p = ROOT / kind / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def build():
    d = Document()
    d.core_properties.title = "EAIhome | Fictief projectmemo"
    d.core_properties.author = "EAIhome testdata"
    d.sections[0].page_width = Inches(8.5)
    d.sections[0].page_height = Inches(11)
    d.styles["Normal"].font.size = Pt(10.5)
    d.add_heading("Project Atlas | overlegnotitie", 0)
    d.add_paragraph("FICTIEVE TESTBRON | EAIHOME-DEMO-001 | 18 november 2026")
    d.add_heading("Afspraak en besluit", 1)
    d.add_paragraph("Op 20 november 2026 vindt een controleoverleg plaats. Het besluit is nog niet goedgekeurd.")
    d.add_heading("Acties", 1)
    table = d.add_table(rows=1, cols=3)
    table.style = "Light Shading Accent 1"
    for cell, value in zip(table.rows[0].cells, ("Code", "Actie", "Status")):
        cell.text = value
    for line in (("ACT-001", "Controleer agenda en stukken", "Open"), ("ACT-002", "Verzamel opmerkingen", "Afgerond")):
        for cell, value in zip(table.add_row().cells, line):
            cell.text = value
    d.add_paragraph("Fictieve gegevens. Geen echte opdracht.")
    d.save(out("docx", "EAIhome_mockup_doc.docx"))

    wb = Workbook()
    ws = wb.active
    ws.title = "Taken"
    for row in [
        ("Code", "Taak", "Status", "Eigenaar", "Datum"),
        ("ACT-001", "Controleer agenda en stukken", "Open", "Testcollega A", "2026-11-20"),
        ("ACT-002", "Verzamel opmerkingen", "Afgerond", "Testcollega B", "2026-11-19"),
        ("ACT-003", "Beoordeel voorstel", "Voorgesteld", "Testcollega A", "2026-11-21"),
    ]:
        ws.append(row)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:E4"
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="1B334A")
        cell.font = Font(color="FFFFFF", bold=True)
    for col, width in (("A", 16), ("B", 40), ("C", 16), ("D", 19), ("E", 16)):
        ws.column_dimensions[col].width = width
    info = wb.create_sheet("Bronnen")
    for row in (("Case-ID", CASE), ("Bron", "Fictieve testdata"), ("Besluit", "Nog niet goedgekeurd")):
        info.append(row)
    info.column_dimensions["A"].width = 21
    info.column_dimensions["B"].width = 33
    wb.save(out("xlsx", "EAIhome_mockup_xlsx.xlsx"))

    pdf = out("pdf", "EAIhome_mockup_pdf.pdf")
    c = canvas.Canvas(str(pdf), pagesize=A4)
    w, h = A4
    c.setTitle("EAIhome fictief projectoverzicht")
    c.setFillColorRGB(.11, .20, .29)
    c.rect(0, h-110, w, 110, fill=1, stroke=0)
    c.setFillColorRGB(1,1,1)
    c.setFont("Helvetica-Bold",20)
    c.drawString(50,h-57,"Project Atlas | Testoverzicht")
    c.setFont("Helvetica",11)
    c.drawString(50,h-80,CASE+" | Fictieve bron")
    c.setFillColorRGB(.11,.20,.29)
    c.setFont("Helvetica-Bold",14)
    c.drawString(50,h-170,"Afspraak")
    c.setFont("Helvetica",11)
    c.drawString(50,h-192,"20 november 2026: controleoverleg Project Atlas.")
    c.drawString(50,h-215,"ACT-001: Controleer agenda en stukken. Status: Open.")
    c.drawString(50,h-238,"Het voorstel is nog niet goedgekeurd.")
    c.save()

    im = Image.new("RGB",(920,400),"#f4f7fb")
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((22,22,898,376),radius=18,fill="#ffffff",outline="#cbd6e2",width=3)
    draw.text((60,67),"EAIhome | Project Atlas (FICTIEF)",fill="#1b334a")
    for i,label in enumerate(("Mail","Agenda","Taak")):
        x = 74+i*270
        draw.rounded_rectangle((x,158,x+207,268),radius=16,fill="#e0edff",outline="#507499",width=3)
        draw.text((x+59,204),label,fill="#1b334a")
    draw.text((60,334),CASE,fill="#5e7288")
    im.save(out("png","EAIhome_mockup_png.png"))
    im.save(out("jpg","EAIhome_mockup_jpg.jpg"),quality=83)
    rate = 12000
    with wave.open(str(out("wav","EAIhome_mockup_wav.wav")),"wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"".join(struct.pack("<h",int(8000*math.sin(2*math.pi*440*i/rate))) for i in range(rate//2)))
    with zipfile.ZipFile(out("zip","EAIhome_mockup_zip.zip"),"w",zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt","EAIHOME-DEMO-001 | fictief testarchief\n")
        archive.writestr("agenda.txt","Controleoverleg 20 november 2026\n")
    subprocess.run(["node",str(Path(__file__).with_name("generate_mockup_pptx.js")),str(out("pptx","EAIhome_mockup_pptx.pptx"))],check=True)

    supported = {".md",".markdown",".txt",".csv",".json",".eml"}
    manifest = []
    for path in sorted(ROOT.rglob("EAIhome_mockup_*")):
        if not path.is_file(): continue
        manifest.append({
            "path":path.relative_to(ROOT).as_posix(),"format":path.suffix[1:],
            "bytes":path.stat().st_size,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "case_id":CASE,"fictional":True,
            "expected_ingest_status_v0_1":"processed" if path.suffix.lower() in supported else "unsupported_format",
        })
    if len(manifest)!=20:
        raise ValueError("Expected 20 files, got "+str(len(manifest)))
    (ROOT/"manifest.json").write_text(
        json.dumps({"schema":"eaihome.fixture-manifest.v1","case_id":CASE,"fixtures":manifest},ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8",
    )
    print("Generated 20 genuine fixtures, manifest hashes verified on next step.")

if __name__=="__main__":
    build()
