"""The .ics file: valid RFC 5545, and only dates the validator accepted."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import ics                                                       # noqa: E402
from radar import offline                                                   # noqa: E402
from radar import validate                                                  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def result_for(name="devpost_build_with_ai.txt"):
    with open(os.path.join(ROOT, "samples", name), "r", encoding="utf-8") as fh:
        source = fh.read()
    return validate.analyse(offline.extract(source), source, mode="offline")


class TestStructure(unittest.TestCase):
    def setUp(self):
        self.text = ics.build(result_for())
        self.lines = self.text.split("\r\n")

    def test_wrapped_with_the_right_envelope(self):
        self.assertTrue(self.text.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(self.text.endswith("END:VCALENDAR\r\n"))

    def test_every_line_ends_with_crlf(self):
        self.assertNotIn("\n\n", self.text)
        for line in self.lines[:-1]:
            self.assertFalse(line.endswith("\r"), repr(line))

    def test_begin_and_end_blocks_are_balanced(self):
        self.assertEqual(self.lines.count("BEGIN:VEVENT"), self.lines.count("END:VEVENT"))
        self.assertEqual(self.lines.count("BEGIN:VALARM"), self.lines.count("END:VALARM"))

    def test_required_properties_are_present(self):
        for prop in ("VERSION:2.0", "PRODID:", "CALSCALE:GREGORIAN", "DTSTAMP:"):
            self.assertTrue(any(line.startswith(prop) for line in self.lines), prop)

    def test_line_folding_keeps_lines_under_76_octets(self):
        for line in self.lines:
            self.assertLessEqual(len(line.encode("utf-8")), 75)

    def test_long_descriptions_are_folded_and_still_one_property(self):
        text = ics.build(result_for())
        unfolded = text.replace("\r\n ", "")
        self.assertIn("DESCRIPTION:", unfolded)
        self.assertIn("Validated by Deadline Radar", unfolded)


class TestEvents(unittest.TestCase):
    def test_deadline_event_carries_three_reminders(self):
        text = ics.build(result_for())
        blocks = text.split("BEGIN:VEVENT")
        deadline = [b for b in blocks if "Submission deadline" in b]
        self.assertEqual(len(deadline), 1)
        self.assertEqual(deadline[0].count("BEGIN:VALARM"), 3)
        for trigger in ("TRIGGER:-P7D", "TRIGGER:-P1D", "TRIGGER:-PT2H"):
            self.assertIn(trigger, deadline[0])

    def test_a_timed_event_is_written_in_utc(self):
        text = ics.build(result_for())
        self.assertIn("DTSTART:20261026T210000Z", text)

    def test_an_all_day_event_uses_value_date(self):
        text = ics.build(result_for())
        self.assertIn("DTSTART;VALUE=DATE:20261201", text)

    def test_uids_are_stable_between_runs(self):
        self.assertEqual(ics.build(result_for()), ics.build(result_for()))

    def test_only_validated_dates_become_events(self):
        with open(os.path.join(ROOT, "samples", "thin_announcement.txt"), encoding="utf-8") as fh:
            source = fh.read()
        raw = offline.extract(source)
        raw["key_dates"].append({"label": "not a date", "value": "soon",
                                 "evidence": "soon"})
        result = validate.analyse(raw, source, mode="offline")
        text = ics.build(result)
        self.assertEqual(text.count("BEGIN:VEVENT"), 1)

    def test_escaping_commas_and_semicolons(self):
        event = {"uid": "u@x", "summary": "One, two; three", "start": "20261026",
                 "end": "20261027", "all_day": True, "description": "a\nb",
                 "alarms": []}
        text = ics.build({"events": [event], "brief": {"title": "T"}})
        self.assertIn("SUMMARY:One\\, two\\; three", text)
        self.assertIn("DESCRIPTION:a\\nb", text)

    def test_filename_is_a_slug(self):
        result = result_for()
        self.assertEqual(ics.filename(result), "build-with-ai-basics-deadlines.ics")


if __name__ == "__main__":
    unittest.main()
