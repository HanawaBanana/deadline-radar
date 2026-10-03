"""The offline reader, and the promise that nothing in a brief is invented."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import offline                                                   # noqa: E402
from radar import validate                                                  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sample(name):
    with open(os.path.join(ROOT, "samples", name), "r", encoding="utf-8") as fh:
        return fh.read()


def analyse(name):
    source = sample(name)
    return source, validate.analyse(offline.extract(source), source, mode="offline")


class TestSamples(unittest.TestCase):
    def test_devpost_sample_is_read_completely(self):
        source, result = analyse("devpost_build_with_ai.txt")
        self.assertEqual(result["counts"]["rejected"], 0)
        self.assertEqual(result["brief"]["title"], "Build With AI: Basics")
        self.assertEqual(result["brief"]["organizer"], "Devpost")
        dates = {f["name"]: f["value"] for f in result["key_dates"]}
        self.assertEqual(dates["submission_open"], "2026-09-22")
        self.assertEqual(dates["submission_deadline"], "2026-10-26")
        amounts = [f["value"] for f in result["fields"] if f["name"] == "prizes"]
        self.assertIn("$5,000 USD", amounts)
        self.assertEqual(len(result["events"]), 5)

    def test_chinese_sample_infers_the_missing_year(self):
        source, result = analyse("chinese_rules.txt")
        self.assertEqual(result["counts"]["rejected"], 0)
        deadline = [f for f in result["key_dates"]
                    if f["name"] == "submission_deadline"][0]
        self.assertEqual(deadline["value"], "2026-10-26")
        self.assertEqual(deadline["iso"], "2026-10-26T17:00:00-04:00")
        self.assertTrue(deadline["year_inferred"])
        self.assertIn("inferred", deadline["reason"])

    def test_thin_sample_reports_the_gaps_instead_of_filling_them(self):
        source, result = analyse("thin_announcement.txt")
        self.assertEqual(result["counts"]["accepted"] + result["counts"]["corrected"], 4)
        self.assertGreaterEqual(result["counts"]["missing"], 3)
        for field in result["fields"]:
            if field["verdict"] == "missing":
                self.assertEqual(field["value"], validate.MISSING)
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["start"], "20261114")


class TestGrounding(unittest.TestCase):
    def test_every_quote_in_a_brief_is_a_real_slice_of_the_page(self):
        for name in ("devpost_build_with_ai.txt", "chinese_rules.txt", "thin_announcement.txt"):
            source, result = analyse(name)
            for field in result["fields"]:
                if field["verdict"] == "missing":
                    continue
                start, end = field["span"]
                self.assertTrue(0 <= start < end <= len(source), "%s span" % field["id"])
                self.assertEqual(source[start:end], field["evidence"],
                                 "%s span does not match its quote" % field["id"])

    def test_no_brief_contains_a_number_that_is_absent_from_the_page(self):
        for name in ("devpost_build_with_ai.txt", "chinese_rules.txt", "thin_announcement.txt"):
            source, result = analyse(name)
            self.assertEqual(result["ungrounded_numbers"], [], name)

    def test_the_readers_own_output_survives_validation(self):
        source = sample("devpost_build_with_ai.txt")
        result = validate.analyse(offline.extract(source), source, mode="offline")
        self.assertEqual(result["rejected"], [])

    def test_the_reader_never_invents_a_field(self):
        raw = offline.extract("Autumn Jam")
        self.assertIsNone(raw["organizer"])
        self.assertEqual(raw["key_dates"], [])
        self.assertEqual(raw["prizes"], [])
        self.assertEqual(raw["deliverables"], [])


class TestParagraphs(unittest.TestCase):
    def test_wrapped_lines_are_merged_into_one_paragraph(self):
        segs = offline.segments("A long first line\nthat continues here.\nNew thought.")
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]["text"], "A long first line that continues here.")
        self.assertEqual(segs[1]["text"], "New thought.")

    def test_a_date_is_quoted_with_its_own_clause(self):
        text = "Submissions open September 22, 2026 at 10:00 AM PT and close " \
               "October 26, 2026 at 5:00pm ET."
        spans = offline._date_spans({"text": text}, [2026])
        clauses = [offline._date_clause(text, s, e) for s, e in spans]
        self.assertEqual(clauses[0], "Submissions open September 22, 2026 at 10:00 AM PT")
        self.assertEqual(clauses[1], "close October 26, 2026 at 5:00pm ET.")

    def test_a_dot_inside_a_word_does_not_end_a_sentence(self):
        text = "Submit by email to hello@example.com before the deadline."
        at = text.find("submit")
        self.assertEqual(offline._sentence(text, at), text)


if __name__ == "__main__":
    unittest.main()
