"""One validated brief as a single self-contained HTML file.

The brief is only worth anything if it survives leaving the app: attached to an
email, copied to a USB stick, opened on a machine that has never seen Deadline
Radar. So this module writes one document that carries everything - the verdict
of every field, the quoted page text behind it, the character offsets, the raw
proposal next to the validated brief and the exact .ics payload - with its
stylesheet inlined. The output has no <link rel="stylesheet">, no <script src>
and no remote asset of any kind; URLs that merely appear in the page text stay
as text. Every string that came from the page goes through html.escape().
"""

import datetime

from . import ics as ics_mod
from . import render

MISSING_TEXT = "page does not state"

STYLE = """\
* { box-sizing: border-box; }
body {
  margin: 0; padding: 1.5rem 1rem 3rem; background: #f7f8fa; color: #101828;
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
main { max-width: 920px; margin: 0 auto; }
h1 { font-size: 1.3rem; margin: 0 0 .3rem; }
h2 { font-size: .95rem; text-transform: uppercase; letter-spacing: .06em; color: #475467;
     margin: 0 0 .6rem; }
h3 { font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; color: #667085;
     margin: 1rem 0 .3rem; }
p { margin: .3rem 0; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.card { background: #fff; border: 1px solid #e4e7ec; border-radius: 10px;
        padding: 1rem 1.1rem; margin-bottom: 1rem; }
.sub { color: #667085; font-size: .85rem; }
.chips { margin-top: .5rem; font-size: .85rem; color: #475467; }
.chips b { color: #101828; }
.tbl { width: 100%; border-collapse: collapse; font-size: .85rem; }
.tbl th { text-align: left; font-size: .72rem; text-transform: uppercase; letter-spacing: .05em;
          color: #667085; border-bottom: 1px solid #e4e7ec; padding: .35rem .5rem .35rem 0; }
.tbl td { vertical-align: top; padding: .5rem .5rem .5rem 0; border-bottom: 1px solid #f2f4f7; }
.c-id { width: 22%; }
.c-ev { width: 30%; }
.c-verdict { width: 20%; }
.lbl { color: #667085; font-size: .78rem; }
.ev { background: #f2f4f7; border-radius: 4px; padding: 0 .25rem; word-break: break-word; }
.ev-none { color: #667085; font-size: .8rem; }
.offs { color: #667085; font-size: .75rem; white-space: nowrap; }
.why { color: #475467; font-size: .78rem; margin-top: .2rem; }
.pill { display: inline-block; border-radius: 999px; padding: .05rem .5rem; font-size: .75rem;
        font-weight: 600; }
.pill-accepted { background: #ecfdf3; color: #067647; }
.pill-corrected { background: #fffaeb; color: #b54708; }
.pill-rejected { background: #fef3f2; color: #b42318; }
.pill-missing { background: #f2f4f7; color: #475467; }
pre { background: #f7f8fa; border: 1px solid #e4e7ec; border-radius: 8px; padding: .7rem;
      overflow: auto; font-size: .78rem; white-space: pre-wrap; word-break: break-word; }
mark { background: #eef0ff; border-bottom: 2px solid #3538cd; }
footer { color: #667085; font-size: .78rem; }
.empty { color: #667085; }
"""


def _pill(verdict):
    verdict = verdict or "missing"
    return '<span class="pill pill-%s">%s</span>' % (render.esc(verdict), render.esc(verdict))


def _offsets(field):
    span = field.get("span")
    if span and len(span) == 2:
        return '<span class="offs">chars %d-%d</span>' % (span[0], span[1])
    return '<span class="offs">no character offsets</span>'


def _evidence(field):
    text = field.get("evidence") or ""
    if not text:
        return '<span class="ev-none">no evidence quoted</span>'
    return '<code class="ev">%s</code>' % render.esc(text)


def _field_rows(fields):
    rows = []
    for field in fields:
        rows.append(
            "<tr>"
            '<td class="c-id"><code>%s</code><br><span class="lbl">%s</span></td>'
            '<td class="c-val">%s</td>'
            '<td class="c-verdict">%s<div class="why">%s</div></td>'
            '<td class="c-ev">%s %s</td>'
            "</tr>" % (
                render.esc(field.get("id", "")), render.esc(field.get("label", "")),
                render.esc(field.get("value", "")), _pill(field.get("verdict")),
                render.esc(field.get("reason", "")), _evidence(field), _offsets(field)))
    return "".join(rows)


def _date_rows(result):
    rows = []
    for field in result.get("key_dates") or []:
        rows.append(
            "<tr>"
            '<td class="c-id"><code>%s</code><br><span class="lbl">%s</span></td>'
            '<td class="c-val">%s%s</td>'
            '<td class="c-verdict"><code>%s</code><br><span class="offs">%s %s</span>'
            '<div class="why">%s</div></td>'
            '<td class="c-ev">%s %s</td>'
            "</tr>" % (
                render.esc(field.get("id", "")), render.esc(field.get("label", "")),
                render.esc(field.get("raw_value") or field.get("value") or ""),
                '<br><span class="offs">year inferred</span>' if field.get("year_inferred") else "",
                render.esc(field.get("iso") or "no ISO 8601 value"),
                render.esc(field.get("zone") or "unknown zone"),
                render.esc(field.get("precision") or ""), render.esc(field.get("reason", "")),
                _evidence(field), _offsets(field)))
    if not rows:
        return '<p class="empty">%s any dates.</p>' % MISSING_TEXT
    return "".join(rows)


