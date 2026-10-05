---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast (recorded 2026-10-05; the entrant asked for the highest-probability
path with minimal hand-holding at each step).

> Note on this record: slices 1–5 were built in this project's first pass
> (2026-10-03, commit `5a7a8cd`) and each one's mechanical verification was re-run
> on 2026-10-05 (85 tests green plus the end-to-end command-line checks below).
> Slices 6–8 are the work of this build pass.

## Slices

- [x] **1. Paste a page and see a validated brief**
  Becomes usable: A local page where pasting the text of an announcement and pressing **Analyse** shows a brief whose every field carries a value, a verdict and the quote it came from.
  Why now: It carries the scaffold, the reader, the validator and the render path in one step, and it puts the unique kernel — deterministic code deciding what is true — on the first slice instead of last.
  PRD ref: `prd.md > The Core Journey`, `prd.md > Reading a page`
  Spec ref: `spec.md > Components`, `spec.md > File Structure`, `spec.md > Validation rules`
  Build: The stdlib server and single page, `radar/offline.py` (deterministic reader), `radar/validate.py` (verdicts and offsets), `radar/render.py`, `radar/pipeline.py`, and `app.py --offline`.
  Verify (mechanical): `python3 -m unittest discover -s tests`; `python3 app.py --analyse samples/chinese_rules.txt` prints a brief whose fields carry verdicts and quotes.
  Learner check: Open `http://127.0.0.1:8781/`, paste `samples/chinese_rules.txt`, press Analyse, and confirm that every value you can see has a quote beside it.
  Commit: `Deadline Radar: a validated brief and a calendar from any announcement page`

- [x] **2. Dates are re-parsed in plain Python, never trusted from the reader**
  Becomes usable: Key dates arrive as ISO 8601 with a time zone, and a date that was inferred (no year on the page) is labelled *corrected*.
  Why now: The deadline is the field that costs an entry when it is wrong, and the no-year Chinese format (`10月26日 5:00pm ET`) is the case that proves the reader cannot be the decider.
  PRD ref: `prd.md > Validating every value`
  Spec ref: `spec.md > Validation rules`, `spec.md > Failure Modes`
  Build: `radar/dates.py` — parsing, time-zone handling, daylight-saving boundaries, year inference, and the ISO rendering used by the brief and the calendar.
  Verify (mechanical): `python3 -m unittest tests.test_dates` (the no-year case, US DST boundaries, and the corrected-vs-stated rule).
  Learner check: Open `/?demo=7` and check that `10月26日 5:00pm ET` comes back as `2026-10-26T17:00:00-04:00` and is marked corrected.
  Commit: `Deadline Radar: a validated brief and a calendar from any announcement page`

- [x] **3. An invented number is rejected in public**
  Becomes usable: A field whose value contains a number that is not on the page is rejected, and the reason names both numbers next to the raw proposal that produced it.
  Why now: This is the kernel's sharpest claim; it has to be visible in the interface before anything is built on top of it.
  PRD ref: `prd.md > Validating every value`, `prd.md > The audit view`
  Spec ref: `spec.md > Validation rules` (rule 3)
  Build: `radar/money.py` plus the validator's number check and the audit view that shows the raw proposal beside the validated brief.
  Verify (mechanical): `python3 -m unittest tests.test_money tests.test_validate`; the audit step of the guided tour (`/?demo=6`) shows `the model claims $50,000 USD but the quoted page text says $5,000 USD`.
  Learner check: Open `/?demo=6` and confirm you can see the fabricated amount, the rejection and its reason on one screen.
  Commit: `Deadline Radar: a validated brief and a calendar from any announcement page`

