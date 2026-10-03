"""The validator: deterministic code that decides what is true.

The language model produces a *proposal*. This module turns that proposal into a
brief by applying four rules to every field, and it records what it did to each
one so the reader can audit it:

R1  the evidence span the model quotes must really exist in the page;
R2  every number the model writes must exist in the page (a year that was
    inferred from the only year on the page is the single allowed exception,
    and it is labelled as inferred);
R3  dates are re-parsed here, and when the page and the model disagree the page
    wins -- the field is marked `corrected`, never silently accepted;
R4  a field the model leaves empty becomes the literal string
    `page does not state` -- the product never invents a value to fill a gap.

Nothing here calls the network.
"""

import datetime
import hashlib
import re

from . import dates as D
from . import money

MISSING = "page does not state"

LABEL_RULES = [
    ("event_date", "Event date",
     ("event starts", "event begins", "hackathon begins", "hackathon starts", "demo day",
      "kickoff", "kick-off", "finalist", "finals", "活动", "决赛")),
    ("submission_open", "Submissions open",
     ("submission opens", "submissions open", "opens", "opening", "registration",
      "starts", "start date", "begins", "kick", "开始", "报名", "开放")),
    ("submission_deadline", "Submission deadline",
     ("submission deadline", "deadline", "closes", "close", "due", "final date",
      "entries", "entry", "截止", "提交截止")),
    ("judging", "Judging period",
     ("judg", "review", "evaluat", "assess", "screening", "评审")),
    ("winners_announced", "Winners announced",
     ("winner", "announce", "result", "notif", "award", "ceremony", "颁奖", "公示", "结果")),
    ("submission_deadline", "Submission deadline",
     ("submit", "submission", "提交", "接收")),
]
TEXT_FIELDS = [
    ("title", "Event"),
    ("organizer", "Organiser"),
    ("submission_channel", "Submission channel"),
    ("eligibility", "Eligibility"),
]

LIST_FIELDS = [
    ("key_dates", "Key dates"),
    ("prizes", "Prizes"),
    ("deliverables", "Deliverables"),
]

SKEL_RE = re.compile(r"[0-9a-zA-Z\u4e00-\u9fff]+")
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
DATEY_RE = re.compile(
    r"[A-Za-z]{3,9}\.?\s*\d{1,2}|\d{1,2}\s*[A-Za-z]{3,9}|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}|\d{1,2}\s*月")



# --------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------

def collapse(text):
    """Whitespace-collapsed copy plus a map back to original offsets."""
    chars, idx = [], []
    prev_space = True
    for i, ch in enumerate(text):
        if ch.isspace():
            if not prev_space:
                chars.append(" ")
                idx.append(i)
                prev_space = True
            continue
        chars.append(ch)
        idx.append(i)
        prev_space = False
    return "".join(chars), idx


def skeleton(text):
    """Letters, digits and CJK only, lowercased, with a map to offsets."""
    chars, idx = [], []
    for m in SKEL_RE.finditer(text):
        for k, ch in enumerate(m.group(0).lower()):
            chars.append(ch)
            idx.append(m.start() + k)
    return "".join(chars), idx


def looks_like_date(text):
    return bool(text) and bool(DATEY_RE.search(text))


class Page(object):
    """A source document with the indexes the validator needs."""

    def __init__(self, text, default_year=None, today=None):
        self.text = text or ""
        self.collapsed, self.col_idx = collapse(self.text)
        self.skel, self.skel_idx = skeleton(self.text)
        self.tokens = money.numbers_in(self.text)
        self.hints = D.year_hints(self.text)
        self.default_year = default_year if default_year is not None else (
            max(self.hints) if self.hints else None)
        self.today = today or datetime.date.today()

    def find(self, needle):
        """Locate `needle` in the page. Returns (start, end, text, how) or None."""
        needle = (needle or "").strip()
        if not needle:
            return None
        n = " ".join(needle.split())
        pos = self.collapsed.find(n)
        if pos >= 0:
            return self._span_from(pos, len(n), n)
        pos = self.collapsed.lower().find(n.lower())
        if pos >= 0:
            return self._span_from(pos, len(n), n, "matched after ignoring letter case")
        sk, _ = skeleton(needle)
        if sk:
            pos = self.skel.find(sk)
            if pos >= 0:
                return self._span_from(pos, len(sk), needle,
                                       "matched after ignoring punctuation and spacing", skel=True)
        return None

    def _span_from(self, pos, length, needle, how="found in the page verbatim", skel=False):
        col, idx = (self.skel_idx, self.skel_idx) if skel else (self.col_idx, self.col_idx)
        if pos + length - 1 >= len(idx):
            return None
        start, end = idx[pos], idx[pos + length - 1] + 1
        return {"start": start, "end": end, "text": self.text[start:end], "how": how}

    def grounded(self, token):
        if token in self.tokens:
            return True
        return bool(re.search(r"(?<!\d)" + re.escape(token) + r"(?!\d)", self.text))

    def ungrounded_numbers(self, value):
        return [t for t in money.numbers_in(value) if not self.grounded(t)]


