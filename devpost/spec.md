---
doc: spec
status: draft
---

# Deadline Radar — Technical Spec

## How This Works, In Plain Language
There are three pieces, and they are deliberately different kinds of thing.

1. **A reader** turns the pasted page into a *proposal*: a small JSON object with
   the title, the key dates, the prize lines, the submission channel, the
   deliverables and the eligibility, each with the exact quote it came from. There
   are two readers — a deterministic one that uses no network, and an optional one
   that asks a language model — and they emit the same shape, so nothing downstream
   cares which one ran.
2. **The validator** is plain Python and has no model in it. It takes the proposal
   and the page text and decides, field by field, whether the proposal can be
   traced back to the page. It re-parses dates, reads prize amounts out of the
   quoted sentence, and gives every field one of four verdicts.
3. **The brief** is what the user sees: each field with its value, its verdict, its
   quote and the character offsets, plus an audit view that shows the raw proposal
   beside the validated one and lists what was rejected and why. From the brief
   come two exports — a calendar (`.ics`) and a self-contained HTML file — and every
   analysis is kept in a local `sqlite3` file.

Why this shape: a summariser that asks to be trusted cannot be checked. Splitting
"reading" from "deciding" means the deciding half can be tested offline, character
by character, and the half that can hallucinate is never the half that gets the
final word.

## The Core Journey Through the System
PRD ref: `prd.md > The Core Journey`.

- The user runs `python3 app.py --offline` → `app.py` starts the stdlib HTTP server
  (`radar/web.py`) with the offline reader selected, and the store points at the
  local `.db` file.
- They paste a page and press **Analyse** → the browser posts `{"text": …,
  "mode": "offline"}` to `/api/analyse` → `radar/web.py` hands the text to
  `radar/pipeline.analyse()`.
- `radar/pipeline.py` asks the chosen reader for a proposal — `radar/offline.py`
  (regex over paragraphs) or `radar/extract.py` (one call to the configured
  endpoint) — then hands proposal + source text to `radar/validate.py`.
- The validator walks each field: the quote is looked up in the page
  (`source.find`), dates go through `radar/dates.py`, money through
  `radar/money.py`, and each field comes back with a value, a verdict, the quote
  and `[start, end]` offsets.
- The validated brief is stored (`radar/store.py`, one row per analysis) and the
  HTML fragment for it is rendered server-side (`radar/render.py`) and returned to
  the page.
- The user reads the brief and the audit; the `.ics` comes from `radar/ics.py`
  (only accepted dates are written), and the downloadable brief comes from
  `radar/export.py` (one self-contained HTML document).
- Reopening an analysis from the history loads the same row and re-renders it, so
  the evidence highlighting still works days later.

## Stack
| Piece | Choice | Why |
|---|---|---|
| Language | Python **3.9 or newer** | available everywhere, no install step for the user |
| Web server | `http.server` (standard library) | the whole product is one local page; a framework would only add a dependency |
| Storage | `sqlite3` (standard library) | one file next to the app, no server, no schema migration step |
| Interface | hand-written HTML + CSS + one small JavaScript file | no build step, and the brief is rendered in Python so the screenshots are the real interface |
| Calendar | RFC 5545 text written by hand (`radar/ics.py`) | the format is small; a library would hide the one rule that matters (only accepted dates) |
| Optional model reader | any OpenAI-compatible endpoint over `urllib` | the entrant already has an endpoint; nothing new is bought or signed up for |

No third-party runtime dependency, no npm, no build step. Unverified nothing: the
whole path is exercised by the offline test suite.

## Where It Runs and How Someone Tries It
Runtime: a local Python process that serves one page on `127.0.0.1`.

```bash
git clone https://github.com/HanawaBanana/deadline-radar
cd deadline-radar
python3 app.py --offline          # open http://127.0.0.1:8781/
```

