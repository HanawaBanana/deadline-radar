"""The scripted scenario used by the demo video, reachable by URL.

    /?demo=1   ... one page per tour step, server rendered
    /ics/<id>  ... the generated .ics text for a step
    /api/demo  ... the same steps as JSON, for a driver that would rather drive
                   a browser than follow links

Everything here runs the real product on the real samples in samples/. Step 6 is
the only synthetic one: it feeds the validator a proposal containing a
fabricated amount, to show what the validator does with an invented number.

Analyses are saved under a stable id per sample (demo-a, demo-b, demo-c), so the
history list stays short no matter which order the steps are visited in.
"""

import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES_DIR = os.path.join(ROOT, "samples")

SAMPLES = {
    "a": "devpost_build_with_ai.txt",
    "b": "chinese_rules.txt",
    "c": "thin_announcement.txt",
}

HALLUCINATED_ID = "demo-hallucinated"

STEPS = [
    {"n": 0, "title": "Paste any announcement",
     "note": "The whole product is one textarea, one button and one honest answer.",
     "focus": "composer", "sample": None},
    {"n": 1, "title": "The page goes in",
     "note": "A real competition page: dates, prizes, deliverables, judging - as prose.",
     "focus": "composer", "sample": "a", "analyse": False},
    {"n": 2, "title": "The validated brief",
     "note": "Five counters: accepted, corrected, rejected, not stated, calendar events.",
     "focus": "brief-head", "sample": "a"},
    {"n": 3, "title": "Key dates, re-parsed in plain Python",
     "note": "The page's wording on the left, ISO 8601 on the right, with the quote and "
             "character offsets that back it.",
     "focus": "dates", "sample": "a"},
    {"n": 4, "title": "Prizes and deliverables",
     "note": "Amounts are read from the quoted page text, never from the model's arithmetic.",
     "focus": "prizes", "sample": "a"},
    {"n": 5, "title": "Audit: proposal versus validated brief",
     "note": "Exactly what the reader proposed, side by side with what survived validation.",
     "focus": "audit", "sample": "a"},
    {"n": 6, "title": "Audit: an invented amount is rejected",
     "note": "This step feeds the validator a proposal with a fabricated $50,000 and a wrong "
             "deadline. Both are caught: one rejected, one corrected to the page's date.",
     "focus": "audit", "sample": "a", "inject": "hallucinate"},
    {"n": 7, "title": "Ambiguous dates: 10月26日 5:00pm ET",
     "note": "No year on the deadline line, CJK month and day, a US time zone: the year comes "
             "from the page and the field is labelled year inferred.",
     "focus": "dates", "sample": "b"},
    {"n": 8, "title": "A page with gaps",
     "note": "No prize amount, no eligibility, no deliverables. The brief says "
             "\"page does not state\" instead of inventing anything.",
     "focus": "prizes", "sample": "c"},
    {"n": 9, "title": "The calendar it produces",
     "note": "Only validated dates become events, and the deadline event carries three reminders.",
     "focus": "calendar", "sample": "a", "page": "ics"},
    {"n": 10, "title": "History",
     "note": "Every analysis is stored in a local sqlite3 file and can be reopened later.",
     "focus": "history", "sample": "a", "populate": True},
    {"n": 11, "title": "Every value points at the source",
     "note": "The page with each evidence span highlighted in place.",
     "focus": "source", "sample": "a"},
    {"n": 12, "title": "Run it yourself",
     "note": "python3 app.py --offline - no dependencies, no accounts, no network.",
     "focus": "about", "sample": "a"},
]


def step(n):
    for candidate in STEPS:
        if candidate["n"] == n:
            return candidate
    return None


def analysis_id(step_dict):
    """One saved analysis per sample, plus one for the fabricated proposal."""
    if not step_dict.get("sample"):
        return None
    if step_dict.get("inject"):
        return HALLUCINATED_ID
    return "demo-" + step_dict["sample"]


def load_sample(key):
    with open(os.path.join(SAMPLES_DIR, SAMPLES[key]), "r", encoding="utf-8") as fh:
        return fh.read()


def hallucinate(raw):
    """Return a plausible but wrong proposal: one fabricated prize, one wrong date."""
    out = copy.deepcopy(raw)
    for prize in out.get("prizes") or []:
        prize["amount"] = "$50,000"
        prize["evidence"] = "Grand Prize: $50,000 USD"
        break
    for date in out.get("key_dates") or []:
        if "deadline" in (date.get("label") or "").lower():
            date["value"] = "November 2, 2026"
            return out
    return out


def url_for(step_dict):
    if step_dict.get("page") == "ics" and step_dict.get("sample"):
        return "/ics/%s" % analysis_id(step_dict)
    return "/?demo=%d" % step_dict["n"]


def step_by_number(number, pipeline):
    """Run one tour step through the real pipeline and describe it for the page."""
    current = step(number)
    if current is None:
        return None

    source = load_sample(current["sample"]) if current.get("sample") else ""
    result = None
    saved = None
    if current.get("sample") and current.get("analyse", True):
        result, saved = pipeline.run(
            source, mode="offline", analysis_id=analysis_id(current),
            inject=hallucinate if current.get("inject") else None)
    if current.get("populate"):
        for other in STEPS:
            if other.get("sample") and other.get("analyse", True) and not other.get("inject"):
                if analysis_id(other) not in [analysis_id(s) for s in STEPS[:STEPS.index(other)]]:
                    pipeline.run(load_sample(other["sample"]), mode="offline",
                                 analysis_id=analysis_id(other))

    first, last = STEPS[0]["n"], STEPS[-1]["n"]
    tour = {
        "n": number, "total": len(STEPS), "title": current["title"], "note": current["note"],
        "focus": current["focus"], "sample": current.get("sample"),
        "prev": "/?demo=%d" % (number - 1) if number > first else None,
        "next": "/?demo=%d" % (number + 1) if number < last else None,
    }
    return {
        "number": number, "title": current["title"], "note": current["note"],
        "focus": current["focus"], "source": source, "result": result,
        "id": saved, "mode": "offline", "tour": tour, "url": url_for(current),
    }


def plan():
    """The scenario as plain data: what the video tool walks through."""
    return [{"n": s["n"], "title": s["title"], "note": s["note"], "focus": s["focus"],
             "sample": s.get("sample"), "url": url_for(s)} for s in STEPS]


def plan_json():
    return json.dumps({"steps": plan()}, indent=2)
