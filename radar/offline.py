"""Offline extraction: a deterministic reader that needs no network.

This is the module that runs in `--offline` mode, in every unit test and in the
demo recording. It reads the same page the language model would read and emits
the *same JSON shape*, so the audit panel, the validator and the calendar do not
know or care which reader produced the proposal.

Being rule based, it can only quote text that is really on the page. That makes
it a useful floor: if the model ever disagrees with it, the validator shows both.
"""

import re

from . import dates as D
from . import money
from .validate import canonical_label

# Words that introduce the *sentence about* a field. They are deliberately
# specific: "submission" alone would match the heading "Submission window".
CHANNEL_WORDS = ("submit your", "submit by", "submit at", "submit to", "submit on",
                 "submit through", "upload", "enter at", "apply at", "apply through",
                 "portal", "email your", "send your", "open an issue")

DELIVERABLE_WORDS = ("must include", "must submit", "must contain", "should include", "required",
                     "deliverable", "provide", "consist of", "entail", "need to", "please include",
                     "必须提交", "必须提供", "需要提供", "必须包含")

ELIGIBILITY_WORDS = ("open to", "eligible", "eligibility", "who can", "must be", "only for",
                     "restricted to", "limited to", "18 years", "students", "residents", "开放给")

# A trailing clause introduced by a past participle ("... , written during the
# event") is not itself a deliverable.
CLAUSE_START_RE = re.compile(r"^(written|created|made|submitted|built|developed|posted|hosted|"
                             r"published|recorded|used|named)\b", re.I)

ORGANIZER_RE = re.compile(
    r"(?:organised|organized|hosted|run|presented)\s+by\s+([A-Z][\w&.\- ]{2,60}?)(?:[\.,;!]|\s+in\s|\s+for\s|$)",
    re.I)
TITLE_RE = re.compile(r"^\s*(?:title|event|competition|challenge)\s*[:\-]\s*(.+)$", re.I)

TIME_TAIL_RE = re.compile(
    r"^[,\s]*(?:at\s+|@\s*)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*"
    r"(?:ET|EST|EDT|CT|CDT|MT|MDT|PT|PST|PDT|UTC|GMT)\b", re.I)

DATE_PATTERNS = [D._ISO_RE, D._CJK_RE, D._MONTH_FIRST_RE, D._DAY_FIRST_RE, D._SLASH_RE]

# Clause boundaries used to quote one date at a time.
DATE_BREAKS = (" and ", "; ", ". ", "。", "\n", " through ", " until ", " 至 ")


def segments(text):
    """Non-empty paragraphs with their offsets, so every quote is a real slice.

    A line that starts with a lowercase letter is almost always a wrapped
    continuation of the line above, so it is merged into the same paragraph and
    joined with one space. The offsets still cover the original text.
    """
    text = text or ""
    out = []
    pos = 0
    for line in text.splitlines(True):
        body = line.rstrip("\n").rstrip("\r")
        if body.strip():
            if out and body[:1].islower():
                out[-1]["end"] = pos + len(body)
                out[-1]["text"] = re.sub(r"[ \t]*\n[ \t]*", " ",
                                         text[out[-1]["start"]:out[-1]["end"]])
            else:
                out.append({"start": pos, "end": pos + len(body), "text": body})
        pos += len(line)
    return out


def _break_at(text, i):
    """True when position `i` ends a sentence. A dot inside a word does not."""
    if text[i] in "。!?":
        return True
    if text[i] == ".":
        return i + 1 >= len(text) or text[i + 1] in " \t\n\r"
    return False


def _sentence(text, index):
    """The sentence around `index`, used to keep a value short and readable."""
    left = 0
    for i in range(index - 1, -1, -1):
        if _break_at(text, i):
            left = i + 1
            break
    right = len(text)
    for i in range(index, len(text)):
        if _break_at(text, i):
            right = i + 1
            break
    return text[left:right].strip()


def _date_clause(text, start, end):
    """Quote one date, cutting at the nearest clause boundary on both sides."""
    left = 0
    for i in range(start - 1, -1, -1):
        for brk in DATE_BREAKS:
            if text.startswith(brk, i):
                left = i + len(brk)
                break
        else:
            continue
        break
    right = len(text)
    for i in range(end, len(text)):
        if any(text.startswith(brk, i) for brk in DATE_BREAKS):
            right = i
            break
    return text[left:right].strip() or text[start:end].strip()


def _first_index(text, words):
    low = text.lower()
    best = -1
    for word in words:
        found = low.find(word)
        if found >= 0 and (best < 0 or found < best):
            best = found
    return best


def _date_spans(seg, hints=None):
    """Real dates on this paragraph. A phrase like "3 minute" is not a date."""
    spans = []
    for regex in DATE_PATTERNS:
        for m in regex.finditer(seg["text"]):
            if any(m.start() >= s[0] and m.start() < s[1] for s in spans):
                continue
            start, end = m.start(), m.end()
            tm = TIME_TAIL_RE.match(seg["text"][end:])
            if tm:
                end += tm.end()
            if D.parse(seg["text"][start:end], hints=hints or []) is None:
                continue
            spans.append((start, end))
    spans.sort()
    return spans


