# SubmitNotes.md — Devpost submission sheet

Everything the Devpost form asks for, in one place, with the exact text to paste.

## Project

* **Project name:** Deadline Radar
* **Tagline (one line):**
  Paste an announcement; get a brief where every value is backed by a quote from
  the page — or says it is not stated.
* **Elevator line (one sentence, if a longer field is offered):**
  A single-user web app that turns messy announcement text into a validated,
  auditable brief and an `.ics` calendar, where deterministic Python — not the
  language model — decides what is true.

* **Built with (5 tags):** `Python` · `SQLite` · `HTML5` · `CSS3` · `JavaScript`

  (The app is Python standard library only; the interface is hand-written HTML,
  CSS and one small JavaScript file; history is stored in sqlite3 from the
  standard library.)

## Submission text for the Devpost form (ready to paste, ~245 words)

> Deadline Radar turns a messy announcement into a brief you can act on, and it
> never asks you to trust a summary.
>
> Paste the text of a competition page, a call for entries or a set of rules. A
> reader — a deterministic offline one, or an optional language model — proposes
> the key dates, prize structure, submission channel, required deliverables and
> eligibility, quoting the page for every value.
>
> Then deterministic Python decides what is true. Every quote must really exist in
> the pasted text. Every number must appear on the page: a value containing an
> invented number is rejected, in public, with the reason. Dates are re-parsed and
> re-rendered as ISO 8601 with a time zone; when the reader and the page disagree,
> the page wins and the field is marked corrected. Prize amounts are read from the
> quoted sentence rather than computed. Anything the page does not state is
> reported as "page does not state".
>
> The result is a brief where each field carries its evidence, its character
> offsets and a verdict, with the raw machine proposal shown next to the validated
> one. Validated dates become an `.ics` calendar with reminders, the whole brief
> downloads as a single self-contained HTML file that still shows every quote with
> the app closed, and every analysis is kept in a local sqlite3 history.
>
> Python standard library only: run it with `python3 app.py --offline`. No
> accounts, no API keys, no dependencies, 96 offline unit tests.

## Links and files

* **Public repository:** https://github.com/HanawaBanana/deadline-radar
* **Demo video (public):** https://youtu.be/DX7l92AQ6pQ — 130 s, 1280×800, 30 fps,
  H.264 + AAC, 3.55 MB. Recorded 2026-10-03 from the guided-tour URLs; the same file
  is committed in the repository at `docs/media/deadline_radar_demo.mp4`.
* **Thumbnail:** `docs/media/thumbnail.jpg`
* **Planning documents (the Devpost Learn Skill Pack workspace):**
  `devpost/scope.md`, `devpost/prd.md`, `devpost/spec.md`, `devpost/checklist.md`,
  `devpost/app-map.html`. The root-level `scope.md` / `prd.md` / `spec.md` are the
  first pass's notes from the same submission period.

## Requirements to run the submitted project

| Requirement | Version / note |
|---|---|
| Python | **3.9 or newer** — that is the whole runtime, standard library only |
| Node.js | **not required** (there is no build step and no npm dependency) |
| git | any recent version, only to clone the repository |
| SQLite | included with Python; the history file `deadline_radar.db` is created on first run |
| Network | **not required** with `--offline`; the optional language-model reader needs an OpenAI-compatible endpoint in `.env` |
| Optional (only to rebuild the demo video) | Google Chrome, `ffmpeg`, `edge-tts` |

```bash
git clone https://github.com/HanawaBanana/deadline-radar
cd deadline-radar
python3 app.py --offline
# open http://127.0.0.1:8781/
```

```bash
python3 -m unittest discover -s tests     # 96 tests, all offline
python3 tools/make_video.py               # optional: rebuild docs/media/deadline_radar_demo.mp4
```

## How the submission meets the track rules

* **New project**: created during the submission window (first commit 2026-10-03,
  emptied-folder start; window runs 2026-09-22 → 2026-10-26).
* **Built with the Devpost Learn Skill Pack**, installed into this repository with
  the command the rules give (`npx skills add challengepost/learn-ai-basics --all -y`
  — recorded in `skills-lock.json`, skills under `.agents/skills/`). The skills ran
  in this coding agent, in sequence: `1-start` (learner profile) → `2-scope`
  (`devpost/scope.md`) → `3-prd` (`devpost/prd.md`) → `4-spec`
  (`devpost/spec.md`, including the exact validation rules) → `5-build`
  (`devpost/checklist.md`: eight slices, each verified and committed; this pass added
  the self-contained HTML brief and its route) → `6-ship` (this sheet).
  `devpost/app-map.html` is the take-home map of the finished code.
* **Planning documents in the repository**: `scope.md`, `prd.md` and `spec.md` as
  the skills generated them, under `devpost/`.
* MIT licence detectable in the About section; README carries the run and test
  commands.
* No third-party paid API and no new account: the offline reader is the default, and
  the optional model reader reuses an endpoint already configured on the machine
  through an environment variable.

### Draft answers for the form's two new required questions (2026-10-05)

* **"A short explanation of how you used the Devpost Learn Skill Pack":**
  *"I ran the pack's skills in my coding agent against this repository and let them
  drive the build. `2-scope` and `3-prd` turned the idea into `devpost/scope.md` and
  `devpost/prd.md`; `4-spec` produced `devpost/spec.md` with the exact validation
  rules and the file structure; `5-build` turned those into `devpost/checklist.md` —
  eight slices built, verified and committed one at a time, including the
  self-contained HTML brief added in this pass. Everything the skills produced is
  still in `devpost/`, and `devpost/app-map.html` maps one action from the paste box
  down to the validator."*
* **Age of majority:** checked — an adult individual entering solo.

## What the demo video shows (1–3 minute requirement, 130 s)
Recorded 2026-10-03 from the same guided-tour URLs: it shows the kernel end to end
but predates the `.html` export link added on 2026-10-05 (that export is covered by
the README and the test suite rather than by a frame in the video).


| Time | Step | What is on screen |
|---|---|---|
| 0:00 | `/?demo=0` | the product: paste box, reader selector, history |
| 0:10 | `/?demo=1` | a real announcement pasted as raw prose |
| 0:20 | `/?demo=2` | the validated brief and its five counters |
| 0:31 | `/?demo=3` | key dates: as written → ISO 8601 with zone, quote and offsets |
| 0:43 | `/?demo=4` | prize structure and deliverables, each with its evidence |
| 0:51 | `/?demo=5` | the audit trail: raw proposal beside validated brief |
| 1:00 | `/?demo=6` | a fabricated $50,000 rejected, a wrong deadline corrected to the page |
| 1:12 | `/?demo=7` | `10月26日 5:00pm ET`: no year on the page, inferred and labelled |
| 1:22 | `/?demo=8` | a thin page: "page does not state" instead of invented values |
| 1:32 | `/ics/demo-a` | the generated `.ics` text with three reminders on the deadline |
| 1:42 | `/?demo=10` | local sqlite3 history |
| 1:50 | `/?demo=11` | the source text with every evidence span highlighted |
| 1:57 | `/?demo=12` | closing: `python3 app.py --offline`, no dependencies |

Every frame is a screenshot of the running application at a URL that anyone can
open; the narration is generated by `tools/make_video.py`.
