---
doc: scope
status: draft
---

# Deadline Radar

Paste an announcement page, get a brief where every value carries its own quote —
or says it is not stated — plus a calendar that contains nothing else.

## The Unique Kernel
The language model is allowed to *read*; it is never allowed to decide. Every value
a reader proposes is re-checked against the pasted page by deterministic Python:
the quote must really exist in the text, every number must be on the page, dates
are re-parsed and re-rendered, prize amounts are read out of the quoted sentence
rather than computed, and the verdict — **accepted / corrected / rejected / not
stated** — is published next to the evidence. Delete that and what is left is one
more summariser asking to be trusted.

## Who It's For
One solo entrant working through calls for entries: a designer/freelancer who has
to pull the deadline, the prize structure, the submission channel and the required
deliverables out of prose written for lawyers — and then retype the deadline into a
calendar. What they do today: read the page twice, copy the numbers by hand, and
occasionally work against a date they misread.

## The Core Loop
Open the app → paste the text of the announcement → press **Analyse** → read the
brief, where each field shows its value, its verdict and the exact quoted
characters plus offsets it came from → download the `.ics` (and the self-contained
HTML brief) → the analysis stays in a local history, so an old page can be reopened
days later with its evidence intact.

## Inspiration & Identity
A printed brief with a margin full of notes — not a chat window. Evidence forward:
the raw machine proposal sits beside the validated brief, rejected fields are
listed with a reason, and a gap is printed as `page does not state` instead of
being dressed up. Restrained editorial palette, the verdict pills are the only
colour, typography does the work. Interface copy is plain and non-promotional:
nothing claims certainty the code did not check.

## Why This Matters to the Learner
It comes straight out of the entrant's own week: five or six open calls at once,
each with a different date format and a prize table buried in a paragraph. A
misread date costs an entry; a guessed number costs trust in the tool.

## What "Working" Looks Like
Paste a real rules page: the brief lists **17 values accepted, 0 rejected**; the
raw proposal's invented `$50,000 USD` is visible beside a rejected field with its
reason (`the model claims $50,000 USD but the quoted page text says $5,000 USD`);
`10月26日 5:00pm ET`, which carries no year on the page, comes back as
`2026-10-26T17:00:00-04:00` and labelled *corrected*; a thin page answers
`page does not state` three times instead of inventing values; the `.ics` opens in
a calendar with three reminders on the deadline; and the **downloaded HTML brief
still shows every quote after the app is closed**.

## The POC Boundary
In: an offline deterministic reader; an optional model reader over an
OpenAI-compatible endpoint; the validator with four verdicts, quotes and character
offsets; the brief and its audit view; `.ics` export; a self-contained HTML brief
export; sqlite history; one page of interface; Python standard library only.

## Later
Worth doing, not now: analysing several pages at once; a watchlist of followed
calls; more languages; Markdown/JSON export for the brief.

## Explicitly Cut
- **Accounts, teams, sharing** — nothing here needs a second person; a login would
  add a credential surface for zero product value.
- **PDF / image / OCR input** — the readers work on pasted text; layout parsing is
  a different project with different failure modes.
- **Notifications and email reminders** — the `.ics` already lands in the
  entrant's own calendar; standing infrastructure is out of a two-to-four-hour
  proof of concept.
- **Hosted deployment** — the video and the public repository are what judges
  consume; a public URL would only add secrets management to a POC.
- **Fetching or automating the source sites** — reliably reading other people's
  pages is a legal and maintenance problem, not a feature.
