"""History storage and the HTTP surface, both exercised offline."""

import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import demo                                                     # noqa: E402
from radar import offline                                                  # noqa: E402
from radar import validate                                                 # noqa: E402
from radar import web                                                      # noqa: E402
from radar.pipeline import Pipeline                                        # noqa: E402
from radar.store import Store                                              # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THIN = open(os.path.join(ROOT, "samples", "thin_announcement.txt"), encoding="utf-8").read()


def analyse(text):
    return validate.analyse(offline.extract(text), text, mode="offline")


class TestStore(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()

    def test_save_then_read_back_the_whole_analysis(self):
        analysis_id = self.store.save(THIN, analyse(THIN))
        found = self.store.get(analysis_id)
        self.assertEqual(found["source"], THIN)
        self.assertEqual(found["result"]["counts"]["missing"], 3)
        self.assertEqual(found["title"], "Autumn Mini Jam")

    def test_history_is_newest_first_and_carries_counts(self):
        self.store.save(THIN, analyse(THIN))
        second = self.store.save("Prizes\nGrand Prize: $1,000 USD\n", analyse(
            "Prizes\nGrand Prize: $1,000 USD\n"))
        rows = self.store.history()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["id"], second)
        self.assertIn("accepted", rows[0]["counts"])

    def test_an_analysis_can_be_replaced_by_id(self):
        self.store.save(THIN, analyse(THIN), analysis_id="fixed")
        self.store.save(THIN, analyse(THIN), analysis_id="fixed")
        self.assertEqual(self.store.count(), 1)


class TestHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store(":memory:")
        cls.httpd = web.make_server(host="127.0.0.1", port=0, offline_default=True,
                                    pipeline=Pipeline(cls.store, offline_default=True),
                                    quiet=True)
        cls.port = cls.httpd.server_address[1]
        cls.base = "http://127.0.0.1:%d" % cls.port
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.store.close()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8"), dict(resp.headers)

    def post(self, path, payload):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_index_renders_the_product(self):
        status, html, _ = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("Deadline Radar", html)
        self.assertIn("Analyse", html)
        self.assertIn("static/style.css", html)

    def test_static_assets_are_served(self):
        status, css, headers = self.get("/static/style.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", headers["Content-Type"])
        self.assertIn(".card", css)

    def test_health_endpoint(self):
        status, body, _ = self.get("/healthz")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_analyse_endpoint_returns_a_rendered_brief(self):
        status, data = self.post("/api/analyse", {"text": THIN, "mode": "offline"})
        self.assertEqual(status, 200)
        self.assertEqual(data["counts"]["missing"], 3)
        self.assertIn("page does not state", data["html"])
        self.assertIn("Audit trail", data["html"])
        self.assertIn("Download .ics", data["html"])
        self.assertGreater(data["elapsed_ms"], -1)

    def test_saved_analysis_can_be_reopened(self):
        status, data = self.post("/api/analyse", {"text": THIN, "mode": "offline"})
        analysis_id = data["id"]
        status, html, _ = self.get("/analysis/" + analysis_id)
        self.assertEqual(status, 200)
        self.assertIn("Autumn Mini Jam", html)
        status, body, _ = self.get("/api/analysis/" + analysis_id)
        self.assertEqual(json.loads(body)["id"], analysis_id)

    def test_ics_download_has_the_right_type_and_filename(self):
        status, data = self.post("/api/analyse", {"text": THIN, "mode": "offline"})
        req = urllib.request.Request(self.base + "/api/analysis/%s.ics" % data["id"])
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            self.assertEqual(resp.status, 200)
            self.assertIn("text/calendar", resp.headers["Content-Type"])
            self.assertIn("autumn-mini-jam-deadlines.ics", resp.headers["Content-Disposition"])
        self.assertTrue(body.startswith("BEGIN:VCALENDAR"))
        self.assertIn("DTSTART", body)

    def test_history_endpoint_returns_rows_and_html(self):
        self.post("/api/analyse", {"text": THIN, "mode": "offline"})
        status, body, _ = self.get("/api/history")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(payload["rows"]), 1)
        self.assertIn("hist-list", payload["html"])

    def test_the_language_model_reader_is_refused_when_running_offline(self):
        status, data = self.post("/api/analyse", {"text": THIN, "mode": "llm"})
        self.assertEqual(status, 400)
        self.assertIn("offline", data["error"])

    def test_empty_text_is_a_bad_request(self):
        status, data = self.post("/api/analyse", {"text": "   ", "mode": "offline"})
        self.assertEqual(status, 400)

    def test_unknown_paths_are_404(self):
        try:
            status, _, _ = self.get("/nope")
        except urllib.error.HTTPError as exc:
            status = exc.code
        self.assertEqual(status, 404)

    def test_every_demo_step_is_reachable_by_url(self):
        status, body, _ = self.get("/api/demo")
        self.assertEqual(status, 200)
        steps = json.loads(body)["steps"]
        self.assertEqual(len(steps), len(demo.STEPS))
        self.assertGreaterEqual(len(steps), 10)
        for step in steps:
            self.assertTrue(step["url"].startswith("/"), step)
            status, html, _ = self.get(step["url"].split("#")[0])
            self.assertEqual(status, 200, step["url"])
            self.assertIn("Deadline Radar", html)

    def test_the_tour_pages_carry_the_step_and_a_focus(self):
        status, html, _ = self.get("/?demo=3")
        self.assertIn("guided tour 3/%d" % len(demo.STEPS), html)
        self.assertIn('data-focus="dates"', html)
        self.assertIn("2026-10-26T17:00:00-04:00", html)

    def test_the_hallucination_step_shows_a_rejection_and_a_correction(self):
        status, html, _ = self.get("/?demo=6")
        self.assertIn("$50,000", html)
        self.assertIn("rejected", html)
        self.assertIn("the page wins", html)

    def test_the_ics_page_shows_the_file_that_the_button_serves(self):
        self.get("/?demo=2")
        status, html, _ = self.get("/ics/demo-a")
        self.assertEqual(status, 200)
        self.assertIn("BEGIN:VCALENDAR", html)


if __name__ == "__main__":
    unittest.main()
