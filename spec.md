# spec.md — Deadline Radar

Exact behaviour of the shipping version. If the code and this document disagree,
one of them is a bug; the tests in `tests/` decide which.

---

## 1. Input and output

**Input:** one block of plain text, pasted by the user (5–100,000 characters; the
API refuses bodies larger than 400 kB). No URL is fetched.

**Output:** one *analysis* object, addressable by id, containing:

```
{
  "mode": "offline" | "llm",
  "created_at": ISO-8601 local timestamp,
  "source": {"chars", "sha256" (16 hex chars), "years" [ints], "default_year", "lines"},
  "raw":     <exactly what the reader proposed, unmodified>,
  "fields":  [ field, ... ],      # everything that survived validation
  "rejected":[ field, ... ],      # everything that did not
  "key_dates":[ field, ... ],     # the date fields, sorted by ISO instant
  "brief":   {...},               # convenience view: title, organizer, channel, lists
  "counts":  {"accepted", "corrected", "rejected", "missing"},
  "ungrounded_numbers": [ ... ],  # must always be empty; a self-check
  "events":  [ calendar event, ... ]
}
```

A **field** is:

```
{"id", "name", "label", "kind": "text"|"date"|"prize"|"list",
 "value",            # what the brief shows
 "evidence",         # the quote it rests on ("" when there is none)
 "span": [start, end] | null,   # offsets of that quote in the source text
 "verdict": "accepted"|"corrected"|"rejected"|"missing",
 "reason",           # one sentence, shown in the UI
 "raw_value",        # what the reader wrote, kept for the audit view
 ...kind-specific extras}
```

---

## 2. Readers

Both readers emit the same JSON shape:

```
{"title": {"value", "evidence"}, "organizer": {...},
 "submission_channel": {...}, "eligibility": {...},
 "key_dates": [{"label", "value", "evidence"}],
 "prizes":    [{"place", "amount", "currency", "evidence"}],
 "deliverables": [{"value", "evidence"}]}
```

* **offline reader** (`radar/offline.py`) — regular expressions only, no network.
  Splits the page into paragraphs (a line starting with a lowercase letter is a
  wrapped continuation of the line above), finds dates, money and the sentences
  that introduce the channel, eligibility and deliverables. It quotes the
  *clause* around each date so that one date gets one unambiguous quote.
* **language-model reader** (`radar/extract.py`) — one `/chat/completions` call
  to the OpenAI-compatible endpoint in `LLM_BASE_URL` with model `LLM_MODEL`,
  `temperature: 0`, and a system prompt that requires a verbatim quote per value
  and forbids arithmetic. The reply is parsed as JSON (fenced blocks are
  tolerated). An empty reply with `finish_reason=length` is retried once with a
  doubled token budget.

No reader result is ever shown to the user directly.

---

## 3. Validation rules

Applied per field, in this order.

**V1 — the quote must exist.** The evidence string is located in the source text
through three progressively looser searches: verbatim, ignoring letter case,
ignoring punctuation and spacing. The offsets returned are always into the
original text. If none of the three succeed, the field is **rejected**
(`the quoted evidence is not in the page ...`).

**V2 — numbers must exist.** Every numeric token in the value the reader wrote
must occur on the page as a standalone number (`26` does not match inside `2026`).
For dates and prizes a failure **rejects** the field; for free text the field is
**corrected** to the page's own wording and the reason names the invented number.

**V3 — dates are re-parsed.** `radar/dates.py` parses the value (or, if the value
is unparseable, the quote) and renders:

```
"value": "YYYY-MM-DD", "iso": "YYYY-MM-DDTHH:MM:SS±HH:MM",
"utc":  "YYYY-MM-DDTHH:MM:SSZ",
"zone": "America/New_York", "offset": "-04:00",
"precision": "minute" | "day", "year_inferred": bool
```

* When the quote is on the page but the value is not part of it, the quote's own
  date wins and the verdict is **corrected**
  (`the page states X; the model wrote Y -- the page wins`).
* When the quote contains several dates and the value is not one of them, the
  field is **rejected**: there is nothing to compare against.
* When the page gives a month and a day but no year anywhere, the field is
  **rejected**; nothing is calendared.
* When the page mentions exactly one year and the date omits it, that year is
  used and the field is marked `year_inferred`, with the reason saying so.

**V4 — prizes come from the quote.** The amount is parsed from the quoted page
text (`$5,000 USD`, `€2,500`, `3,000 dollars`, `5,000 元`). If the reader's amount
differs from the quote, the field is **rejected** and the reason shows both
numbers. If the quote has no amount (`mentorship and cloud credits`), the value
becomes `non-cash`. A place label the reader invented is replaced with
`Prize N` and the field is **corrected**.

**V5 — gaps.** An empty or missing field becomes
`value = "page does not state"` with verdict `missing`. A whole missing list
becomes one `missing` field with that name.

**V6 — the self-check.** After validation, every number in the surviving fields
is checked against the page once more; the result is reported as
`ungrounded_numbers`, which must be empty. It is displayed in the audit panel.

---

## 4. Calendar (.ics)

`radar/ics.py` writes RFC 5545:

* `BEGIN:VCALENDAR`, `VERSION:2.0`, `PRODID:-//Deadline Radar//Validated brief//EN`,
  `CALSCALE:GREGORIAN`, `METHOD:PUBLISH`;
