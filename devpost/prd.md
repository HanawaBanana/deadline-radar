---
doc: prd
status: draft
---

# Deadline Radar — Product Requirements

A single-user web app that turns the text of an announcement into a validated
brief — every value quoted and judged, or reported as not stated — and a calendar
that contains only what the validator accepted.
Source: `scope.md > The Unique Kernel`, `scope.md > The POC Boundary`.

## The Core Journey
1. The user runs `python3 app.py --offline` and opens `http://127.0.0.1:8781/`.
   There is one page: a paste box, a reader selector, an **Analyse** button, a work
   area for the brief, and a history list.
2. They paste the text of an announcement — a competition page, a call for
   entries, a set of rules — or open one of the worked examples.
3. They choose the reader: **offline** (deterministic, no network) or **language
   model + validator** (only if an endpoint is configured).
4. They press **Analyse**. The reader proposes values; the validator decides which
   are true and shows its work.
5. They read the brief: key dates as written → ISO 8601 with a time zone, prize
   structure, submission channel, required deliverables, eligibility — each field
   carrying its value, its verdict, the quoted characters and the offsets.
6. They open the audit: the raw machine proposal beside the validated brief, with
   rejected fields listed and the reason shown in plain language.
7. They download the `.ics` (three reminders on the deadline) and, if they want the
   evidence outside the app, the **self-contained HTML brief**.
8. The analysis is stored locally; reopening it from the history restores the same
   brief, the same evidence and the same verdicts.

Success = step 5 to 8 happen on a real page without the user trusting a summary:
they can point at any value and see the characters it came from.

## Screens and Layout
One screen, top to bottom:

| Band | What is there |
|---|---|
| Composer | the paste box, the reader selector, **Analyse**, and the worked examples |
| Brief head | title, source hash, counters — `accepted` / `corrected` / `rejected` / `not stated` — and the download links (`.ics`, `.html`) |
| Brief body | one row per field: label, value, verdict pill, the quoted evidence and its character offsets |
| Audit | raw proposal beside the validated brief, plus the list of rejected values with reasons |
| Source | the pasted text with every accepted evidence span highlighted |
| History | recent analyses (time, title, mode, counters); clicking one reopens it |

The guided tour (`/?demo=0` … `/?demo=12`, and `/ics/demo-a`) renders these same
states one URL at a time; that is how the demo video is captured, so what the video
shows is the real interface.

## Look and Feel
A printed brief with a margin full of notes. Light, editorial, low saturation —
paper-like background, one restrained accent, verdict pills as the only colour
signal (accepted / corrected / rejected / not stated). Serif-ish display for the
title and the field labels, quiet sans for values; generous line height on the
evidence quotes because they are meant to be read character by character. Nothing
animated except the work area swapping in. Interface copy is plain: no "AI magic",
no confidence theatre — `page does not state` is printed as it is.

## Features and Behavior

### Reading a page
Two readers emit the same JSON shape, so the pipeline does not care which ran.
- **offline** — deterministic regular expressions over paragraphs: dates, money,
  requirement sentences. No network, always available.
- **language model** — one call to an OpenAI-compatible endpoint; the reader must
  quote the page for every value it proposes.
- As a solo entrant with a page open in another tab, I want the analysis to work
  with no key and no network so that the tool is never blocked by a service.
  - [ ] `--offline` produces a full brief with no outbound request.
  - [ ] With no endpoint configured, choosing the model reader explains the missing
        configuration instead of failing silently.

### Validating every value
The product is the validator.
- [ ] Every quote proposed must exist in the pasted text; otherwise the field is
      **rejected** with the reason.
- [ ] A value containing a number that is not on the page is rejected — never
      silently corrected.
- [ ] Dates are re-parsed in plain Python and re-rendered as ISO 8601 with a time
      zone; a date inferred rather than stated is labelled **corrected**.
- [ ] Prize amounts are read out of the quoted sentence, not computed.
- [ ] A field the page does not state becomes the literal string
      `page does not state`, with verdict **not stated**.
- [ ] Each accepted field carries the exact quoted characters and their offsets.

