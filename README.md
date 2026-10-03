# Deadline Radar

**Paste an announcement. Get a brief where every value is either backed by a quote
from the page, or says "page does not state" — plus an `.ics` calendar that
contains nothing else.**

![Deadline Radar showing a validated brief with evidence and verdicts per field]
(docs/media/thumbnail.jpg)

Most text-to-data tools ask you to trust a summary. Deadline Radar is built the
other way round: a reader proposes values, deterministic Python decides which of
them are true, and anything that cannot be traced back to the pasted text is
thrown out in public.

* **Every field carries its evidence** — the exact quote and its character offsets.
* **Dates are never taken from the model.** They are re-parsed in plain Python and
  re-rendered as ISO 8601 with a time zone.
* **No invented numbers.** A value containing a number that is not on the page is
  rejected, with the reason shown.
* **Gaps stay gaps.** A field the page does not state becomes the literal string
  `page does not state`.
* **The audit is visible.** The raw proposal sits next to the validated brief, and
  rejected fields are listed with the reason.
* **Zero dependencies.** Python standard library only, no account, no token, no
  install step.

```
Build With AI: Basics                        17 values accepted, 0 rejected
Hosted by Devpost                            Key dates   2026-09-22 → 2026-12-01
Submissions close October 26, 2026 at 5:00pm ET  = 2026-10-26T17:00:00-04:00
Grand Prize: $5,000 USD                      read from the quoted line
"the model claims $50,000 USD but the quoted page text says $5,000 USD"  rejected
```

## Run it

```bash
git clone <this repo> && cd deadline-radar
python3 app.py --offline
# open http://127.0.0.1:8781/
```

Python 3.9 or newer. Nothing to install. `--offline` never touches the network.

Useful flags:

```bash
python3 app.py                      # both readers offered in the UI
python3 app.py --port 9000          # different port
python3 app.py --db /tmp/x.db       # where the history lives (default ./deadline_radar.db)
python3 app.py --analyse page.txt   # print the validated brief as JSON
python3 app.py --analyse page.txt --ics out.ics
python3 app.py --plan               # print the demo scenario as JSON
```

## Test it

```bash
python3 -m unittest discover -s tests
```

85 unit tests, all offline: date normalisation (including `10月26日 5:00pm ET`
with no year and US daylight-saving boundaries), prize parsing, the
"page does not state" fallback, rejection of values that are not in the source,
`.ics` generation, sqlite history, and the HTTP endpoints. No test needs a
network connection or an API key.

## Two readers, one validator

| Reader | Network | How it reads |
|---|---|---|
| `offline` (default with `--offline`) | none | regular expressions over paragraphs: dates, money, requirement sentences |
| `llm` | one call to an OpenAI-compatible endpoint | a language model that must quote the page for every value |

Both emit the same JSON, so the pipeline does not care which one ran:

```
text ──▶ reader (offline | llm) ──▶ proposal ──▶ validator ──▶ brief + .ics + audit
                                                    │
                                        dates.py · money.py · the pasted page
```

The validator is the product. It checks that each quote exists in the page, that
every number is on the page, re-parses every date, reads prize amounts out of the
quoted text, and labels each field `accepted`, `corrected`, `rejected` or
`missing`. See `spec.md` for the exact rules.

### The language-model reader (optional)

Put an OpenAI-compatible endpoint in `.env` (git-ignored) or in the environment:

```
LLM_BASE_URL=https://your-endpoint/v1
LLM_API_KEY=...
LLM_MODEL=your-model
```

Then choose "language model + validator" in the UI. If the variables are missing
the app still starts; the offline reader works, and the model reader reports the
missing configuration instead of failing silently. Nothing else in the app needs
the network.

## The demo video

`docs/media/deadline_radar_demo.mp4` (about two minutes) is generated from the
running product, not from slides:

```bash
python3 tools/make_video.py            # needs Google Chrome, ffmpeg and edge-tts
```

The tool starts the app on port 8781 in `--offline` mode, walks the guided-tour
URLs (`/?demo=0` … `/?demo=12`, `/ics/demo-a`), screenshots each state with
headless Chrome, writes the narration with `edge-tts` and assembles the video with
`ffmpeg`. Because every state is a URL, the recording is reproducible and the
frames are the real interface.

## Layout

```
app.py                 CLI and server entry point
radar/dates.py         date, time and time-zone normalisation (deterministic)
radar/money.py         prize amount parsing (deterministic)
radar/offline.py       the offline reader
radar/extract.py       .env loading and the OpenAI-compatible client
radar/validate.py      the validator and the audit trail
radar/ics.py           RFC 5545 calendar output
radar/store.py         sqlite3 history
radar/render.py        all HTML rendering (server side)
radar/web.py           the HTTP surface
radar/demo.py          the guided-tour scenario used by the video
templates/, static/    the page, its CSS and its single script
samples/               three real-shaped pages used in the tests and the demo
scope.md prd.md spec.md  the planning documents this was built from
```

## Why paste text instead of a URL?

Because the promise is "every value comes from the page *you* read". Fetching a URL
would move the source of truth to whatever the server returns at that moment —
behind a login, behind a cookie wall, or after a silent edit. Pasting keeps the
audit honest, and it is the reason this tool needs no scraper, no headless
browser and no rate limits.

## Design notes

* **Deterministic code owns arithmetic.** Models are allowed to read; they are not
  allowed to compute, round, convert or restate a number.
* **Rejection is a feature.** The counters are shown, not hidden.
* **The evidence offset is always into the original text**, even when the match
  ignored case, punctuation or line wrapping.
* **Same input, same output.** Identical text produces an identical brief and
  identical `.ics` bytes; the calendar UIDs are derived from the field and the
  ISO instant.

## License

MIT — see `LICENSE`.
