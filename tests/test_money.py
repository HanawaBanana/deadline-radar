"""Prize parsing and the "no invented numbers" rule."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import money                                                     # noqa: E402


class TestAmounts(unittest.TestCase):
    def test_dollar_amount_with_currency_word(self):
        got = money.parse_amount("Grand Prize: $5,000 USD")
        self.assertEqual(got["amount"], "5000")
        self.assertEqual(got["currency"], "USD")
        self.assertEqual(got["display"], "$5,000 USD")

    def test_euro_symbol(self):
        got = money.parse_amount("Runner up: €2,500")
        self.assertEqual(got["amount"], "2500")
        self.assertEqual(got["currency"], "EUR")

    def test_words_instead_of_a_symbol(self):
        got = money.parse_amount("Winner: 3,000 dollars")
        self.assertEqual(got["amount"], "3000")
        self.assertEqual(got["currency"], "USD")

    def test_bare_number_is_only_money_in_a_money_sentence(self):
        self.assertIsNone(money.parse_amount("the event runs for 2 days"))
        self.assertEqual(money.parse_amount("First place 1,000")["amount"], "1000")

    def test_non_cash_prize(self):
        got = money.parse_amount("mentorship and cloud credits")
        self.assertFalse(got["cash"])
        self.assertEqual(got["display"], "non-cash")

    def test_yuan(self):
        got = money.parse_amount("一等奖：5,000 元")
        self.assertEqual(got["currency"], "CNY")


class TestFindingSpans(unittest.TestCase):
    def test_find_amounts_keeps_offsets(self):
        text = "Grand Prize: $5,000 USD, Second place: $2,000 USD"
        found = money.find_amounts(text)
        self.assertEqual([a["amount"] for a in found], ["5000", "2000"])
        self.assertEqual(text[found[0]["start"]:found[0]["end"]], "$5,000 USD")

    def test_numbers_in_normalises_commas(self):
        self.assertEqual(money.numbers_in("$5,000 and 2,000 and 30"),
                         ["5000", "2000", "30"])


if __name__ == "__main__":
    unittest.main()
