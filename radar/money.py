"""Prize string parsing. Deterministic, no model involved.

"$5,000 USD", "5,000 US dollars", "€2,500", "Grand Prize 1,000 元", or a
non-cash line such as "mentorship and cloud credits" all become the same small
structure, so the brief never repeats a model's arithmetic to the reader.
"""

import re

CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "CNY", "元": "CNY"}

CURRENCY_WORDS = {
    "usd": "USD", "us dollar": "USD", "us dollars": "USD", "dollar": "USD", "dollars": "USD",
    "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "gbp": "GBP", "pound": "GBP", "pounds": "GBP",
    "cny": "CNY", "rmb": "CNY", "yuan": "CNY", "元": "CNY",
    "jpy": "JPY", "yen": "JPY", "美元": "USD", "人民币": "CNY",
}

MONEY_WORDS = ("prize", "award", "cash", "pool", "grand", "place", "winner", "payout", "奖金")

NON_CASH = ("mentorship", "cloud credits", "credits", "swag", "recognition",
            "certificate", "feature", "interview", "no cash", "bragging")

_AMOUNT_RE = re.compile(r"(?<![\d])(?:([$€£¥元])\s*)?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
                        r"\s*(k\b|m\b)?(?:\s*([A-Za-z]{3,20}|元|美元|人民币))?", re.I)


def parse_amount(text):
    """Return {amount, currency, display, raw, cash} or None."""
    if not text or not isinstance(text, str):
        return None
    low = text.lower()
    for m in _AMOUNT_RE.finditer(text):
        symbol, digits, scale, word = m.group(1), m.group(2), m.group(3), m.group(4)
        known_word = bool(word) and word.lower().strip(".,") in CURRENCY_WORDS
        if not symbol and not known_word:
            # a bare number is only money in a sentence that is about money
            if not any(w in low for w in MONEY_WORDS):
                continue
        try:
            value = float(digits.replace(",", ""))
        except ValueError:
            continue
        if scale and scale.lower().startswith("k"):
            value *= 1000
        if value <= 0:
            continue
        currency = None
        if symbol:
            currency = CURRENCY_SYMBOLS.get(symbol)
        if word:
            currency = CURRENCY_WORDS.get(word.lower().strip(".,")) or currency
        amount = ("%d" % value) if value == int(value) else ("%.2f" % value)
        return {
            "amount": amount,
            "currency": currency or "unspecified",
            "display": _display(symbol, digits, scale, currency),
            "raw": m.group(0).strip(),
            "cash": True,
        }
    for word in NON_CASH:
        if word in low:
            return {"amount": None, "currency": None, "display": "non-cash", "raw": text.strip(),
                    "cash": False}
    return None


def _display(symbol, digits, scale, currency):
    out = (symbol or "") + digits + ("K" if scale else "")
    if currency and currency != "unspecified":
        out += " " + currency
    return out.strip()


def numbers_in(text):
    """Every numeric token in `text`, normalised (commas removed)."""
    out = []
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text or ""):
        tok = m.group(0).rstrip(".,")
        norm = tok.replace(",", "")
        if norm and norm not in out:
            out.append(norm)
    return out


def find_amounts(text):
    """Every money-looking span in `text`, with offsets into `text`."""
    out = []
    low = (text or "").lower()
    for m in _AMOUNT_RE.finditer(text or ""):
        symbol, digits, scale, word = m.group(1), m.group(2), m.group(3), m.group(4)
        known_word = bool(word) and word.lower().strip(".,") in CURRENCY_WORDS
        if not symbol and not known_word:
            if not any(w in low for w in MONEY_WORDS):
                continue
        currency = CURRENCY_SYMBOLS.get(symbol) if symbol else None
        if word:
            currency = CURRENCY_WORDS.get(word.lower().strip(".,")) or currency
        try:
            value = float(digits.replace(",", ""))
        except ValueError:
            continue
        if scale and scale.lower().startswith("k"):
            value *= 1000
        if value <= 0:
            continue
        out.append({
            "amount": ("%d" % value) if value == int(value) else ("%.2f" % value),
            "currency": currency or "unspecified",
            "display": _display(symbol, digits, scale, currency),
            "raw": m.group(0).strip(),
            "start": m.start(), "end": m.end(),
        })
    return out
