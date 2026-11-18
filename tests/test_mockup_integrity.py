"""Check actual mockup files, file signatures, SHA-256 and import behavior."""
import hashlib
import json
import tempfile
import unittest
import wave
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path

from eaihome.search import rebuild, search
from eaihome.store import add_file

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "mockups"

@unittest.skipUnless((ROOT / "manifest.json").is_file(), "Generate binary fixtures before checking mockup integrity")
class MockupIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        cls.entries = cls.manifest["fixtures"]

    def test_manifest_names_and_hashes(self):
        self.assertEqual("EAIHOME-DEMO-001", self.manifest["case_id"])
        self.assertEqual(20, len(self.entries))
        self.assertEqual(18, len({e["format"] for e in self.entries}))
        for entry in self.entries:
            self.assertTrue(entry["fictional"])
            path = ROOT / entry["path"]
            self.assertTrue(path.name.startswith("EAIhome_mockup_"))
            self.assertEqual(entry["bytes"], path.stat().st_size)
            self.assertEqual(entry["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_actual_binary_signatures(self):
        files = {p.suffix: p for p in ROOT.rglob("EAIhome_mockup_*") if p.is_file()}
        for extension, member in (
            (".docx", "word/document.xml"),
            (".xlsx", "xl/workbook.xml"),
            (".pptx", "ppt/presentation.xml"),
            (".zip", "agenda.txt"),
        ):
            with zipfile.ZipFile(files[extension]) as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn(member, archive.namelist())
        self.assertTrue(files[".pdf"].read_bytes().startswith(b"%PDF-"))
        self.assertTrue(files[".png"].read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertTrue(files[".jpg"].read_bytes().startswith(b"\xff\xd8\xff"))
        with wave.open(str(files[".wav"]), "rb") as audio:
            self.assertEqual((audio.getnchannels(), audio.getframerate()), (1, 12000))
        mails = sorted((ROOT / "eml").glob("*.eml"))
        self.assertEqual(2, len(mails))
        self.assertTrue(all(BytesParser(policy=policy.default).parsebytes(p.read_bytes())["Message-ID"] for p in mails))

    def test_import_contract_and_search(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            for entry in self.entries:
                path = ROOT / entry["path"]
                record = add_file(home, path, family="mockup-case", version="v1", groups=("owner",))
                self.assertEqual(entry["expected_ingest_status_v0_1"], record["ingest_status"], path.name)
            index = rebuild(home)
            self.assertEqual(20, index["records"])
            self.assertGreater(index["indexed_passages"], 0)
            self.assertEqual(7, sum(entry["expected_ingest_status_v0_1"] == "processed" for entry in self.entries))
            self.assertTrue(search(home, "ACT-001", groups=("owner",))["matches"])
            self.assertEqual([], search(home, "ACT-001", groups=("someone-else",))["matches"])

if __name__ == "__main__":
    unittest.main()
