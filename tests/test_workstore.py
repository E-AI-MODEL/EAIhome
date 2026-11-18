"""Vaste negatieve en positieve regressies voor lokale fictieve correcties."""

from __future__ import annotations

import json
import shutil
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from eaihome.search import rebuild
from eaihome.workstore import CorrectionStore

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "fixtures/scenarios/EAIhome_mockup_corrections.json"
T0 = "2026-11-18T16:00:00+01:00"
T1 = "2026-11-18T17:00:00+01:00"
LATER = "2026-11-18T18:00:00+01:00"


class LocalCorrectionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "private"
        self.store = CorrectionStore(self.home, SCENARIO)

    def write(self, *, request_id="test-change-0001", subject_id="task_demo_a",
              event_kind="task.dismissed", reason="Dit was alleen een vraag",
              expected_revision=1, recorded_at=T0, effective_at=None, actor_ref="demo-operator"):
        return self.store.append(
            request_id=request_id, subject_id=subject_id,
            event_kind=event_kind, reason=reason, actor_ref=actor_ref,
            expected_revision=expected_revision, recorded_at=recorded_at,
            effective_at=effective_at,
        )

    def entry(self, view, subject_id):
        for item in view["open_tasks"] + view["proposed_tasks"] + view["other_objects"]:
            if item["id"] == subject_id:
                return item
        raise AssertionError(f"Onbekend object: {subject_id}")

    def test_source_scenario_starts_with_only_proposals(self):
        snap = self.store.view("2026-11-18T15:00:00+01:00")
        self.assertEqual(0, snap["local_correction_count"])
        self.assertEqual({"task_demo_a", "task_demo_b"}, {t["id"] for t in snap["proposed_tasks"]})
        self.assertFalse(self.store.path.exists())

    def test_dismissal_is_saved_and_survives_restart(self):
        record = self.write()
        self.assertFalse(record["replayed"])
        reopened = CorrectionStore(self.home, SCENARIO)
        snap = reopened.view(T1)
        self.assertEqual("dismissed", self.entry(snap, "task_demo_a")["status"])
        self.assertEqual("proposed", self.entry(snap, "task_demo_b")["status"])
        self.assertEqual(1, snap["local_correction_count"])
        source = self.entry(snap, "task_demo_a")["trace"][-1]["source"]
        self.assertEqual("unverified_local_operator_note", source["kind"])
        self.assertIn("vraag", source["reason"])

    def test_index_rebuild_cannot_erase_correction(self):
        self.write()
        rebuild(self.home)
        (self.home / "index.sqlite3").unlink()
        rebuild(self.home)
        self.assertEqual(
            "dismissed",
            self.entry(CorrectionStore(self.home, SCENARIO).view(LATER), "task_demo_a")["status"],
        )
        self.assertTrue((self.home / "work-events.sqlite3").is_file())

    def test_two_time_axes_keep_late_entry_out_of_earlier_history(self):
        self.write(recorded_at=T1, effective_at=T0)
        earlier_known = self.store.view(T0, LATER)
        earlier_valid = self.store.view(LATER, "2026-11-18T15:00:00+01:00")
        later_known = self.store.view(LATER, T1)
        self.assertEqual("proposed", self.entry(earlier_known, "task_demo_a")["status"])
        self.assertEqual("proposed", self.entry(earlier_valid, "task_demo_a")["status"])
        self.assertEqual("dismissed", self.entry(later_known, "task_demo_a")["status"])

    def test_accept_then_complete_but_earlier_snapshot_remains_open(self):
        self.write(request_id="test-accept-0001", event_kind="task.accepted")
        self.write(request_id="test-finish-0002", event_kind="task.completed",
                   expected_revision=2, recorded_at=T1)
        before = self.store.view("2026-11-18T16:30:00+01:00")
        after = self.store.view(LATER)
        self.assertEqual(["task_demo_a"], [t["id"] for t in before["open_tasks"]])
        self.assertEqual("completed", self.entry(after, "task_demo_a")["status"])
        self.assertEqual(3, len(self.entry(after, "task_demo_a")["trace"]))

    def test_same_idempotency_key_and_same_request_returns_original(self):
        first = self.write()
        again = self.write(recorded_at=T1)
        self.assertEqual(first["event_id"], again["event_id"])
        self.assertTrue(again["replayed"])
        self.assertEqual(1, self.store.view(LATER)["local_correction_count"])

    def test_changed_payload_cannot_reuse_idempotency_key(self):
        self.write()
        with self.assertRaisesRegex(ValueError, "Idempotency"):
            self.write(reason="Ander besluit over dezelfde aanvraag")
        self.assertEqual(1, self.store.view(LATER)["local_correction_count"])

    def test_stale_revision_from_another_writer_is_rejected(self):
        stale_client = CorrectionStore(self.home, SCENARIO)
        self.write(event_kind="task.accepted")
        with self.assertRaisesRegex(ValueError, "Verouderde revisie"):
            stale_client.append(request_id="test-second-0002", subject_id="task_demo_a",
                                event_kind="task.dismissed", reason="Tweede bewerking",
                                actor_ref="other-demo", expected_revision=1, recorded_at=T1)
        self.assertEqual("accepted", self.entry(self.store.view(LATER), "task_demo_a")["status"])

    def test_inconsistent_transition_does_not_commit(self):
        with self.assertRaisesRegex(ValueError, "Ongeldige statusovergang"):
            self.write(event_kind="task.completed")
        self.assertEqual(0, self.store.view(LATER)["local_correction_count"])
        result = self.write(request_id="test-valid-0002", event_kind="task.accepted")
        self.assertEqual(2, result["revision"])

    def test_second_application_is_not_allowed(self):
        self.write()
        with self.assertRaisesRegex(ValueError, "Ongeldige statusovergang"):
            self.write(request_id="test-again-0002", subject_id="task_demo_a",
                       event_kind="task.accepted", expected_revision=2, recorded_at=T1)

    def test_decision_is_not_promoted_to_formal_decision(self):
        with self.assertRaisesRegex(ValueError, "beperkte correcties"):
            self.write(subject_id="decision_demo_a", event_kind="decision.decided")

    def test_wrong_object_kind_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "past niet bij werkobject"):
            self.write(subject_id="decision_demo_a", event_kind="task.dismissed")

    def test_blank_reason_and_bad_key_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "reason"):
            self.write(reason=" ")
        with self.assertRaisesRegex(ValueError, "request_id"):
            self.write(request_id="../escape")

    def test_naive_effective_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "tijdzone"):
            self.write(effective_at="2026-11-18T11:00:00")

    def test_recorded_event_bytes_are_checked(self):
        self.write()
        with sqlite3.connect(self.store.path) as db:
            db.execute("UPDATE events SET payload_json=replace(payload_json, 'vraag', 'taak')")
        with self.assertRaisesRegex(ValueError, "Registerintegriteit"):
            self.store.view(LATER)

    def test_original_scenario_change_requires_explicit_migration(self):
        self.write()
        with tempfile.TemporaryDirectory() as directory:
            new_root = Path(directory)
            shutil.copytree(ROOT / "fixtures", new_root / "fixtures")
            changed = new_root / "fixtures/scenarios/EAIhome_mockup_corrections.json"
            scenario = json.loads(changed.read_text(encoding="utf-8"))
            scenario["subjects"][0]["title"] += " (herzien)"
            changed.write_text(json.dumps(scenario, ensure_ascii=False), encoding="utf-8")
            different = CorrectionStore(self.home, changed)
            with self.assertRaisesRegex(ValueError, "Scenario of context"):
                different.view(LATER)

    def test_cross_context_reuse_is_rejected(self):
        self.write()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "fixtures", root / "fixtures")
            path = root / "fixtures/scenarios/EAIhome_mockup_corrections.json"
            scenario = json.loads(path.read_text(encoding="utf-8"))
            scenario["context_id"] = "ctx_different"
            for item in scenario["subjects"]:
                item["context_id"] = "ctx_different"
            for event in scenario["events"]:
                event["context_id"] = "ctx_different"
            path.write_text(json.dumps(scenario), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Scenario of context"):
                CorrectionStore(self.home, path).view(LATER)

    def test_source_tampering_is_detected_on_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "fixtures", root / "fixtures")
            scenario = root / "fixtures/scenarios/EAIhome_mockup_corrections.json"
            original = CorrectionStore(self.home, scenario)
            original.append(request_id="test-anchor-0001", subject_id="task_demo_a",
                            event_kind="task.dismissed", reason="Geen opdracht",
                            actor_ref="operator-demo", expected_revision=1, recorded_at=T0)
            source = root / "fixtures/mockups/eml/EAIhome_mockup_eml.eml"
            source.write_bytes(source.read_bytes() + b"\nGewijzigd")
            with self.assertRaisesRegex(ValueError, "Bronhash"):
                CorrectionStore(self.home, scenario).view(LATER)

    def test_view_rebuild_is_deterministic(self):
        self.write()
        first = self.store.view(LATER)
        second = CorrectionStore(self.home, SCENARIO).view(LATER)
        self.assertEqual(first, second)

    def test_commitment_can_be_cancelled_without_closing_task(self):
        self.write(subject_id="commitment_demo_a", event_kind="commitment.cancelled",
                   reason="De toezegging is ingetrokken")
        result = self.store.view(LATER)
        self.assertEqual("cancelled", self.entry(result, "commitment_demo_a")["status"])
        self.assertEqual("proposed", self.entry(result, "task_demo_a")["status"])

    def test_version_counter_includes_non_local_source_events(self):
        result = self.write()
        self.assertEqual(2, result["revision"])

    @unittest.skipUnless(hasattr(Path, "chmod"), "Requires local file permissions")
    def test_database_file_is_private_on_posix(self):
        self.write()
        self.assertEqual(stat.S_IMODE(self.store.path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
