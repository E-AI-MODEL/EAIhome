"""Fictieve werkcasus: regels en negatieve voorbeelden, zonder LLM/provider."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from eaihome.continuity import load_scenario, work_status

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "fixtures/scenarios/EAIhome_mockup_work_scenario.json"


class WorkContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = load_scenario(SCENARIO, ROOT)

    def snapshot(self, known: str, effective: str | None = None):
        return work_status(self.scenario, known, effective)

    def item(self, snap: dict, id_: str):
        for x in snap["open_tasks"] + snap["proposed_tasks"] + snap["other_objects"]:
            if x["id"] == id_:
                return x
        self.fail(f"Niet gevonden: {id_}")

    def amended(self, action):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT / "fixtures", root / "fixtures")
            path = root / "fixtures/scenarios/EAIhome_mockup_work_scenario.json"
            source = json.loads(path.read_text(encoding="utf8"))
            action(source, root)
            path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf8")
            return load_scenario(path, root)

    def test_question_is_not_an_accepted_task(self):
        snap = self.snapshot("2026-11-18T10:30:00+01:00")
        self.assertEqual([], snap["open_tasks"])
        self.assertEqual("proposed", self.item(snap, "task_atlas_001")["status"])

    def test_reported_promise_does_not_accept_task(self):
        snap = self.snapshot("2026-11-18T11:10:00+01:00")
        self.assertEqual("reported", self.item(snap, "commitment_atlas_001")["status"])
        self.assertEqual("proposed", self.item(snap, "task_atlas_001")["status"])

    def test_later_notice_does_not_implicitly_change_status(self):
        snap = self.snapshot("2026-11-19T08:30:00+01:00")
        item = self.item(snap, "task_atlas_001")
        self.assertEqual("proposed", item["status"])
        self.assertEqual("task.noted", item["trace"][-1]["kind"])

    def test_manually_accepted_task_is_open(self):
        snap = self.snapshot("2026-11-19T11:00:00+01:00")
        self.assertEqual(["task_atlas_001"], [x["id"] for x in snap["open_tasks"]])
        self.assertEqual("accepted", self.item(snap, "task_atlas_001")["status"])

    def test_discussed_means_not_decided(self):
        snap = self.snapshot("2026-11-19T16:00:00+01:00")
        self.assertEqual("discussed", self.item(snap, "decision_atlas_001")["status"])

    def test_cancelled_meeting_does_not_cancel_task_or_promise(self):
        snap = self.snapshot("2026-11-20T09:30:00+01:00")
        self.assertEqual("cancelled", self.item(snap, "meeting_atlas_001")["status"])
        self.assertEqual("accepted", self.item(snap, "task_atlas_001")["status"])
        self.assertEqual("reported", self.item(snap, "commitment_atlas_001")["status"])

    def test_late_registration_changes_what_was_known_not_when_it_applied(self):
        past = self.snapshot("2026-11-20T11:00:00+01:00")
        later = self.snapshot("2026-11-20T13:00:00+01:00", "2026-11-20T11:00:00+01:00")
        before_effect = self.snapshot("2026-11-20T13:00:00+01:00", "2026-11-20T09:00:00+01:00")
        self.assertEqual("accepted", self.item(past, "task_atlas_001")["status"])
        self.assertEqual("completed", self.item(later, "task_atlas_001")["status"])
        self.assertEqual("accepted", self.item(before_effect, "task_atlas_001")["status"])

    def test_correction_survives_replay(self):
        snap = self.snapshot("2026-11-20T15:00:00+01:00")
        again = self.snapshot("2026-11-21T10:00:00+01:00")
        self.assertEqual("dismissed", self.item(snap, "task_atlas_002")["status"])
        self.assertEqual("dismissed", self.item(again, "task_atlas_002")["status"])
        self.assertEqual([], snap["open_tasks"])
        self.assertEqual([], snap["proposed_tasks"])

    def test_a_model_cannot_accept_or_complete(self):
        def change(data, _):
            next(x for x in data["events"] if x["id"] == "ev_007")["actor_kind"] = "model"
        with self.assertRaisesRegex(ValueError, "actor"):
            self.amended(change)

    def test_decided_is_not_possible_without_authorisation(self):
        def change(data, _):
            next(x for x in data["events"] if x["id"] == "ev_008")["event_kind"] = "decision.decided"
        with self.assertRaisesRegex(ValueError, "Onbekende gebeurtenis"):
            self.amended(change)

    def test_false_source_quote_is_rejected(self):
        def change(data, _):
            data["events"][0]["source_quote"] = "Dit staat niet in de bron."
        with self.assertRaisesRegex(ValueError, "bron"): self.amended(change)

    def test_modified_source_blob_is_rejected(self):
        def change(data, root):
            file_path = root / data["events"][0]["source_ref"]
            file_path.write_bytes(file_path.read_bytes() + b"CHANGED")
        with self.assertRaisesRegex(ValueError, "Bronhash"):
            self.amended(change)

    def test_source_path_traversal_is_rejected(self):
        def change(data, _):
            data["events"][0]["source_ref"] = "fixtures/../outside.md"
        with self.assertRaisesRegex(ValueError, "Bronpad"):
            self.amended(change)

    def test_context_mixing_is_rejected(self):
        def change(data, _):
            data["events"][0]["context_id"] = "ctx_another"
        with self.assertRaisesRegex(ValueError, "context"):
            self.amended(change)

    def test_exact_duplicate_event_is_idempotent(self):
        amended = self.amended(lambda d, _: d["events"].append(copy.deepcopy(d["events"][0])))
        result = work_status(amended, "2026-11-18T10:30:00+01:00")
        self.assertEqual(1, len(self.item(result, "task_atlas_001")["trace"]))

    def test_conflicting_duplicate_event_id_is_rejected(self):
        def change(data, _):
            copy_event = copy.deepcopy(data["events"][0])
            copy_event["actor_ref"] = "other"
            data["events"].append(copy_event)
        with self.assertRaisesRegex(ValueError, "strijdige"):
            self.amended(change)

    def test_naive_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "tijdzone"):
            self.snapshot("2026-11-19T12:00:00")

    def test_invalid_transition_is_rejected(self):
        def change(data, _):
            event = next(x for x in data["events"] if x["id"] == "ev_010")
            event["effective_at"] = "2026-11-18T10:01:00+01:00"
            event["recorded_at"] = "2026-11-18T10:02:00+01:00"
        amended = self.amended(change)
        with self.assertRaisesRegex(ValueError, "Ongeldige statusovergang"):
            work_status(amended, "2026-11-21T12:00:00+01:00")

    def test_source_path_and_timestamp_are_visible(self):
        snap = self.snapshot("2026-11-19T11:00:00+01:00")
        trace = self.item(snap, "task_atlas_001")["trace"]
        self.assertEqual(3, len(trace))
        self.assertTrue(all(x["source"]["sha256"] and x["source"]["path"] for x in trace))
        self.assertEqual("2026-11-19T10:05:00+01:00", trace[-1]["recorded_at"])


if __name__ == "__main__":
    unittest.main()