def _rejected_rows(rejected):
    if not rejected:
        return ('<p class="empty">Nothing was rejected: every proposed value was found '
                "in the page.</p>")
    rows = []
    for field in rejected:
        rows.append(
            "<tr>"
            '<td class="c-id"><code>%s</code></td>'
            '<td class="c-val">%s</td>'
            '<td class="c-ev">%s %s</td>'
            '<td class="c-verdict">%s<div class="why">%s</div></td>'
            "</tr>" % (
                render.esc(field.get("id", "")),
                render.esc(field.get("raw_value") or field.get("value") or MISSING_TEXT),
                _evidence(field), _offsets(field), _pill(field.get("verdict") or "rejected"),
                render.esc(field.get("reason", ""))))
    return "".join(rows)


def brief_html(record):
    """Render one store record (store.get(id)) as a standalone HTML document."""
    record = record or {}
    result = record.get("result") or {}
    source = record.get("source") or ""
    brief = result.get("brief") or {}
    counts = result.get("counts") or {}
    source_meta = result.get("source") or {}
    title = brief.get("title") or "Untitled page"
    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    fields = list(result.get("fields") or []) + list(result.get("rejected") or [])
    ics_text = ics_mod.build(result)
    formula = ("Generated %s by Deadline Radar &middot; analysis %s &middot; reader %s &middot; "
               "source sha256 %s &middot; %s chars &middot; %s"
               % (render.esc(generated), render.esc(record.get("id") or "-"),
                  render.esc(record.get("mode") or result.get("mode") or "-"),
                  render.esc(source_meta.get("sha256") or "-"),
                  render.esc(source_meta.get("chars", len(source))),
                  render.esc(record.get("created_at") or result.get("created_at") or "-")))

    document = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Deadline Radar brief - %(title)s</title>
<style>
%(style)s</style>
</head>
<body>
<main>
  <section class="card">
    <h1>%(title)s</h1>
    <p class="sub">validated brief &middot; every value below is either quoted from the page or
    spelled <b>%(missing)s</b></p>
    <p class="chips">%(accepted)s accepted &middot; %(corrected)s corrected &middot;
    %(rejected)s rejected &middot; %(missing_count)s <b>%(missing)s</b> &middot;
    %(events)s calendar events</p>
  </section>

  <section class="card">
    <h2>Fields, verdicts and evidence</h2>
    <table class="tbl">
      <thead><tr><th>field</th><th>value</th><th>verdict</th><th>evidence quoted from the page</th></tr></thead>
      <tbody>%(fields)s</tbody>
    </table>
  </section>

  <section class="card">
    <h2>Key dates</h2>
    <table class="tbl">
      <thead><tr><th>field</th><th>as written on the page</th><th>normalised</th><th>evidence</th></tr></thead>
      <tbody>%(dates)s</tbody>
    </table>
  </section>

  <section class="card">
    <h2>Audit trail</h2>
    <h3>Raw proposal (what the reader proposed)</h3>
    <pre>%(raw)s</pre>
    <h3>Validated brief (what survived)</h3>
    <pre>%(validated)s</pre>
    <h3>Rejected</h3>
    <table class="tbl">
      <thead><tr><th>field</th><th>the reader proposed</th><th>what the page says</th><th>verdict</th></tr></thead>
      <tbody>%(rejected_rows)s</tbody>
    </table>
  </section>

  <section class="card">
    <h2>Source text with evidence highlighted</h2>
    <pre>%(source)s</pre>
  </section>

  <section class="card">
    <h2>Calendar file (.ics)</h2>
    <p class="sub">Exactly the bytes the Download .ics button serves: only validated dates.</p>
    <pre>%(ics)s</pre>
  </section>

  <footer><p>%(formula)s</p>
  <p>This file is self-contained: the stylesheet is inlined and nothing is fetched.</p></footer>
</main>
</body>
</html>
""" % {
        "title": render.esc(title),
        "style": STYLE,
        "missing": MISSING_TEXT,
        "accepted": counts.get("accepted", 0),
        "corrected": counts.get("corrected", 0),
        "rejected": counts.get("rejected", 0),
        "missing_count": counts.get("missing", 0),
        "events": len(result.get("events") or []),
        "fields": _field_rows(fields),
        "dates": _date_rows(result),
        "raw": render.esc(render.raw_json(result)),
        "validated": render.esc(render.validated_json(result)),
        "rejected_rows": _rejected_rows(result.get("rejected") or []),
        "source": render.source_html(source, fields),
        "ics": render.esc(ics_text),
        "formula": formula,
    }
    return document