def _trim(seg, start, end):
    """Smallest comma/clause sized quote containing the span."""
    text = seg["text"]
    left = 0
    for i in range(start - 1, -1, -1):
        if text[i] in ",;。|":
            left = i + 1
            break
    right = len(text)
    for i in range(end, len(text)):
        if text[i] in ",;。|":
            right = i
            break
    return text[left:right].strip() or text[start:end].strip()


def _label_for(text, prev_end, start):
    """Name a date from the words between it and the previous date on the line."""
    between = text[prev_end:start]
    if between.strip():
        key, human = canonical_label(between)
        if key != "date":
            return key, human
    return canonical_label(text[:start][-70:])


def extract(source, default_year=None):
    """Return a proposal dict in the same shape the language model returns."""
    segs = segments(source)
    hints = D.year_hints(source)
    raw = {
        "title": None, "organizer": None, "submission_channel": None, "eligibility": None,
        "key_dates": [], "prizes": [], "deliverables": [],
        "reader": "offline-regex",
    }

    head = next((s for s in segs if len(s["text"].strip()) > 2), None)
    if head:
        tm = TITLE_RE.match(head["text"])
        title = tm.group(1).strip() if tm else head["text"].strip()
        if len(title) > 90:
            title = title[:90].rsplit(" ", 1)[0]
        raw["title"] = {"value": title, "evidence": head["text"].strip()}

    seen_dates = set()
    seen_prizes = set()
    for seg in segs:
        text = seg["text"]
        low = text.lower()

        if not raw["organizer"]:
            om = ORGANIZER_RE.search(text)
            if om:
                raw["organizer"] = {"value": om.group(1).strip(), "evidence": text.strip()}

        prev_end = 0
        for start, end in _date_spans(seg, hints):
            value = text[start:end].strip()
            key, human = _label_for(text, prev_end, start)
            prev_end = end
            probe = "%s|%s" % (key, value.lower())
            if probe in seen_dates:
                continue
            seen_dates.add(probe)
            raw["key_dates"].append({"label": human, "value": value,
                                     "evidence": _date_clause(text, start, end)})

        amounts = money.find_amounts(text)
        if amounts and ("prize" in low or "award" in low or "奖金" in text
                        or any(a["currency"] != "unspecified" for a in amounts)):
            for amt in amounts:
                probe = amt["amount"] + "|" + amt["currency"]
                if probe in seen_prizes:
                    continue
                seen_prizes.add(probe)
                quote = _trim(seg, amt["start"], amt["end"])
                place = quote.split(amt["raw"])[0].strip(" :-\u2013") if amt["raw"] in quote else ""
                raw["prizes"].append({"place": place, "amount": amt["display"],
                                      "currency": amt["currency"], "evidence": quote})

        if not raw["submission_channel"]:
            at = _first_index(text, CHANNEL_WORDS)
            if at >= 0:
                sentence = _sentence(text, at)
                raw["submission_channel"] = {"value": sentence, "evidence": sentence}
        if not raw["eligibility"]:
            at = _first_index(text, ELIGIBILITY_WORDS)
            if at >= 0:
                sentence = _sentence(text, at)
                raw["eligibility"] = {"value": sentence, "evidence": sentence}
        if any(w in low for w in DELIVERABLE_WORDS):
            for item in _deliverables(text):
                raw["deliverables"].append({"value": item, "evidence": text.strip()})

    raw["key_dates"] = raw["key_dates"][:8]
    raw["prizes"] = raw["prizes"][:6]
    raw["deliverables"] = raw["deliverables"][:6]
    return raw


def _deliverables(text):
    """Pull the noun phrases out of a requirement sentence."""
    if len(text.strip()) <= 12:
        return []                                        # a heading such as a section title
    low = text.lower()
    cut = None
    for word in DELIVERABLE_WORDS:
        i = low.find(word)
        if i >= 0 and (cut is None or i < cut):
            cut = i
    if cut is None:
        return []
    body = text[cut:]
    body = re.sub(r"^[^:：]{0,40}[:：]", "", body)
    body = re.sub(r"^\W*(must|should|need to|please|have to|be sure to|必须|需要|请|需)\W*"
                  r"(include|contain|submit|provide|consist of|entail|提交|提供|包含)\W*",
                  "", body, flags=re.I)
    parts = re.split(r"\s*(?:,| and | as well as | plus |;|、|，|和)\s*", body.strip())
    out = []
    for part in parts:
        part = part.strip(" .;:。")
        if not (3 <= len(part) <= 90):
            continue
        if part.lower().startswith(("you", "we", "it")) or CLAUSE_START_RE.match(part):
            continue
        out.append(part)
    return out[:4]
