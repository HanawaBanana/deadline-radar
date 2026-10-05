"""The standalone HTML brief: self-contained, escaped, honest about gaps."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import export                                                     # noqa: E402
from radar import offline                                                    # noqa: E402
from radar import validate                                                   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THIN = open(os.path.join(ROOT, "samples", "thin_announcement.txt"), encoding="utf-8").read()


def record_for(text, analysis_id="thin-brief"):
    """The same shape store.get(id) returns, built without touching sqlite3."""
    result = validate.analyse(offline.extract(text), text, mode="offline")
    return {
        "id": analysis_id, "created_at": result.get("created_at"),
        "title": (result.get("brief") or {}).get("title"), "mode": "offline",
        "source": text, "result": result,
    }


class TestBriefHtml(unittest.TestCase):
    def test_it_is_one_complete_document(self):
        html = export.brief_html(record_for(THIN))
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn('<meta charset="utf-8">', html)
        self.assertIn("<style>", html)
        self.assertIn("</html>", html)

    def test_nothing_is_loaded_from_outside_the_file(self):
        html = export.brief_html(record_for(THIN))
        self.assertNotIn('<link rel="stylesheet"', html)
        self.assertNotIn('src="http', html)
        self.assertNotIn("<script", html)

    def test_a_field_the_page_never_states_says_so(self):
        html = export.brief_html(record_for(THIN))
        self.assertIn("page does not state", html)

    def test_the_evidence_and_its_character_offsets_are_in_the_file(self):
        html = export.brief_html(record_for(THIN))
        self.assertIn("Submissions close November 14, 2026 at 11:59pm PT.", html)
        self.assertIn("chars 93-143", html)
        self.assertIn("accepted", html)
        self.assertIn("missing", html)

    def test_the_proposal_the_validation_and_the_calendar_are_in_the_file(self):
        record = record_for(THIN)
        html = export.brief_html(record)
        self.assertIn("Raw proposal", html)
        self.assertIn("Validated brief", html)
        self.assertIn("BEGIN:VCALENDAR", html)
        self.assertIn("BEGIN:VEVENT", html)
        self.assertIn(record["result"]["source"]["sha256"], html)
        self.assertIn("Generated ", html)

    def test_a_page_containing_script_tags_is_escaped(self):
        record = record_for("<script>alert('x')</script>\nOrganised by the Studio Collective\n")
        html = export.brief_html(record)
        self.assertNotIn("<script", html)
        self.assertIn("&lt;script&gt;", html)

    def test_a_hostile_field_value_cannot_break_out_of_the_table(self):
        record = record_for(THIN)
        record["result"]["fields"][0]["value"] = '<script>alert("1")</script>'
        record["result"]["fields"][0]["reason"] = '"><img src=x>'
        html = export.brief_html(record)
        self.assertNotIn("<script", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;alert(&quot;1&quot;)&lt;/script&gt;", html)

    def test_an_analysis_with_a_rejection_still_exports_a_whole_document(self):
        html = export.brief_html(record_for("Prizes\nGrand Prize: $50,000 USD\n"))
        self.assertIn("rejected", html.lower())
        self.assertIn("</html>", html)


if __name__ == "__main__":
    unittest.main()