| Flag | What it does |
|---|---|
| `--offline` | deterministic reader only; no outbound request at all |
| `--port N` | a different port |
| `--db PATH` | where the history file lives (default `./deadline_radar.db`) |
| `--analyse page.txt` | print the validated brief as JSON |
| `--analyse page.txt --ics out.ics` | write the calendar |
| `--analyse page.txt --export out.html` | write the self-contained HTML brief |
| `--plan` | print the demo scenario as JSON |

Tests: `python3 -m unittest discover -s tests` — offline, no key, no network.
Recording: `python3 tools/make_video.py` walks the guided-tour URLs with headless
Chrome and assembles `docs/media/deadline_radar_demo.mp4` (needs Chrome, `ffmpeg`
and, for narration, `edge-tts`).

Submission requires a short demo video **and** a public repository; deployment is
optional and not chosen (see `prd.md > Non-Goals`). The env-var example
(`.env.example`) is secret-free.

## Look and Feel
Carried forward from `prd.md > Look and Feel`; implementable as it stands:
paper-like background (`#f7f5f1`-ish work area) and dark ink; one restrained accent
for links and the `Analyse` button; **verdict pills are the only saturated colour**
— accepted (green-ish), corrected (amber), rejected (red), not stated (grey, low
contrast on purpose). Display face for the title and field labels, quiet sans for
values and interface copy, monospace for quotes and offsets. Evidence quotes get
extra line height and a left rule, because they are meant to be read character by
character. Radius small, shadows absent, borders hairline. Motion: only the work
area swapping in; no spinner theatre. The stack can honour all of this — the CSS is
static, `static/style.css`, with no framework resetting it.

## Components

### The offline reader — `radar/offline.py`
Deterministic extraction with no network: paragraph-splitting plus regexes for
dates, money and requirement sentences, plus the deliverable/channel/eligibility
line heuristics. Emits the same proposal shape as the model reader.
PRD ref: `prd.md > Reading a page`.

### The model reader — `radar/extract.py`
Reads `.env` / environment for `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` and makes
one `urllib` call to an OpenAI-compatible endpoint, asking for a quoted proposal.
Returns a structured error when the configuration is missing so the interface can
say so. The key is never written to code, the repository or the logs.
PRD ref: `prd.md > Reading a page`.

### The validator — `radar/validate.py`
Turns a proposal into a validated brief: quote lookup, number check, date and money
delegation, verdict assignment, counters, and the list of rejections with reasons.
PRD ref: `prd.md > Validating every value`, `prd.md > The audit view`.

### Date and money parsing — `radar/dates.py`, `radar/money.py`
`dates.py` parses the date/time formats the pages actually use (including
`10月26日 5:00pm ET` with no year) and renders ISO 8601 with a zone, flagging an
inferred year. `money.py` parses prize strings into an amount, a currency and the
raw text.
PRD ref: `prd.md > Validating every value`.

### The brief and audit renderer — `radar/render.py`
Server-side HTML for the brief, the evidence spans, the audit view, the history
list and the guided tour bar. The browser never assembles the brief, so a
screenshot and a user see the same markup.
PRD ref: `prd.md > The brief and its evidence trail`, `prd.md > The audit view`.

### The self-contained brief — `radar/export.py`
Builds one HTML document from a stored record: inline styles, no external
stylesheet, script or image reference, all page-derived text escaped, containing
the fields with verdicts and quotes, the audit, the `.ics` text, the source hash
and the production time.
PRD ref: `prd.md > The self-contained HTML brief`.

### The calendar writer — `radar/ics.py`
RFC 5545 output. Only dates the validator accepted become events; reminders are
written as `VALARM` blocks.
PRD ref: `prd.md > The calendar export (.ics)`.

### The store — `radar/store.py`
`sqlite3` history: one row per analysis, including the source text so evidence
highlighting survives.
PRD ref: `prd.md > History`.

### The pipeline — `radar/pipeline.py`
The single path from page text to a stored, validated brief, used by both the HTTP
handler and the command line, so the audit trail cannot differ between them.