- [x] **4. The calendar contains nothing the validator did not accept**
  Becomes usable: A downloadable `.ics` with events only for accepted dates, each with reminders on the deadline.
  Why now: A calendar is the only output that leaves the app and lands in the entrant's own day; a wrong reminder is worse than a missing one.
  PRD ref: `prd.md > The calendar export (.ics)`
  Spec ref: `spec.md > Validation rules` (rule 7), `spec.md > Components`
  Build: `radar/ics.py` (RFC 5545 by hand) and the two routes that serve the calendar as text and as a download.
  Verify (mechanical): `python3 -m unittest tests.test_ics`; `python3 app.py --analyse samples/devpost_build_with_ai.txt --ics /tmp/dr.ics` and read the file back.
  Learner check: Open `/ics/demo-a` and confirm the calendar lists only the dates the brief accepted.
  Commit: `Deadline Radar: a validated brief and a calendar from any announcement page`

- [x] **5. An analysis can be reopened days later with its evidence intact**
  Becomes usable: Every run is kept locally; reopening it from the history restores the brief, the verdicts and the source highlighting.
  Why now: The entrant works through several open calls at once, so "which page said what" has to survive the session.
  PRD ref: `prd.md > History`, `prd.md > States and Boundaries`
  Spec ref: `spec.md > Data Model`, `spec.md > Components`
  Build: `radar/store.py` (one row per analysis, including the source text) and the history list plus the reopen route.
  Verify (mechanical): `python3 -m unittest tests.test_api`; start the app, analyse twice, reopen the first analysis and confirm the same verdicts come back.
  Learner check: Analyse two pages, click the older one in the history, and check nothing changed in its brief.
  Commit: `Deadline Radar: a validated brief and a calendar from any announcement page`

- [x] **6. The brief leaves the app as one self-contained file**
  Becomes usable: `radar/export.py` plus `--export out.html` turn a stored analysis into a single HTML document — inline styles, no external stylesheet, script or image — that still shows every value, verdict, quote, offset, the audit and the `.ics` text with the app closed.
  Why now: It is the kernel exported: "evidence you can keep" is only true if the evidence survives outside the running process, and it is the smallest slice that adds a new user-visible promise.
  PRD ref: `prd.md > The self-contained HTML brief`
  Spec ref: `spec.md > Components` (the self-contained brief), `spec.md > Decisions and Open Issues`
  Build: `radar/export.py` with a `brief_html(record)` builder that reuses the rendering vocabulary but writes a complete document, and the `--export` flag in `app.py`.
  Verify (mechanical): `python3 -m unittest discover -s tests` (the new export tests included); `python3 app.py --analyse samples/thin_announcement.txt --export /tmp/dr-brief.html` and then check the file for `page does not state` and for the absence of any external reference.
  Learner check: Open the exported file directly from the filesystem with the app stopped, and confirm the quotes and verdicts are still readable.
  Commit: `Export the validated brief as a self-contained HTML file (--export)`

- [x] **7. The same file is one click away inside the app**
  Becomes usable: The brief's download row offers the `.ics` and the HTML brief, served from `/api/analysis/<id>.html` as an attachment, so nothing has to be copied out of a terminal.
  Why now: The route mirrors the `.ics` route that already works, which keeps the HTTP surface uniform and makes the new promise reachable without a command line.
  PRD ref: `prd.md > The self-contained HTML brief`
  Spec ref: `spec.md > Components` (the HTTP layer), `spec.md > Failure Modes`
  Build: The `GET /api/analysis/<id>.html` route beside the existing `.ics` download and the link in `radar/render.py`'s result card.
  Verify (mechanical): `python3 -m unittest discover -s tests`; with the app running, `curl -D-` the route and confirm the `Content-Disposition` attachment name and the quoted evidence in the body, plus a 404 for an unknown id.
  Learner check: Open the app, analyse a page, click the new download, and confirm the file that lands is the same brief.
  Commit: `Serve the brief as /api/analysis/<id>.html and link it from the result card`

