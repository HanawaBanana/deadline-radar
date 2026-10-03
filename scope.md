# scope.md — Deadline Radar

Written during the planning interview, before any code. It is the document that
answers "what is this, who is it for, and what is it deliberately not".

## The problem

Opportunity announcements are written for humans to skim and for lawyers to
defend. They are prose: dates in three formats, a prize table as a paragraph, a
submission channel mentioned once in the middle, deliverables scattered across
two sections, and time zones implied rather than stated.

Automating the reading is the easy half. A language model will happily produce a
clean-looking summary — including, occasionally, a deadline that was never on the
page, a rounded prize amount, or an eligibility rule borrowed from a similar
competition. That is worse than no automation, because the output *looks* like
data. A wrong deadline is not a formatting problem; it is a missed submission.

So the interesting problem is not extraction. It is **trust**: how does the person
acting on the brief know that the number in front of them came from the page?

## Who it is for

A single person tracking competitions, grants and calls for entries on their own:

* they read 10–40 pages a week and act on two or three;
* they care about four things (when it closes, what it pays, where to send it,
  what must be in the submission);
* they will not maintain a database, sign up for a service, or trust a summary
  they cannot check;
* when the app is unsure, they want to be told, not guessed at.

## Scope

In scope:

* paste plain text from any announcement page (no scraper, no browser extension);
* extract: event, organiser, key dates, prize structure, submission channel,
  required deliverables, eligibility;
* **validate every extracted value against the pasted text** and record what
  happened to it: accepted, corrected, rejected, or "page does not state";
* show the evidence span and its character offsets for each surviving field;
* show the raw machine proposal next to the validated brief, so the difference is
  visible rather than claimed;
* export the validated dates as an `.ics` calendar with reminders;
* keep a local history of analyses in sqlite3;
* work with no network at all, and with no third-party account.

Out of scope (non-goals):

* **no fetching.** The user pastes text. Deadline Radar never crawls a URL, so it
  can never be blamed for reading a stale or different page than the one the user
  saw.
* **no accounts, no server, no cloud.** One process on one machine, standard
  library only.
* **no notifications.** The calendar file does that, in whatever calendar app the
  user already uses.
* **no multi-user, no sharing, no collaboration.**
* **no PDF or image input** in this version.
* **no paid API.** The optional language-model reader talks to a single
  OpenAI-compatible endpoint configured through the environment; if it is not
  configured, the offline reader runs instead.
* **no inference about what the text means.** If the page does not state the
  eligibility, the brief says "page does not state". That is the product, not a
  shortcoming.

## Product principles (used to settle every later decision)

1. **The page is the source of truth.** Not the model, not the parser, not the
   developer's intuition. Every value carries a quote, and the quote is checked.
2. **Deterministic code owns arithmetic.** Dates, time zones, ISO rendering and
   money parsing are plain Python and unit tested; the reader supplies strings.
3. **Show the failure.** A rejection with a reason is a feature. Hiding it would
   make the brief look cleaner and be less true.
4. **No silent gaps.** Absent fields become the literal string
   `page does not state`.
5. **Zero friction is part of correctness.** If it needs `pip install`, it will
   not be run six months later.

## Success criteria

* A pasted page produces a brief with every field either grounded in a quote or
  explicitly marked as not stated.
* A proposal containing an invented number is rejected, visibly, with the reason.
* The calendar file contains only dates that survived validation.
* The whole thing runs from a clean checkout with `python3 app.py`, offline, with
  no dependencies.
* The behaviour above is covered by unit tests that never touch the network.