### The brief and its evidence trail
One row per field: what the page says, how the code judged it, where it came from.
The user can audit any value in the brief without leaving the page.

### The audit view
The raw machine proposal is rendered next to the validated brief, and rejected
values are listed with their reason, so the tool shows what it threw away.

### The calendar export (`.ics`)
- [ ] The `.ics` contains only events whose dates the validator accepted.
- [ ] Each date carries reminders before the deadline.
- [ ] The file opens in a normal calendar application.

### The self-contained HTML brief
As an entrant who wants to keep the evidence, I want to download the brief as one
file so that I can read or share it with the app closed.
- [ ] A download is offered next to the `.ics` link and also from the command line
      (`--export out.html`).
- [ ] The file is a single document — inline styles, no external stylesheet,
      script or image reference — so it renders offline.
- [ ] It shows the same values, verdicts, quotes, offsets and the audit, and it
      states the source hash and the time it was produced.

### History
- [ ] Every analysis is stored locally (one row per run) with its source text.
- [ ] Reopening an analysis from the history restores the brief, the evidence
      highlighting and the verdicts.
- [ ] Nothing leaves the machine: no account, no upload, no telemetry.

## States and Boundaries
- **First use** — empty brief: the work area says to paste a page or open a worked
      example. History may be empty.
- **Empty input** — pressing Analyse with nothing pasted asks for text; no analysis
      row is written.
- **Thin page** — a page with no recognisable values yields `page does not state`
      for the fields, not invented content.
- **Model reader unavailable** — an explicit note in the work area; the offline
      reader still works.
- **Very long page** — the request body is capped (400 000 characters); beyond that
      the server refuses the request rather than truncating silently.
- **Unknown analysis id** — a 404, never a blank brief.
- **Persistence** — history lives in a single `sqlite3` file next to the app
      (git-ignored); deleting the file loses the history and nothing else.
- **Privacy boundary** — offline mode makes no outbound request at all; model mode
      sends the page text to the endpoint the user configured, then validates
      locally.

## Product Decisions
- **The page wins over the model** — a mismatch is reported as *corrected* (or
  *rejected* when a number is not on the page) instead of being quietly fixed; the
  audit is worthless if the tool edits its own evidence.
- **Prize amounts are read from the quoted sentence, never computed** — summing a
  prize table invents a figure the page never stated.
- **Two readers, one validator** — keeps the deterministic path testable offline
  and makes the model reader optional rather than load-bearing.
- **Local history instead of accounts** — a single user with a deadline does not
  need a login; `sqlite3` is in the standard library.
- **The `.ics` may be empty of a date the validator rejected** — a calendar with a
  wrong reminder is worse than a shorter calendar.
- **The HTML brief is one file with inline styles** — "evidence you can keep" only
  works if the file still renders with the app closed and offline.

## What We're Building
The complete proof of concept: two readers, the validator with four verdicts and
character offsets, the brief and its audit view, `.ics` export, the self-contained
HTML brief export, local history, one page of interface, the guided tour used for
the demo video, and the offline test suite. Python standard library only.

## Deferred From the POC
- An account system behind "keep my analyses" — local `sqlite3` covers one user.
- Sharing a brief with a second person — no second person in this loop yet.
- Reading several pages in one run — the pipeline is per page by design.
- Deployment to a public URL — the video and the repository are the deliverables;
  hosting adds secrets management with no judging benefit.

## Possible Later Enhancements
A watchlist of followed calls with a per-call status column. Markdown/JSON export
next to the HTML brief. More languages in the offline reader (the date grammar is
the constraint). Optional PDF text extraction as an *input*, not as a reader.

## Non-Goals
- Generating or writing the submission itself — the tool briefs, the entrant
  submits.
- Automatically fetching or monitoring the source sites — reliability and legal
  surface are out of scope; the user pastes the page.
- Guaranteeing that a value is *correct* — the guarantee is narrower and honest:
  it is traceable to the page, or it is reported as not stated.

## Open Questions
- Whether the model reader's prompt should be exposed for editing — deferred; the
  offline reader is the default and the testable path.
- Whether a rejected-but-close value should suggest the corrected form — currently
  the reason is shown and the value is dropped, which the entrant preferred.