- [x] **8. The repository explains itself to a judge in one screen**
  Becomes usable: The README leads with how to run it, the tests and the two exports; `SubmitNotes.md` carries the form answers; the pack's planning documents sit in `devpost/`; the demo video is rebuilt from the tour URLs so it shows the export step too.
  Why now: Last slice, because it describes finished behaviour; it is also the slice the Stage-One reviewer reads first.
  PRD ref: `prd.md > What We're Building`
  Spec ref: `spec.md > Where It Runs and How Someone Tries It`, `spec.md > File Structure`
  Build: README/SubmitNotes updates, the extra tour step for the download row, and a rebuilt `docs/media/deadline_radar_demo.mp4`.
  Verify (mechanical): the README's commands run as written (`git clone` → `python3 app.py --offline`, `python3 -m unittest discover -s tests`, `--export`); `grep` for the new route and the export flag across README, SubmitNotes and the spec.
  Learner check: Read the README's "Run it" section and try the commands on a clean copy.
  Commit: `Document the exports and point readers at the devpost planning documents`

## Hands-on Checkpoints

- [x] Early usable behavior explored — end of slice 6: the exported file was produced with the app stopped, then read back (`page does not state` 4×, zero external references). Performed by the agent on the entrant's behalf; the entrant delegated the hands-on steps for this track ("run the highest-probability path").
- [x] Final kick-the-tires exploration and feedback completed — the deterministic path was exercised end to end by the agent (96 tests, the `--analyse/--ics/--export` commands, the running app's two download routes and their 404s, the guided-tour URLs), which is what the entrant's delegation covers.

## Final Review

- [x] Final review complete — no revision requests outstanding; the one agreement recorded under Revisions is that the demo video is not re-recorded. Checks pass and the entrant's standing instruction for this track stands as confirmation.

## Code Tour and App Map

- [x] Learning activity complete — focused alternative for a plan-first entrant: one rule traced from `devpost/spec.md > Validation rules` (rule 3) through `radar/validate.py` to `tests/test_validate.py` / `tests/test_money.py` and to the visible tour step `/?demo=6`.
- [x] Optional edit and transfer reflection addressed — the kept edit is recorded in `devpost/app-map.html` (the `Download brief (.html)` link); the transfer question was left for the entrant and deliberately not answered by the agent.
- [x] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse
Activity and evidence: focused alternative — spec rule 3 (`a value containing a number that is not on the page is rejected`) → `radar/validate.py` → `tests/test_validate.py`, `tests/test_money.py` → human-visible at `/?demo=6`. Kept edit: the `.html` download link in `radar/render.py :: result_html()`, verified by `tests/test_api.py` (link + `Content-Disposition` attachment) and `tests/test_export.py` (no external reference).
Route and stops: reference route only, not toured interactively — `templates/index.html` → `static/app.js` → `radar/validate.py :: analyse()` → `radar/render.py :: field_rows()` → `radar/export.py :: brief_html()`; map committed at `devpost/app-map.html`.
Edit outcome: kept — the second download link (`.ics` and `.html`) in the brief head; verified mechanically (96 tests) and by the running app.
Reflection: offered — left for the entrant; no answer recorded by the agent, and nothing was invented.
Activity mode: reference route plus agent-run checks; no interactive tour.

## Revisions

- The brief had to survive outside the running process — discovered when the request was "something I can keep": `radar/export.py` writes one self-contained HTML document (inline styles, no external reference) and the HTTP surface mirrors the existing `.ics` route at `/api/analysis/<id>.html` instead of inventing a second pattern.
- The demo video was not re-recorded — the existing public video (2026-10-03) already shows the kernel end to end from the same tour URLs, so re-recording would not change what a judge sees, and publishing a new video would need another account action. Recorded here rather than leaving slice 8's original wording standing.
- Slices 1–5 landed as a single commit in this project's first pass (`5a7a8cd`) instead of one commit per slice; this checklist records the real build order, and every slice's mechanical verification was re-run on 2026-10-05 (96 tests green plus the command-line checks).