### The HTTP layer — `radar/web.py`
A stdlib `http.server` with the routes below; it moves bytes and nothing else.

| Route | Purpose |
|---|---|
| `GET /` | the app, or a guided-tour step with `?demo=N` |
| `GET /analysis/<id>` | a saved analysis, reopened |
| `GET /ics/<id>` | the calendar as a readable page |
| `GET /api/analysis/<id>` | the analysis as JSON |
| `GET /api/analysis/<id>.ics` | the calendar as a download |
| `GET /api/analysis/<id>.html` | the self-contained brief as a download |
| `GET /api/history` | JSON + rendered HTML for the history list |
| `GET /api/demo` | the guided tour as JSON |
| `POST /api/analyse` | `{"text": …, "mode": "offline"|"llm"}` |
| `GET /static/<file>` | CSS and JavaScript |
| `GET /healthz` | health probe |

### The command line — `app.py`
Argument parsing, the `--offline` default, port/db selection, and the
`--analyse` / `--ics` / `--export` / `--plan` one-shot modes.

### The guided tour — `radar/demo.py` and `tools/make_video.py`
`demo.py` holds the scripted scenario as one observable state per URL
(`/?demo=0` … `/?demo=12`, `/ics/demo-a`), including an injected hallucination for
the audit step. `tools/make_video.py` screenshots those URLs with headless Chrome,
writes narration with `edge-tts` when present and assembles the video with
`ffmpeg`, so the recording is reproducible and shows the real interface.

## Data Model
One table, one row per analysis (`radar/store.py`):

| Column | Contents |
|---|---|
| `id` | 12-hex id, the address of the analysis in the UI |
| `created_at` | ISO timestamp produced during the run |
| `title` | the page title the reader proposed, truncated to 80 characters |
| `mode` | `offline` or `llm` |
| `source_text` | the pasted page, kept so evidence offsets still resolve later |
| `source_hash` | SHA-256 of the source text |
| `result_json` | the whole validated brief: fields, verdicts, quotes, offsets, counters, rejections |

State that persists: the history rows. State that does not: the proposal itself is
kept inside `result_json` for the audit view, but nothing is recomputed on reopen —
a stored analysis always renders exactly as it was validated.

## File Structure
```
deadline-radar/
├── app.py                     # command line entry: --offline/--analyse/--ics/--export/--plan
├── radar/
│   ├── offline.py             # deterministic reader (no network)
│   ├── extract.py             # .env + OpenAI-compatible model reader
│   ├── validate.py            # the validator: proposal -> validated brief
│   ├── dates.py               # date/time normalisation (ISO 8601 + zone)
│   ├── money.py               # prize string parsing
│   ├── ics.py                 # RFC 5545 calendar, accepted dates only
│   ├── export.py              # one self-contained HTML brief
│   ├── render.py              # server-side HTML for brief, audit, history, tour
│   ├── store.py               # sqlite3 history, one row per analysis
│   ├── pipeline.py            # text -> proposal -> validated -> stored
│   ├── web.py                 # stdlib http.server and the routes above
│   └── demo.py                # the guided tour, one state per URL
├── static/                    # style.css, app.js (no build step)
├── templates/index.html       # the single page
├── samples/                   # three worked pages the user can open
├── tests/                     # offline unit tests (unittest)
├── tools/make_video.py        # reproducible demo recording
├── docs/media/                # the rendered demo video and its thumbnail
├── devpost/                   # Devpost Learn Skill Pack workspace
│   ├── scope.md  prd.md  spec.md
│   ├── checklist.md           # build slices and their verification
│   └── app-map.html           # take-home map of the code
└── README.md  LICENSE  .env.example
```

## External Services and Dependencies
- **None required.** The offline reader, the validator, the exports, the history
  and the interface are all standard library.
