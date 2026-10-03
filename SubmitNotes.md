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

## Submission text for the Devpost form (226 words)

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
> one. Validated dates become an `.ics` calendar with reminders, and every
> analysis is kept in a local sqlite3 history.
>
> Python standard library only: run it with `python3 app.py --offline`. No
> accounts, no API keys, no dependencies, 85 offline unit tests.

## Links and files

* **Public repository:** https://github.com/HanawaBanana/deadline-radar
* **Demo video (local file, to be uploaded to YouTube by the main session):**
  `docs/media/deadline_radar_demo.mp4` — 130 s, 1280×800, 30 fps, H.264 + AAC,
  3.55 MB. The same file is committed in the repository under `docs/media/`.
* **Thumbnail:** `docs/media/thumbnail.jpg`
* **Planning documents (required by the track, all at the repository root):**
  `scope.md`, `prd.md`, `spec.md`

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
python3 -m unittest discover -s tests     # 85 tests, all offline
python3 tools/make_video.py               # optional: rebuild docs/media/deadline_radar_demo.mp4
```

## How the submission meets the track rules

* New project, started from an empty folder during the submission window.
* Built following the planning workflow: `scope.md` (problem, users, scope,
  non-goals) → `prd.md` (numbered, testable requirements) → `spec.md` (exact
  behaviour, API surface, acceptance checks) → implementation → tests.
* No third-party paid API and no new account: the offline reader is the default,
  and the optional model reader reuses an endpoint already configured on the
  machine through an environment variable.
* The repository contains the three planning documents at its root, an MIT
  licence, and a README with the run and test commands.

## What the demo video shows (1–3 minute requirement, 130 s)

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
