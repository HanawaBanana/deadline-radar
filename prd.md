# prd.md — Deadline Radar

Requirements, written after scope.md and before implementation. Each requirement
is testable and is traced to the test that proves it in
`tests/` (unit tests) or `spec.md` §Acceptance.

## The one-sentence product

Paste an announcement; get a brief in which every value is either backed by a
quote from the page or explicitly marked "page does not state", plus an `.ics`
calendar that contains nothing else.

## Users and jobs

**Primary user — the solo opportunity hunter.** "I have 40 tabs of competitions
and I only trust the page. Give me the five facts I act on, show me where each one
came from, and put the deadline in my calendar."

**Secondary user — the sceptic.** "I do not trust summarisers. Show me the raw
model output next to the result and tell me what you threw away."

## Requirements

### Reading

* **R1** The user pastes plain text and analyses it with one action.
  *Test:* `test_analyse_endpoint_returns_a_rendered_brief`.
* **R2** Two readers exist and produce the same JSON shape: a deterministic
  offline reader (no network) and an optional language-model reader.
  *Test:* `test_the_language_model_reader_is_refused_when_running_offline`,
  `test_the_readers_own_output_survives_validation`.
* **R3** Starting without configuration, or with `--offline`, must never touch
  the network. *Test:* the whole suite runs offline; `TestHttp` runs a server
  started with `offline_default=True`.

### Validation (the heart of the product)

* **R4** Every value must be accompanied by evidence that really occurs in the
  pasted text; otherwise the field is rejected with a reason.
  *Test:* `test_evidence_that_is_not_on_the_page_is_rejected`.
* **R5** No number may appear in the brief that does not appear on the page.
  *Test:* `test_a_date_with_a_number_that_is_not_on_the_page_is_rejected`,
  `test_no_brief_contains_a_number_that_is_absent_from_the_page`.
* **R6** Dates are re-parsed by deterministic code and re-rendered as ISO 8601
  with a UTC offset; the page's own wording wins over the reader's claim.
  *Tests:* `test_date_is_rendered_in_iso_with_its_zone`,
  `test_the_page_wins_when_the_model_writes_a_different_date`.
* **R7** Prize amounts are read out of the quoted page text, not from the
  reader's arithmetic. *Test:* `test_prize_amount_comes_from_the_page`,
  `test_amount_that_contradicts_the_quote_is_rejected`.
* **R8** A month/day with no year anywhere on the page must be rejected rather
  than guessed. *Test:*
  `test_a_month_and_day_with_no_year_on_the_page_cannot_be_calendared`.
* **R9** Absent fields become the literal string `page does not state`.
  *Test:* `test_an_empty_field_becomes_page_does_not_state`.
* **R10** A year written only once on the page may be inferred for a
  month/day date, and the field must say so.
  *Test:* `test_chinese_sample_infers_the_missing_year`.

### Reporting

* **R11** The brief shows, per field: the value, the evidence quote, the
  character offsets of that quote, the verdict, and the reason for the verdict.
  *Test:* `test_every_accepted_field_carries_a_span_into_the_page` and the
  rendered checks in `TestHttp`.
* **R12** The raw reader proposal is displayed next to the validated brief, and
  rejected fields are listed separately with the reason.
  *Test:* `test_the_hallucination_step_shows_a_rejection_and_a_correction`.
* **R13** The source text is shown with the evidence spans highlighted in place.
  *Test:* `test_every_demo_step_is_reachable_by_url` (the page renders), and
  `render.source_html` merges overlapping spans without breaking the offsets.

### Calendar

* **R14** Every validated date with a resolvable year becomes a calendar event;
  rejected or unstated dates do not. *Test:*
  `test_only_validated_dates_become_events`, `test_events_only_exist_for_accepted_dates`.
* **R15** The submission deadline carries three reminders (one week, one day and
  two hours before). *Test:* `test_deadline_event_carries_three_reminders`.
* **R16** The file must be valid RFC 5545: CRLF, folded lines, balanced blocks.
  *Test:* `TestStructure` in `tests/test_ics.py`.

### History

* **R17** Every analysis is stored locally (sqlite3) and can be reopened with its
  source text and audit trail. *Test:* `test_save_then_read_back_the_whole_analysis`,
  `test_saved_analysis_can_be_reopened`.
* **R18** The history list shows the newest first, with counts per analysis.
  *Test:* `test_history_is_newest_first_and_carries_counts`.

### Demo and distribution

* **R19** Every state used in the demo must be reachable by URL, so the recorded
  frames are the real product. *Test:* `test_every_demo_step_is_reachable_by_url`.
* **R20** The whole app must run with `python3 app.py` on a clean machine with
  Python 3.9+ and no third-party packages. *Verification:* the test suite and the
  video build both run with only the standard library (edge-tts and ffmpeg are
  used by the video tool, not by the app).

## Non-functional requirements

* **Determinism:** the same text and reader produce the same brief and the same
  `.ics` bytes (except `DTSTAMP`). *Test:* `test_uids_are_stable_between_runs`.
* **No credentials in the repository:** the key is read from the environment or
  from a `.env` that `.gitignore` excludes.
* **Failure is visible:** unhandled HTTP errors are rendered, not swallowed
  (`radar/web.py` returns the traceback in the page and a JSON error from the
  API).
* **Bounded work:** the API rejects bodies over 400 kB.

## Deliberately not building

See scope.md §non-goals. The most tempting one is fetching the page by URL. It is
out of scope because it would move the source of truth away from what the user
actually read, which is the one promise this product makes.

## Open questions for a next version

* Per-field confidence for the offline reader (today it is all-or-nothing).
* A second reader to cross-check the first (two-reader agreement is a stronger
  signal than any prompt).
* Importing a URL *and* storing the fetched bytes so the audit stays honest.