- **Optional** model reader: any OpenAI-compatible endpoint. Configuration comes
  from the environment or a git-ignored `.env`
  (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`); `.env.example` documents the shape
  with no real values. Exact call: one `POST` to `<LLM_BASE_URL>/chat/completions`
  with the page text and a quoting instruction, expecting a JSON object back.
- **Nothing else**: no analytics, no CDN, no fonts fetched at runtime, no account.

## Failure Modes
| Failure | What the user sees | Why that is right |
|---|---|---|
| Model endpoint not configured | an explicit note in the work area; the offline reader still runs | the tool is never blocked by a service |
| Model returns a fabricated number | the field is **rejected** and its reason is printed beside it | the page wins over the model, in public |
| No year on the page (`10月26日 5:00pm ET`) | the date is rendered with a zone and labelled **corrected** | an inferred value must be visible as inferred |
| A page with nothing recognisable | `page does not state` per field, verdict **not stated** | a gap is information; an invented value is not |
| Empty input | a prompt for text; no history row is written | nothing to store |
| Body over 400 000 characters | the request is refused, not truncated | silent truncation would invalidate the quotes |
| Unknown analysis id | HTTP 404 | never a blank brief that looks like a result |
| Unreadable/absent history file | a new empty `sqlite3` file is created on first run | losing history must not break the tool |
| `edge-tts` missing while rebuilding the video | the video is built without narration, and the tool says so | the video is a build artifact, not the product |

## Validation rules
The exact behaviour of `radar/validate.py`, in the order it runs:

1. **Title** — accepted if the quoted text appears in the page, else `not stated`.
2. **Dates** — the quote must exist; the value is re-parsed by `radar/dates.py` and
   re-rendered as ISO 8601 with a zone. If the parsed value differs from what the
   proposal claimed, the field is **corrected** (the page's own text wins). A date
   that cannot be parsed from the quote is **rejected**.
3. **Money** — the amount is parsed from the *quoted sentence*, never summed or
   computed. Any value containing a number that does not appear in the page text is
   **rejected**, and the reason names both numbers
   (`the model claims $50,000 USD but the quoted page text says $5,000 USD`).
4. **Text fields** (submission channel, deliverables, eligibility) — the quote must
   exist in the page; otherwise the field is `not stated`.
5. **Counters** — the brief carries how many fields were `accepted`, `corrected`,
   `rejected` and `not stated`; the audit view lists every rejection with its
   reason.
6. **Offsets** — every accepted or corrected field carries `[start, end]` character
   offsets into the pasted text, which is what the source view highlights.
7. **Calendar** — `radar/ics.py` writes events only for dates that survived rules
   2 and 3.

## Verification
- **Unit tests**: `python3 -m unittest discover -s tests` — the whole deterministic
  path, no network and no key: date normalisation (including the no-year Chinese
  case and US daylight-saving boundaries), prize parsing, the `page does not state`
  fallback, rejection of values that are not in the source, `.ics` generation, the
  self-contained HTML export, the `sqlite3` history, and the HTTP endpoints
  (including the two download routes and their 404s).
- **End-to-end without a browser**: `python3 app.py --analyse samples/thin_announcement.txt`
  and the same command with `--ics` and `--export`.
- **Reproducible visual check**: the guided-tour URLs render the same states the
  demo video captures; `python3 tools/make_video.py` rebuilds the video from them.

## Decisions and Open Issues
- **Reject rather than correct a number** — decided; silently fixing a value would
  make the audit untrustworthy (`prd.md > Product Decisions`).
- **Year inference is allowed but must be labelled** — decided; the alternative
  (refusing the date) loses the most important field on real pages.
- **Export as a single HTML file with inline styles** — decided during this build
  pass: it keeps the "evidence you can keep" promise working with the app closed.
  The route mirrors the existing `.ics` attachment route
  (`/api/analysis/<id>.html`).
- **Open**: whether the model reader's prompt should be user-editable — can wait;
  the offline reader is the tested path.
- **Open**: whether a *rejected* value should be offered in its corrected form —
  currently the reason is shown and the value is dropped, which the entrant chose.