* one `VEVENT` per **accepted** date field, only when a year is resolvable;
* a date with `precision: day` uses `DTSTART;VALUE=DATE` and a next-day `DTEND`;
  a timed date is converted to UTC and written as `DTSTART:YYYYMMDDTHHMMSSZ`;
* `UID` = first 20 hex chars of SHA-1(`deadline-radar|<field>|<iso>`) +
  `@deadline-radar.local`, so the same analysis produces the same UID every time;
* `DESCRIPTION` carries the ISO instant, the evidence quote and the verdict;
* `VALARM`s: the submission deadline gets `-P7D`, `-P1D`, `-PT2H`; every other
  event gets `-P1D`, `-PT2H`;
* lines are folded at 75 octets (UTF-8 safe), CRLF terminated, and `,`, `;`,
  `\` and newlines are escaped in text values.

Filename: `<slug of the title>-deadlines.ics`.

---

## 5. HTTP surface

| Method | Path | Behaviour |
|---|---|---|
| GET | `/` | the app; `?demo=N` renders guided-tour step N (server-rendered brief) |
| GET | `/analysis/<id>` | a stored analysis reopened |
| GET | `/ics/<id>` | the exact `.ics` bytes as a page, for inspection |
| GET | `/api/analysis/<id>` | `{id, result, source, ics}` |
| GET | `/api/analysis/<id>.ics` | `attachment; filename=...`, `text/calendar` |
| GET | `/api/history` | `{rows: [...], html: "..."}` |
| GET | `/api/demo` | the tour steps with their URLs |
| POST | `/api/analyse` | `{"text": ..., "mode": "offline"\|"llm"}` → `{id, html, counts, elapsed_ms, mode}` |
| GET | `/healthz` | `{ok, analyses, offline_default}` |
| GET | `/static/*` | css and js (path-traversal checked) |

Errors: 400 for bad JSON / empty text / `mode: llm` on an `--offline` server,
404 for unknown paths and ids, 413 for bodies over 400 kB, 502 with the exception
message when the model endpoint fails. Unhandled exceptions render a 500 page
with the traceback — never a silent success.

---

## 6. User interface

One page, rendered by Python (`radar/render.py`) and swapped in by
`static/app.js`:

1. **Composer** — textarea, reader selector, `Analyse` button, worked examples.
2. **Brief header** — title, reader badge, five counters, `Download .ics`.
3. **What the page says** — one block per text field with verdict, quote and reason.
4. **Key dates** — table: field · as written · normalised ISO (+ zone, precision,
   `year inferred`) · evidence with offsets · verdict and reason.
5. **Prize structure** and **Required deliverables** — same evidence discipline.
6. **Calendar** — the events the brief produces, with their reminders.
7. **Audit trail** — raw proposal JSON beside the validated brief JSON, then the
   rejected list, then the number cross-check.
8. **Source text** — the page with every evidence span highlighted in place.
9. **History** — local sqlite3 list; clicking an entry reopens it.

Guided-tour pages (`?demo=N`) add a step bar with prev/next links, shrink the
composer, and scroll the focused card into view; the page reports what it did in
`<body data-focus-ready=... data-metrics=...>`, which is how the video tool
verifies that each recorded frame really shows the intended state.

---

## 7. Command line

```
python3 app.py                      # serve on 127.0.0.1:8781
python3 app.py --offline            # never touch the network
python3 app.py --port 9000 --db /tmp/x.db
python3 app.py --analyse page.txt   # print the brief as JSON
python3 app.py --ics out.ics --analyse page.txt
python3 app.py --demo 6             # run a tour step, print the brief
python3 app.py --plan               # print the demo scenario as JSON
```

---

## 8. Determinism and privacy

* Same text + same reader ⇒ byte-identical brief and `.ics` (only `DTSTAMP`
  changes between seconds).
* The `.env` file is read from the project root; values already present in the
  environment win. The key is never written to the database, the page, the log or
  the repository.
* History lives in `deadline_radar.db` next to the app and is excluded from git.

---

## 9. Environment variables

| Name | Meaning |
|---|---|
| `LLM_BASE_URL` | base URL of an OpenAI-compatible API (no trailing slash needed) |
| `LLM_API_KEY` | bearer token for that API |
| `LLM_MODEL` | model name, e.g. `global:fast-model` |
| `PORT` | default port for `python3 app.py` (8781) |

With none of the `LLM_*` variables set, `app.py` starts normally and prints a
note; the LLM reader returns a clear error in the UI while the offline reader
keeps working.

---

## 10. Acceptance (end-to-end, no network)

1. `python3 app.py --offline`, open `/?demo=2` → a brief whose counters are
   `accepted 17, corrected 0, rejected 0, missing 0`, five key dates, three
   prizes, five deliverables.
2. `/?demo=6` → the fabricated `$50,000` appears in the rejected table with the
   reason that the quoted sentence is not on the page, and the wrong deadline is
   listed as corrected to `2026-10-26`, "the page wins".
3. `/?demo=7` → the deadline `10月26日 5:00pm ET` becomes
   `2026-10-26T17:00:00-04:00` with `year inferred`.
4. `/?demo=8` → the thin page yields `page does not state` for the prize amount,
   the eligibility and the deliverables.
5. `/ics/demo-a` → the calendar text, with three alarms on the deadline event.
6. Restart the app → the history list still shows the previous analyses.
7. `python3 -m unittest discover -s tests` → 85 tests, all passing, offline.
