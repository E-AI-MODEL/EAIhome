"""Browser-facing tests for the fictional, loopback-only Vandaag app."""

from __future__ import annotations

import html
import re
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from eaihome.today import create_server, render_today
from eaihome.workstore import CorrectionStore

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "fixtures/scenarios/EAIhome_mockup_corrections.json"


class TodayBrowserTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = CorrectionStore(Path(temp.name) / "private", SCENARIO)
        self.server = create_server(self.store, port=0)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = "http://127.0.0.1:" + str(self.server.server_address[1])

    def get(self, url="/", headers=None):
        with urlopen(Request(self.base + url, headers=headers or {}), timeout=6) as response:
            return response.read().decode("utf-8"), response

    def post(self, values, *, headers=None):
        headers = {"Origin": self.base, "Content-Type": "application/x-www-form-urlencoded",
                   **(headers or {})}
        req = Request(self.base + "/correct", data=urlencode(values).encode("utf-8"),
                      headers=headers, method="POST")
        try:
            with urlopen(req, timeout=6) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def forms(self, page):
        matches = re.findall(r'<form class="action" method="post" action="/correct">(.*?)</form>',
                             page, re.S)
        result = []
        for section in matches:
            result.append({
                html.unescape(k): html.unescape(v)
                for k, v in re.findall(r'name="([^"]+)" value="([^"]*)"', section)
            })
        return result

    def form(self, event, subject):
        page, _ = self.get()
        for form in self.forms(page):
            if form.get("subject_id") == subject and form.get("event_kind") == event:
                return {**form, "reason": "Dit is een gecontroleerde fictieve correctie"}
        self.fail("Expected form missing: " + event)

    def test_initial_page_has_all_four_groups_and_provenance(self):
        page, response = self.get()
        self.assertEqual(200, response.status)
        for label in ("Openstaand", "Nog te beoordelen", "Afgerond of afgewezen",
                      "Andere ontwikkelingen", "Bekijk bronnen en voorgeschiedenis"):
            self.assertIn(label, page)
        self.assertIn("task_demo_a", page)
        self.assertIn("task_demo_b", page)
        self.assertIn("fictieve gegevens", page)
        self.assertIn("eaihome", page.lower())

    def test_page_has_mobile_viewport_accessible_controls_and_no_external_assets(self):
        page, response = self.get()
        self.assertIn('name="viewport"', page)
        self.assertIn('@media(max-width:760px)', page)
        self.assertIn('method="post" action="/correct"', page)
        self.assertIn('<details class="provenance">', page)
        self.assertNotIn("<script", page)
        self.assertNotIn('src="http', page)
        self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])

    def test_localhost_only(self):
        self.assertEqual("127.0.0.1", self.server.server_address[0])
        req = Request(self.base, headers={"Host": "example.invalid"})
        with self.assertRaises(HTTPError) as e:
            urlopen(req, timeout=6)
        self.assertEqual(403, e.exception.code)

    def test_historical_view_is_read_only(self):
        page, _ = self.get("/?at=2026-11-18T10%3A30%3A00%2B01%3A00")
        self.assertIn("Historische weergave", page)
        self.assertNotIn('<form class="action"', page)
        self.assertIn("task_demo_a", page)

    def test_correct_and_refresh_actual_page(self):
        form = self.form("task.accepted", "task_demo_a")
        status, page = self.post(form)
        self.assertEqual(200, status)
        self.assertIn("Aangenomen", page)
        self.assertIn("task_demo_a", page)
        reopened, _ = self.get()
        self.assertIn("Aangenomen", reopened)
        self.assertEqual(1, self.store.view("2099-01-01T00:00:00+00:00")["local_correction_count"])

    def test_post_duplicate_id_is_not_duplicated(self):
        form = self.form("task.dismissed", "task_demo_a")
        self.assertEqual(200, self.post(form)[0])
        self.assertEqual(200, self.post(form)[0])
        self.assertEqual(1, self.store.view("2099-01-01T00:00:00+00:00")["local_correction_count"])

    def test_stale_action_gets_conflict_page(self):
        first = self.form("task.accepted", "task_demo_a")
        second = self.form("task.dismissed", "task_demo_a")
        self.assertEqual(200, self.post(first)[0])
        status, page = self.post(second)
        self.assertEqual(409, status)
        self.assertIn("Verouderde revisie", page)

    def test_csrf_token_is_required(self):
        values = self.form("task.accepted", "task_demo_a")
        values["token"] = "fake"
        status, _ = self.post(values)
        self.assertEqual(403, status)
        self.assertEqual(0, self.store.view("2099-01-01T00:00:00+00:00")["local_correction_count"])

    def test_cross_origin_post_is_rejected(self):
        values = self.form("task.accepted", "task_demo_a")
        status, _ = self.post(values, headers={"Origin": "https://example.invalid"})
        self.assertEqual(403, status)

    def test_cannot_submit_arbitrary_extra_fields(self):
        values = self.form("task.accepted", "task_demo_a")
        values["actor_ref"] = "administrator"
        status, _ = self.post(values)
        self.assertEqual(409, status)

    def test_get_does_not_change_database(self):
        for query in ("/", "/?at=2026-11-19T11%3A00%3A00%2B01%3A00"):
            self.get(query)
        self.assertFalse(self.store.path.exists())

    def test_invalid_date_is_rejected(self):
        req = Request(self.base + "/?at=yesterday")
        with self.assertRaises(HTTPError) as e:
            urlopen(req, timeout=6)
        self.assertEqual(400, e.exception.code)

    def test_no_arbitrary_files_are_served(self):
        with self.assertRaises(HTTPError) as e:
            urlopen(self.base + "/../../README.md", timeout=6)
        self.assertEqual(404, e.exception.code)

    def test_markup_in_source_or_title_is_escaped(self):
        view = self.store.view("2099-01-01T00:00:00+00:00")
        item = view["proposed_tasks"][0]
        item["title"] = '<script>alert("x")</script>'
        item["trace"][0]["source"]["quote"] = '"><img src=x onerror=alert(1)>'
        page = render_today(view, "fixture-token", editable=True)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script", page)
        self.assertNotIn("<img", page)
        self.assertIn("&lt;img", page)


if __name__ == "__main__":
    unittest.main()
