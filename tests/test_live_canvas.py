"""Contract tests for local-only canvas and constrained Ollama planning."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request
from urllib.error import HTTPError

from eaihome.live_canvas import (
    API, DEFAULT_MODEL, canvas_data, create_canvas_server, model_available,
    plan_with_model, validate_plan,
)


class CanvasContractTests(unittest.TestCase):
    def test_only_known_panels_survive(self):
        data = {"panels": ["timeline", "<script>evil</script>", "timeline", "sources", "document", "tasks", "prep"], "html": "<script>"}
        self.assertEqual({"panels": ["timeline", "sources", "document", "tasks"]}, validate_plan(data))

    def test_empty_or_unknown_panels_fail_closed(self):
        for value in (None, {}, {"panels": []}, {"panels": ["execute"]}, {"panels": "timeline"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_plan(value)

    def test_model_plans_from_prompt_not_from_sources(self):
        fake = {"response": json.dumps({"panels": ["prep", "tasks", "sources"]}), "done": True}
        with patch("eaihome.live_canvas._call_ollama", return_value=fake) as call:
            plan = plan_with_model("Bereid mijn overleg voor", "dummy:4b")
            self.assertEqual(["prep", "tasks", "sources"], plan["panels"])
            route, payload = call.call_args.args
            self.assertEqual("/api/generate", route)
            self.assertIn("Bereid mijn overleg voor", payload["prompt"])
            self.assertNotIn("Atlas", json.dumps(payload))
            self.assertNotIn("/tmp", json.dumps(payload))

    def test_model_name_is_never_a_url(self):
        with self.assertRaises(ValueError):
            model_available("http://remote.invalid/x")
        with self.assertRaises(ValueError):
            plan_with_model("test", "../etc/passwd")

    def test_long_prompt_rejected_before_model(self):
        with self.assertRaises(ValueError):
            plan_with_model("x" * 601, DEFAULT_MODEL)

    def test_model_malformed_json_not_passed_to_ui(self):
        with patch("eaihome.live_canvas._call_ollama", return_value={"response": "Here is HTML <script>"}):
            with self.assertRaises(ValueError):
                plan_with_model("tijdlijn", DEFAULT_MODEL)

    def test_snapshot_preserves_status_and_origin(self):
        view = {"case_id": "CASE", "open_tasks": [], "proposed_tasks": [{
            "id": "task-1", "title": "Een vraag", "kind": "task", "status": "proposed",
            "trace": [{"event_kind": "task.proposed", "recorded_at": "2026-11-18T10:00:00+01:00",
                       "source": {"path": "fixtures/demo.eml", "quote": "Kun jij?"}}],
        }], "other_objects": []}
        data = canvas_data(view)
        self.assertEqual("proposed", data["items"][0]["status"])
        self.assertEqual("Kun jij?", data["items"][0]["quote"])
        self.assertEqual("CASE", data["case_id"])


class CanvasHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = create_canvas_server(Path(cls.temp.name) / "demo", port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:" + str(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.temp.cleanup()

    def get(self, path: str, headers: dict | None = None):
        req = request.Request(self.url + path, headers=headers or {})
        try:
            with request.urlopen(req, timeout=5) as r:
                return r.status, r.read().decode("utf-8"), r.headers
        except HTTPError as e:
            return e.code, e.read().decode("utf-8"), e.headers

    def post(self, path: str, value: dict, headers: dict | None = None):
        data = json.dumps(value).encode("utf-8")
        req = request.Request(self.url + path, data=data, headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
        try:
            with request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except HTTPError as e:
            return e.code, json.loads(e.read())

    def test_page_is_downloadable_single_html_with_blank_canvas(self):
        status, body, headers = self.get("/")
        self.assertEqual(200, status)
        self.assertIn("Waar wil je", body)
        self.assertIn('id="canvas"', body)
        self.assertIn('id="ask"', body)
        self.assertNotIn("<script src=", body)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])

    def test_public_paths_do_not_leak_other_files(self):
        status, _, _ = self.get("/src/eaihome/workstore.py")
        self.assertEqual(404, status)

    def test_untrusted_host_is_rejected(self):
        status, _, _ = self.get("/api/status", headers={"Host": "example.invalid"})
        self.assertEqual(403, status)

    def test_status_explicit_when_ollama_not_available(self):
        with patch("eaihome.live_canvas.model_available", return_value=False):
            status, body, _ = self.get("/api/status")
        self.assertEqual(200, status)
        data = json.loads(body)
        self.assertEqual(API, data["api"])
        self.assertFalse(data["model_ready"])

    def test_only_fictional_scenario_is_returned(self):
        status, body, _ = self.get("/api/data")
        self.assertEqual(200, status)
        payload = json.loads(body)
        self.assertIn("fictieve gegevens", payload["context"])
        self.assertTrue(any(item["status"] == "proposed" for item in payload["items"]))
        self.assertTrue(all("source" in i and "quote" in i for i in payload["items"]))

    def test_llm_route_rejects_missing_model(self):
        with patch("eaihome.live_canvas.model_available", return_value=False):
            status, data = self.post("/api/compose", {"prompt": "Wat speelt er?"})
        self.assertEqual(503, status)
        self.assertIn("niet beschikbaar", data["error"])

    def test_llm_route_accepts_only_validated_panel_names(self):
        with patch("eaihome.live_canvas.model_available", return_value=True), patch(
            "eaihome.live_canvas.plan_with_model", return_value={"panels": ["tasks", "sources"]}
        ):
            status, data = self.post("/api/compose", {"prompt": "Wat staat open?"}, headers={"Origin": self.url})
        self.assertEqual(200, status)
        self.assertEqual(["tasks", "sources"], data["panels"])
        self.assertNotIn("html", data)

    def test_cross_origin_post_is_rejected(self):
        status, _ = self.post("/api/compose", {"prompt": "test"}, headers={"Origin": "https://outside.invalid"})
        self.assertEqual(403, status)

    def test_invalid_payload_is_rejected(self):
        status, _ = self.post("/api/compose", {"prompt": "test", "operation": "delete"})
        self.assertEqual(400, status)

    def test_no_get_mutation_route(self):
        status, _, _ = self.get("/api/compose")
        self.assertEqual(404, status)


if __name__ == "__main__":
    unittest.main()