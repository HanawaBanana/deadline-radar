"""The validator: what it accepts, what it corrects and what it refuses."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import validate                                                  # noqa: E402

PAGE = """Build With AI: Basics
Hosted by Devpost

Submissions open September 22, 2026 at 10:00 AM PT and close October 26, 2026 at 5:00pm ET.
Every submission must include a public GitHub repository and a 1 to 3 minute demo video.
Submit your project on the Devpost page before the deadline.

Prizes
Grand Prize: $5,000 USD
Second place: $2,000 USD
"""


def run(raw, source=PAGE):
    return validate.analyse(raw, source, mode="offline")


def field(result, name):
    for item in result["fields"]:
        if item["id"] == name:
            return item
    return None


class TestAcceptance(unittest.TestCase):
    def test_value_on_the_page_is_accepted(self):
        result = run({"title": {"value": "Build With AI: Basics",
                                "evidence": "Build With AI: Basics"}})
        got = field(result, "title")
        self.assertEqual(got["verdict"], "accepted")
        self.assertEqual(got["value"], "Build With AI: Basics")
        self.assertEqual(result["source"]["chars"], len(PAGE))

    def test_evidence_offsets_point_at_the_quote(self):
        result = run({"organizer": {"value": "Devpost", "evidence": "Hosted by Devpost"}})
        got = field(result, "organizer")
        start, end = got["span"]
        self.assertEqual(PAGE[start:end], "Hosted by Devpost")

    def test_date_is_rendered_in_iso_with_its_zone(self):
        result = run({"key_dates": [
            {"label": "Submission deadline", "value": "October 26, 2026 at 5:00pm ET",
             "evidence": "close October 26, 2026 at 5:00pm ET"}]})
        got = result["key_dates"][0]
        self.assertEqual(got["value"], "2026-10-26")
        self.assertEqual(got["iso"], "2026-10-26T17:00:00-04:00")
        self.assertEqual(got["label"], "Submission deadline")
        self.assertEqual(got["verdict"], "accepted")

    def test_prize_amount_comes_from_the_page(self):
        result = run({"prizes": [{"place": "Grand Prize", "amount": "$5,000",
                                  "currency": "USD", "evidence": "Grand Prize: $5,000 USD"}]})
        got = field(result, "prizes[0]")
        self.assertEqual(got["verdict"], "accepted")
        self.assertEqual(got["value"], "$5,000 USD")
        self.assertEqual(got["amount"], "5000")

    def test_a_label_the_model_invented_is_mapped_to_the_products_vocabulary(self):
        result = run({"key_dates": [
            {"label": "the day entries shut", "value": "October 26, 2026",
             "evidence": "close October 26, 2026"}]})
        self.assertEqual(result["key_dates"][0]["label"], "Submission deadline")


class TestCorrection(unittest.TestCase):
    def test_the_page_wins_when_the_model_writes_a_different_date(self):
        result = run({"key_dates": [
            {"label": "Submission deadline", "value": "November 2, 2026",
             "evidence": "close October 26, 2026 at 5:00pm ET"}]})
        got = result["key_dates"][0]
        self.assertEqual(got["verdict"], "corrected")
        self.assertEqual(got["value"], "2026-10-26")
        self.assertIn("October 26, 2026", got["reason"])
        self.assertIn("November 2, 2026", got["reason"])

    def test_prose_is_replaced_by_the_pages_own_wording(self):
        result = run({"submission_channel": {
            "value": "upload it somewhere online",
            "evidence": "Submit your project on the Devpost page before the deadline."}})
        got = field(result, "submission_channel")
        self.assertEqual(got["verdict"], "corrected")
        self.assertTrue(got["value"].startswith("Submit your project"))

    def test_a_number_the_model_invented_in_free_text_falls_back_to_the_page(self):
        result = run({"submission_channel": {
            "value": "Submit to https://example.com/abc123",
            "evidence": "Submit your project on the Devpost page before the deadline."}})
        got = field(result, "submission_channel")
        self.assertEqual(got["verdict"], "corrected")
        self.assertNotIn("abc123", got["value"])
        self.assertIn("not in the page", got["reason"])


class TestRejection(unittest.TestCase):
    def test_evidence_that_is_not_on_the_page_is_rejected(self):
        result = run({"prizes": [{"place": "Grand Prize", "amount": "$50,000 USD",
                                  "evidence": "Grand Prize: $50,000 USD"}]})
        self.assertEqual(result["counts"]["rejected"], 1)
        got = result["rejected"][0]
        self.assertEqual(got["id"], "prizes[0]")
        self.assertIn("not in the page", got["reason"])
        self.assertEqual(got["value"], validate.MISSING)

    def test_amount_that_contradicts_the_quote_is_rejected(self):
        result = run({"prizes": [{"place": "Grand Prize", "amount": "$50,000",
                                  "evidence": "Grand Prize: $5,000 USD"}]})
        got = result["rejected"][0]
        self.assertIn("$50,000", got["reason"])
        self.assertIn("$5,000", got["reason"])

    def test_a_date_with_a_number_that_is_not_on_the_page_is_rejected(self):
        result = run({"key_dates": [
            {"label": "Submission deadline", "value": "December 24, 2026",
             "evidence": "close October 26, 2026 at 5:00pm ET"}]})
        self.assertEqual(len(result["rejected"]), 1)
        self.assertIn("24", result["rejected"][0]["reason"])

    def test_a_month_and_day_with_no_year_on_the_page_cannot_be_calendared(self):
        page = "Autumn Jam\nSubmissions close March 15.\n"
        result = run({"key_dates": [{"label": "Submission deadline", "value": "March 15",
                                     "evidence": "close March 15"}]}, source=page)
        got = result["rejected"][0]
        self.assertIn("no year", got["reason"])
        self.assertEqual(result["events"], [])

    def test_a_quote_with_several_dates_and_a_value_that_is_not_one_of_them(self):
        result = run({"key_dates": [
            {"label": "Submission deadline", "value": "September 26, 2026",
             "evidence": "Submissions open September 22, 2026 at 10:00 AM PT and close "
                         "October 26, 2026 at 5:00pm ET."}]}, source=PAGE)
        got = result["rejected"][0]
        self.assertIn("nothing to compare", got["reason"])


class TestGaps(unittest.TestCase):
    def test_an_empty_field_becomes_page_does_not_state(self):
        result = run({"title": {"value": "Build With AI: Basics",
                                "evidence": "Build With AI: Basics"},
                      "prizes": None, "eligibility": None})
        got = field(result, "eligibility")
        self.assertEqual(got["verdict"], "missing")
        self.assertEqual(got["value"], "page does not state")
        self.assertEqual(field(result, "prizes")["value"], "page does not state")
        self.assertGreaterEqual(result["counts"]["missing"], 2)

    def test_an_empty_list_becomes_page_does_not_state(self):
        result = run({"key_dates": []})
        self.assertEqual(field(result, "key_dates")["value"], "page does not state")
        self.assertGreaterEqual(result["counts"]["missing"], 1)


class TestAuditTrail(unittest.TestCase):
    def test_every_accepted_field_carries_a_span_into_the_page(self):
        result = run({"deliverables": [
            {"value": "a public GitHub repository",
             "evidence": "Every submission must include a public GitHub repository"}]})
        got = field(result, "deliverables[0]")
        start, end = got["span"]
        self.assertTrue(0 <= start < end <= len(PAGE))
        self.assertIn("public GitHub repository", PAGE[start:end])

    def test_a_clean_brief_has_no_ungrounded_numbers(self):
        result = run({
            "title": {"value": "Build With AI: Basics", "evidence": "Build With AI: Basics"},
            "prizes": [{"place": "Grand Prize", "amount": "$5,000", "currency": "USD",
                        "evidence": "Grand Prize: $5,000 USD"}],
            "key_dates": [{"label": "Submission deadline", "value": "October 26, 2026",
                           "evidence": "close October 26, 2026"}],
        })
        self.assertEqual(result["ungrounded_numbers"], [])

    def test_counts_always_account_for_every_field(self):
        result = run({"title": {"value": "Build With AI: Basics", "evidence": "nope"},
                      "key_dates": [], "prizes": None})
        counts = result["counts"]
        total = counts["accepted"] + counts["corrected"] + counts["missing"] + counts["rejected"]
        self.assertEqual(total, len(result["fields"]) + len(result["rejected"]))

    def test_events_only_exist_for_accepted_dates(self):
        result = run({
            "title": {"value": "Build With AI: Basics", "evidence": "Build With AI: Basics"},
            "key_dates": [
                {"label": "Submission deadline", "value": "October 26, 2026 at 5:00pm ET",
                 "evidence": "close October 26, 2026 at 5:00pm ET"},
                {"label": "Fake date", "value": "December 24, 2026",
                 "evidence": "close October 26, 2026 at 5:00pm ET"},
            ]})
        self.assertEqual(len(result["events"]), 1)
        event = result["events"][0]
        self.assertEqual(event["start"], "20261026")
        self.assertEqual(event["field"], "submission_deadline")
        self.assertIn("-P7D", event["alarms"])


if __name__ == "__main__":
    unittest.main()