# --------------------------------------------------------------------------
# field helpers
# --------------------------------------------------------------------------

def _text_of(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("value", "text", "date", "amount", "label", "raw"):
            if value.get(key):
                return str(value[key]).strip()
        return ""
    if isinstance(value, list):
        return " ".join(_text_of(v) for v in value).strip()
    return str(value).strip()


def _evidence_of(item):
    if isinstance(item, dict):
        for key in ("evidence", "quote", "source", "span"):
            if item.get(key):
                return str(item[key]).strip()
    return ""


def canonical_label(label):
    """Map a model-written label onto the product's own date vocabulary."""
    low = (label or "").lower()
    for key, human, words in LABEL_RULES:
        for w in words:
            if w in low:
                return key, human
    return "date", "Other date"


def _field(fid, name, label, kind, value, evidence, span, verdict, reason, **extra):
    out = {
        "id": fid, "name": name, "label": label, "kind": kind,
        "value": value, "evidence": evidence, "span": span,
        "verdict": verdict, "reason": reason,
    }
    out.update(extra)
    return out


# --------------------------------------------------------------------------
# per-kind validation
# --------------------------------------------------------------------------

def validate_text_field(page, fid, name, label, raw_value, raw_evidence):
    raw_value = _text_of(raw_value)
    raw_evidence = _evidence_of({"evidence": raw_evidence}) or raw_evidence
    if not raw_value and not raw_evidence:
        return _field(fid, name, label, "text", MISSING, "", None, "missing",
                      "the page does not state this")
    found = page.find(raw_evidence) if raw_evidence else None
    if found is None and raw_value:
        found = page.find(raw_value)
        if found is not None:
            raw_evidence = raw_value
    if found is None:
        return _field(fid, name, label, "text", MISSING, raw_evidence, None, "rejected",
                      "the quoted evidence is not in the page and the value was not found either",
                      raw_value=raw_value)
    bad = page.ungrounded_numbers(raw_value)
    inside = raw_value and skeleton(raw_value)[0] in skeleton(found["text"])[0]
    if bad:
        return _field(fid, name, label, "text", found["text"], found["text"],
                      [found["start"], found["end"]], "corrected",
                      "the proposed value contained %s, which is not in the page; the page's own wording was kept"
                      % ", ".join(bad), raw_value=raw_value)
    if not raw_value:
        return _field(fid, name, label, "text", found["text"], found["text"],
                      [found["start"], found["end"]], "corrected",
                      "the model returned no value but quoted the page; the quote was used",
                      raw_value=raw_value)
    if inside:
        value = raw_value
        verdict = "accepted"
        reason = found["how"] if found["how"] != "found in the page verbatim" else "value found in the page"
        return _field(fid, name, label, "text", value, found["text"],
                      [found["start"], found["end"]], verdict, reason, raw_value=raw_value)
    return _field(fid, name, label, "text", found["text"], found["text"],
                  [found["start"], found["end"]], "corrected",
                  "the page's own wording was kept; the proposed value is not literally in the page",
                  raw_value=raw_value)


def validate_date_field(page, fid, name, label, raw_value, raw_evidence, reference=None):
    raw_value = _text_of(raw_value)
    if not raw_value and not raw_evidence:
        return _field(fid, name, label, "date", MISSING, "", None, "missing",
                      "the page does not state this")
    if not raw_value:
        raw_value = raw_evidence
    bad = page.ungrounded_numbers(raw_value)
    if bad:
        return _field(fid, name, label, "date", MISSING, raw_evidence, None, "rejected",
                      "the proposed date contains %s, which is not in the page" % ", ".join(bad),
                      raw_value=raw_value)
    found = page.find(raw_evidence) if raw_evidence else None
    if found is None:
        found = page.find(raw_value)
    if found is None:
        return _field(fid, name, label, "date", MISSING, raw_evidence, None, "rejected",
                      "the quoted evidence is not in the page and the value was not found either",
                      raw_value=raw_value)

    proposed = D.parse(raw_value, hints=page.hints, default_year=page.default_year,
                       reference=reference)
    grounded_value = bool(raw_value) and skeleton(raw_value)[0] in skeleton(found["text"])[0]
    from_page = None
    page_dates = []
    if looks_like_date(found["text"]):
        page_dates = D.mentions(found["text"], hints=page.hints,
                                default_year=page.default_year, reference=reference)
    if not grounded_value:
        if len(page_dates) == 1:
            from_page = page_dates[0]
        elif len(page_dates) > 1:
            return _field(fid, name, label, "date", MISSING, found["text"],
                          [found["start"], found["end"]], "rejected",
                          "the quoted evidence contains %d dates and the proposed value is not one "
                          "of them, so there is nothing to compare it with" % len(page_dates),
                          raw_value=raw_value)
    verdict, reason = "accepted", "the date is on the page exactly as reported"
    chosen = proposed
    if from_page and from_page.get("date") and (
            not proposed or not proposed.get("date") or proposed["date"] != from_page["date"]):
        chosen = from_page
        verdict = "corrected"
        reason = "the page states %s; the model wrote %s -- the page wins" % (
            from_page.get("raw") or from_page.get("display"), raw_value)
    elif proposed and proposed.get("year_missing"):
        return _field(fid, name, label, "date", "%s (year not stated)" % proposed["display"],
                      found["text"], [found["start"], found["end"]], "rejected",
                      "the page gives a month and day but no year, so no calendar date can be built",
                      raw_value=raw_value)
    elif not chosen:
        return _field(fid, name, label, "date", MISSING, found["text"],
                      [found["start"], found["end"]], "rejected",
                      "no date could be parsed from the page text for this field",
                      raw_value=raw_value)

    extra = {
        "raw_value": raw_value,
        "iso": chosen.get("iso"),
        "utc": chosen.get("utc"),
        "display": chosen.get("display"),
        "precision": chosen.get("precision", "day"),
        "zone": chosen.get("zone"),
        "year_inferred": bool(chosen.get("year_inferred")),
    }
    if chosen.get("year_inferred") and verdict == "accepted":
        reason = ("the year is not written next to this date; it was inferred from the only year "
                  "on the page"
                  if len(page.hints) <= 1 else
                  "the year is not written next to this date; it was inferred from the closest "
                  "year on the page")
    elif chosen.get("year_inferred"):
        reason += "; the year was inferred from the page"
    return _field(fid, name, label, "date", chosen.get("date") or chosen.get("display"),
                  found["text"], [found["start"], found["end"]], verdict, reason, **extra)


def validate_prize_field(page, fid, name, label, item, index):
    raw_value = _text_of(item.get("amount") or item.get("value") or item)
    raw_place = (item.get("place") or item.get("label") or "").strip() if isinstance(item, dict) else ""
    evidence = _evidence_of(item)
    if not evidence:
        evidence = item.get("value") if isinstance(item, dict) else ""
        evidence = _text_of(evidence)
    if not raw_value and not evidence:
        return _field(fid, name, label, "prize", MISSING, "", None, "missing",
                      "the page does not state this")
    found = page.find(evidence) if evidence else None
    if found is None and raw_value:
        found = page.find(raw_value)
    if found is None:
        return _field(fid, name, label, "prize", MISSING, evidence, None, "rejected",
                      "the quoted evidence is not in the page, so the prize cannot be confirmed",
                      raw_value=raw_value)

    on_page = money.parse_amount(found["text"])
    proposed = money.parse_amount(raw_place + " " + raw_value) if raw_value else None
    if proposed and proposed.get("amount") and (
            not on_page or on_page.get("amount") != proposed["amount"]):
        return _field(fid, name, label, "prize", MISSING, found["text"],
                      [found["start"], found["end"]], "rejected",
                      "the model claims %s but the quoted page text says %s"
                      % (proposed["display"], (on_page or {}).get("display", "no amount")),
                      raw_value=proposed["display"])
    if proposed and proposed.get("amount") and not page.grounded(proposed["amount"]):
        return _field(fid, name, label, "prize", MISSING, found["text"],
                      [found["start"], found["end"]], "rejected",
                      "the amount %s does not appear in the page" % proposed["display"],
                      raw_value=proposed["display"])

    place = raw_place or ("Prize %d" % (index + 1))
    verdict = "accepted"
    reason = "amount read from the page"
    if not on_page or not on_page.get("cash"):
        cash_amount = MISSING if not on_page else "non-cash"
    else:
        cash_amount = on_page["display"]
    if raw_place and page.find(raw_place) is None:
        place = ("Prize %d" % (index + 1))
        verdict = "corrected"
        reason = "the place label the model wrote is not in the page; it was replaced with the prize order"
    if not on_page:
        cash_amount = MISSING
        verdict = "corrected"
        reason = "the quoted page text states no amount; the prize is recorded as unquantified"
    return _field(fid, name, label, "prize", cash_amount, found["text"],
                  [found["start"], found["end"]], verdict, reason,
                  raw_value=proposed["display"] if proposed else raw_value, place=place,
                  amount=(on_page or {}).get("amount"), currency=(on_page or {}).get("currency"))


# --------------------------------------------------------------------------
# top level
# --------------------------------------------------------------------------

def analyse(raw, source, mode="offline", now=None, default_year=None, reference=None):
    """Validate a model proposal against the page it was read from."""
    page = Page(source, default_year=default_year, today=reference)
    reference = reference or page.today
    raw = raw or {}
    fields = []
    rejected = []

    for name, label in TEXT_FIELDS:
        item = raw.get(name)
        ev = _evidence_of(item)
        f = validate_text_field(page, name, name, label, item, ev)
        (fields if f["verdict"] != "rejected" else rejected).append(f)

    for name, label in LIST_FIELDS:
        items = raw.get(name) or []
        if isinstance(items, dict):
            items = [items]
        if not items:
            fields.append(_field(name, name, label, "list", MISSING, "", None, "missing",
                                 "the page does not state this"))
            continue
        for i, item in enumerate(items):
            fid = "%s[%d]" % (name, i)
            if name == "key_dates":
                label_key, human = canonical_label(item.get("label") or item.get("value"))
                f = validate_date_field(page, fid, label_key, human, item.get("value") or item.get("date"),
                                        _evidence_of(item), reference=reference)
                f["raw_label"] = (item.get("label") or "").strip()
            elif name == "prizes":
                f = validate_prize_field(page, fid, name, label, item, i)
            else:
                f = validate_text_field(page, fid, name, label, item.get("value") or item,
                                        _evidence_of(item))
            (fields if f["verdict"] != "rejected" else rejected).append(f)

    dates_only = [f for f in fields if f["kind"] == "date" and f.get("iso")]
    dates_only.sort(key=lambda f: (f["iso"], f["label"]))
    brief = _brief_from(fields)

    ungrounded = []
    for f in fields:
        if f["kind"] == "date":
            continue
        for token in page.ungrounded_numbers(str(f.get("value") or "")):
            if token not in ungrounded:
                ungrounded.append(token)
    counts = {"accepted": 0, "corrected": 0, "rejected": len(rejected), "missing": 0}
    for f in fields:
        counts[f["verdict"]] = counts.get(f["verdict"], 0) + 1

    return {
        "mode": mode,
        "created_at": (now or datetime.datetime.now()).isoformat(timespec="seconds"),
        "source": {
            "chars": len(page.text),
            "sha256": hashlib.sha256(page.text.encode("utf-8")).hexdigest()[:16],
            "years": page.hints,
            "default_year": page.default_year,
            "lines": page.text.count("\n") + 1,
        },
        "raw": raw,
        "fields": fields,
        "rejected": rejected,
        "key_dates": [f for f in dates_only],
        "brief": brief,
        "counts": counts,
        "ungrounded_numbers": ungrounded,
        "events": events_from(fields, brief.get("title")),
    }


def _brief_from(fields):
    out = {}
    for f in fields:
        if f["kind"] == "text":
            out[f["name"]] = f["value"]
    for name, _label in LIST_FIELDS:
        out[name] = [f for f in fields if f["name"] == name
                     or f["name"].split("[")[0] == name]
    return out


def events_from(fields, title):
    """Calendar events, built only from dates the validator accepted."""
    events = []
    for f in fields:
        if f["kind"] != "date" or not f.get("iso"):
            continue
        iso = f["iso"]
        all_day = f.get("precision") == "day"
        start = "%04d%02d%02d" % tuple(int(p) for p in f["value"].split("-"))
        if all_day:
            end = (datetime.date(int(f["value"][:4]), int(f["value"][5:7]), int(f["value"][8:10]))
                   + datetime.timedelta(days=1)).strftime("%Y%m%d")
        else:
            end = None
        uid = hashlib.sha1(("deadline-radar|%s|%s" % (f["name"], iso)).encode()).hexdigest()[:20]
        events.append({
            "uid": uid + "@deadline-radar.local",
            "summary": "%s - %s" % (f["label"], title or "Deadline Radar brief"),
            "start": start,
            "end": end,
            "utc": f.get("utc"),
            "all_day": all_day,
            "description": "%s\nSource text: %s\nValidated by Deadline Radar (%s = %s)"
                           % (f.get("iso"), f.get("evidence", "").replace("\n", " "),
                              f["name"], f["verdict"]),
            "alarms": ["-P7D", "-P1D", "-PT2H"] if f["name"] == "submission_deadline"
                      else ["-P1D", "-PT2H"],
            "field": f["name"],
        })
    return events
