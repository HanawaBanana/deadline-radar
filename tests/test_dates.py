"""Date normalisation: the part of the product that must never guess."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import dates                                                    # noqa: E402


class TestFormats(unittest.TestCase):
    def test_iso_timestamp(self):
        got = dates.parse("2026-10-26T17:00:00")
        self.assertEqual(got["date"], "2026-10-26")
        self.assertEqual(got["time_display"], "17:00")
        self.assertEqual(got["precision"], "minute")

    def test_us_long_form_with_time_and_zone(self):
        got = dates.parse("Submissions close October 26, 2026 at 5:00pm ET.")
        self.assertEqual(got["iso"], "2026-10-26T17:00:00-04:00")
        self.assertEqual(got["utc"], "2026-10-26T21:00:00Z")
        self.assertEqual(got["zone"], "America/New_York")
        self.assertFalse(got["year_inferred"])

    def test_day_first_form(self):
        got = dates.parse("26 October 2026")
        self.assertEqual(got["date"], "2026-10-26")

    def test_slash_form_is_month_first_for_us_pages(self):
        got = dates.parse("20/12/2026")
        self.assertEqual(got["date"], "2026-12-20")
        self.assertTrue(got["ambiguous_order"])

    def test_cjk_full_date_with_time_and_zone(self):
        got = dates.parse("2026年9月22日 10:00 AM PT")
        self.assertEqual(got["date"], "2026-09-22")
        self.assertEqual(got["iso"], "2026-09-22T10:00:00-07:00")

    def test_ordinal_suffix_and_caps(self):
        got = dates.parse("Sep 22nd, 2026 at 5:00 PM ET")
        self.assertEqual(got["date"], "2026-09-22")
        self.assertEqual(got["time_display"], "17:00")

    def test_midnight_words(self):
        got = dates.parse("November 2, 2026 at 12:00am UTC")
        self.assertEqual(got["time_display"], "00:00")

    def test_zone_can_precede_the_date(self):
        got = dates.parse("5pm EST on 26 October 2026")
        self.assertEqual(got["date"], "2026-10-26")
        self.assertEqual(got["time_display"], "17:00")


class TestMissingYear(unittest.TestCase):
    def test_cjk_month_day_takes_the_year_from_the_page(self):
        page = "The 2026 edition. 提交截止：10月26日 5:00pm ET"
        got = dates.parse("10月26日 5:00pm ET", hints=dates.year_hints(page))
        self.assertEqual(got["date"], "2026-10-26")
        self.assertEqual(got["iso"], "2026-10-26T17:00:00-04:00")
        self.assertTrue(got["year_inferred"])

    def test_no_year_anywhere_is_reported_not_guessed(self):
        got = dates.parse("March 15")
        self.assertTrue(got["year_missing"])
        self.assertIsNone(got["iso"])
        self.assertIsNone(got["date"])

    def test_default_year_is_used_only_when_the_page_has_none(self):
        got = dates.parse("March 15", hints=[], default_year=2027)
        self.assertEqual(got["date"], "2027-03-15")
        self.assertTrue(got["year_inferred"])

    def test_a_past_month_day_rolls_into_next_year(self):
        import datetime
        got = dates.parse("January 5", hints=[2026],
                          reference=datetime.date(2026, 11, 30))
        self.assertEqual(got["date"], "2027-01-05")


class TestDaylightSaving(unittest.TestCase):
    def test_october_is_still_daylight_time(self):
        self.assertEqual(dates.parse("October 26, 2026 at 5:00pm ET")["offset"], "-04:00")

    def test_november_is_standard_time(self):
        self.assertEqual(dates.parse("November 9, 2026 at 5:00pm ET")["offset"], "-05:00")

    def test_china_never_shifts(self):
        self.assertEqual(dates.parse("2026年10月26日 5:00pm 北京时间")["offset"], "+08:00")


class TestRangesAndMentions(unittest.TestCase):
    def test_range_shares_the_year(self):
        got = dates.parse_range("September 22 - October 26, 2026", hints=[2026])
        self.assertEqual(got["start"]["date"], "2026-09-22")
        self.assertEqual(got["end"]["date"], "2026-10-26")

    def test_mentions_lists_each_date_once(self):
        got = dates.mentions("Opens September 22, 2026 and closes October 26, 2026.",
                             hints=[2026])
        self.assertEqual([d["date"] for d in got], ["2026-09-22", "2026-10-26"])

    def test_a_phrase_that_only_looks_like_a_date_is_not_one(self):
        self.assertIsNone(dates.parse("a 1 to 3 minute demo video"))
        self.assertEqual(dates.mentions("a 1 to 3 minute demo video"), [])


if __name__ == "__main__":
    unittest.main()
