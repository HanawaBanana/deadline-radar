"""Server-side HTML rendering.

The browser never assembles the brief. Python renders the same markup for the
interactive request, for a saved analysis reopened from history, and for the
demo tour, so what the screenshots capture is exactly what a user gets. The
client-side JavaScript only swaps this fragment in and out.
"""

import html
import json

VERDICT_LABEL = {
    "accepted": "accepted",
    "corrected": "corrected",
    "rejected": "rejected",
    "missing": "not stated",
}


def esc(text):
    return html.escape(str(text if text is not None else ""), quote=True)


def _pill(verdict):
    return '<span class="pill pill-%s">%s</span>' % (
        esc(verdict), esc(VERDICT_LABEL.get(verdict, verdict)))


def _evidence(field):
    span = field.get("span")
    where = ""
    if span and len(span) == 2:
        where = ' <span class="offs">chars %d-%d</span>' % (span[0], span[1])
    text = field.get("evidence") or ""
    if not text:
        return '<span class="ev ev-none">no evidence quoted</span>'
    return '<code class="ev">%s</code>%s' % (esc(text), where)


def source_html(source, fields):
    """The page with every accepted evidence span highlighted."""
    spans = []
    for field in fields:
        span = field.get("span")
        if span and len(span) == 2 and span[1] > span[0]:
            spans.append((span[0], span[1], field.get("id", ""), field.get("verdict", "")))
    spans.sort()
    merged = []
    for start, end, fid, verdict in spans:
        if merged and start < merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1][1] = end
            continue
        merged.append([start, end, verdict])
    out = []
    cursor = 0
    for start, end, verdict in merged:
        out.append(esc(source[cursor:start]))
        out.append('<mark class="mark-%s">%s</mark>' % (esc(verdict), esc(source[start:end])))
        cursor = end
    out.append(esc(source[cursor:]))
    return "".join(out)


def field_rows(result):
    """Text fields as a definition list with verdicts and evidence."""
    rows = []
    for field in result.get("fields", []):
        if field.get("kind") != "text":
            continue
        rows.append(
            '<div class="field" id="f-%s">'
            '<div class="field-head"><span class="field-name">%s</span>%s</div>'
            '<div class="field-value">%s</div>'
            '<div class="field-ev">%s</div>'
            '<div class="field-why">%s</div>'
            '</div>' % (
                esc(field["id"]), esc(field["label"]), _pill(field["verdict"]),
                esc(field["value"]), _evidence(field), esc(field["reason"])))
    return "".join(rows)


def date_rows(result):
    rows = []
    for field in result.get("key_dates", []):
        iso = field.get("iso") or "&mdash;"
        note = ""
        if field.get("year_inferred"):
            note = '<span class="tag">year inferred</span>'
        rows.append(
            "<tr>"
            '<td class="c-label">%s%s<br><span class="raw-label">%s</span></td>'
            '<td class="c-raw">%s</td>'
            '<td class="c-iso"><code>%s</code>%s</td>'
            '<td class="c-ev">%s</td>'
            '<td class="c-verdict">%s<div class="why">%s</div></td>'
            "</tr>" % (
                esc(field["label"]), note, esc(field.get("raw_label") or ""),
                esc(field.get("raw_value") or ""), esc(iso),
                ('<br><span class="offs">%s %s</span>' % (esc(field.get("zone") or ""),
                                                          esc(field.get("precision") or ""))),
                _evidence(field), _pill(field["verdict"]), esc(field["reason"])))
    if not rows:
        rows.append('<tr><td colspan="5" class="empty">page does not state any dates</td></tr>')
    return "".join(rows)


def prize_rows(result):
    rows = []
    for field in result.get("fields", []):
        if field.get("name") != "prizes":
            continue
        rows.append(
            "<tr>"
            '<td class="c-label">%s</td><td class="c-iso">%s</td>'
            '<td class="c-ev">%s</td><td class="c-verdict">%s<div class="why">%s</div></td>'
            "</tr>" % (esc(field.get("place") or field["label"]), esc(field["value"]),
                       _evidence(field), _pill(field["verdict"]), esc(field["reason"])))
    if not rows:
        for field in result.get("fields", []):
            if field.get("name") == "prizes":
                rows.append('<tr><td colspan="4" class="empty">page does not state</td></tr>')
                break
    if not rows:
        rows.append('<tr><td colspan="4" class="empty">page does not state any prizes</td></tr>')
    return "".join(rows)


def deliverable_items(result):
    items = []
    for field in result.get("fields", []):
        if field.get("name") != "deliverables":
            continue
        items.append(
            '<li><div class="deliv"><span class="deliv-value">%s</span>%s</div>'
            '<div class="field-ev">%s</div><div class="field-why">%s</div></li>'
            % (esc(field["value"]), _pill(field["verdict"]), _evidence(field),
               esc(field["reason"])))
    if not items:
        return '<li class="empty">page does not state any deliverables</li>'
    return "".join(items)


def rejected_table(result):
    rejected = result.get("rejected") or []
    if not rejected:
        return ('<p class="empty ok">Nothing was rejected: every proposed value was found in '
                'the page.</p>')
    rows = []
    for field in rejected:
        rows.append(
            "<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                esc(field["id"]), esc(field.get("raw_value") or field.get("evidence") or ""),
                esc(field.get("evidence") or ""), esc(field["reason"])))
    return ("<table class=\"tbl\"><thead><tr><th>field</th><th>the model proposed</th>"
            "<th>what the page says</th><th>why it was rejected</th></tr></thead>"
            "<tbody>%s</tbody></table>" % "".join(rows))


def calendar_html(result):
    events = result.get("events") or []
    if not events:
        return '<p class="empty">No calendar events: no accepted date yet.</p>'
    rows = []
    for event in events:
        rows.append(
            "<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                esc(event["uid"][:12] + "..."), esc(event["summary"]),
                esc(event["start"] + (" (all day)" if event["all_day"] else "")),
                esc(event.get("utc") or "-"),
                " ".join('<code class="alarm">%s</code>' % esc(a) for a in event["alarms"])))
    return ("<table class=\"tbl\"><thead><tr><th>UID</th><th>event</th><th>start</th>"
            "<th>UTC</th><th>reminders</th></tr></thead><tbody>%s</tbody></table>"
            % "".join(rows))


def raw_json(result):
    return json.dumps(result.get("raw") or {}, indent=2, ensure_ascii=False)


def validated_json(result):
    slim = {
        "title": (result.get("brief") or {}).get("title"),
        "organizer": (result.get("brief") or {}).get("organizer"),
        "submission_channel": (result.get("brief") or {}).get("submission_channel"),
        "eligibility": (result.get("brief") or {}).get("eligibility"),
        "key_dates": [
            {"field": f["name"], "iso": f.get("iso"), "zone": f.get("zone"),
             "verdict": f["verdict"], "year_inferred": f.get("year_inferred", False)}
            for f in result.get("key_dates", [])],
        "prizes": [
            {"place": f.get("place"), "value": f["value"], "amount": f.get("amount"),
             "currency": f.get("currency"), "verdict": f["verdict"]}
            for f in result.get("fields", []) if f.get("name") == "prizes"],
        "counts": result.get("counts"),
        "ungrounded_numbers": result.get("ungrounded_numbers"),
    }
    return json.dumps(slim, indent=2, ensure_ascii=False)


def history_html(rows, current_id=None):
    if not rows:
        return '<p class="empty">No analyses yet.</p>'
    items = []
    for row in rows:
        current = " current" if row["id"] == current_id else ""
        items.append(
            '<li class="hist%s"><a href="/analysis/%s">'
            '<span class="hist-title">%s</span>'
            '<span class="hist-meta">%s &middot; %s &middot; %d events &middot; %d rejected</span>'
            "</a></li>" % (
                current, esc(row["id"]), esc(row["title"]), esc(row["created_at"]),
                esc(row["mode"]), row.get("events", 0), row.get("rejected", 0)))
    return '<ul class="hist-list">%s</ul>' % "".join(items)


def result_html(result, source, analysis_id=None, ics_url=None):
    """The whole brief: fields, dates, prizes, source, audit trail, calendar."""
    counts = result.get("counts") or {}
    ics_url = ics_url or ("/api/analysis/%s.ics" % analysis_id if analysis_id else "#")
    brief_url = ("/api/analysis/%s.html" % analysis_id) if analysis_id else ""
    brief_link = ('<a class="btn" id="brief-link" href="%s">Download brief (.html)</a>'
                  % esc(brief_url)) if brief_url else ""
    return """
<div class="result">
  <section class="card" id="brief-head">
    <div class="head-row">
      <div>
        <h2 class="brief-title">%(title)s</h2>
        <p class="brief-sub">%(subtitle)s</p>
      </div>
      <div class="head-actions">
        <span class="pill pill-%(mode)s">%(mode)s reader</span>
        <a class="btn btn-primary" id="ics-link" href="%(ics_url)s">Download .ics</a>
        %(brief_link)s
      </div>
    </div>
    <div class="counters">
      <div class="counter"><b>%(accepted)s</b><span>accepted</span></div>
      <div class="counter"><b>%(corrected)s</b><span>corrected</span></div>
      <div class="counter"><b>%(rejected)s</b><span>rejected</span></div>
      <div class="counter"><b>%(missing)s</b><span>page does not state</span></div>
      <div class="counter"><b>%(events)s</b><span>calendar events</span></div>
    </div>
  </section>

  <div class="grid2">
    <section class="card" id="fields">
      <h3>What the page says</h3>
      %(fields)s
    </section>
    <section class="card" id="dates">
      <h3>Key dates</h3>
      <table class="tbl tbl-dates">
        <thead><tr><th>field</th><th>as written on the page</th><th>normalised (ISO 8601)</th>
        <th>evidence</th><th>verdict</th></tr></thead>
        <tbody>%(dates)s</tbody>
      </table>
      <p class="card-note">Dates are re-parsed from the quoted page text. The model is never
      trusted to do the arithmetic, and a year that the page does not repeat is labelled
      <span class="tag">year inferred</span>.</p>
    </section>
  </div>

  <section class="card" id="prizes">
    <h3>Prize structure</h3>
    <table class="tbl"><thead><tr><th>place</th><th>amount read from the page</th>
    <th>evidence</th><th>verdict</th></tr></thead><tbody>%(prizes)s</tbody></table>
    <h3 class="mt">Required deliverables</h3>
    <ul class="deliv-list">%(deliverables)s</ul>
  </section>

  <section class="card" id="calendar">
    <h3>Calendar the brief produces</h3>
    %(calendar)s
    <p class="card-note">Only validated dates become events. Deadline events carry three
    reminders: one week, one day and two hours before.</p>
  </section>

  <section class="card" id="audit">
    <h3>Audit trail</h3>
    <p class="card-note">Left: exactly what the reader proposed. Right: what survived
    validation, plus every field that did not.</p>
    <div class="grid2 grid-audit">
      <div>
        <h4>Raw proposal (JSON)</h4>
        <pre class="json" id="raw-json">%(raw)s</pre>
      </div>
      <div>
        <h4>Validated brief (JSON)</h4>
        <pre class="json" id="validated-json">%(validated)s</pre>
        <h4 class="mt">Rejected</h4>
        %(rejected)s
      </div>
    </div>
    %(ungrounded)s
  </section>

  <section class="card" id="source">
    <h3>Source text with evidence highlighted</h3>
    <p class="card-note">Every value above points at one of these marked spans.</p>
    <pre class="source">%(source)s</pre>
  </section>
</div>
""" % {
        "title": esc((result.get("brief") or {}).get("title") or "Untitled page"),
        "subtitle": esc("analysed %s &middot; %s chars &middot; source fingerprint %s" % (
            result.get("created_at", ""), (result.get("source") or {}).get("chars", 0),
            (result.get("source") or {}).get("sha256", ""))),
        "mode": esc(result.get("mode", "")),
        "accepted": counts.get("accepted", 0),
        "corrected": counts.get("corrected", 0),
        "rejected": counts.get("rejected", 0),
        "missing": counts.get("missing", 0),
        "events": len(result.get("events") or []),
        "ics_url": esc(ics_url),
        "brief_link": brief_link,
        "fields": field_rows(result),
        "dates": date_rows(result),
        "prizes": prize_rows(result),
        "deliverables": deliverable_items(result),
        "calendar": calendar_html(result),
        "raw": esc(raw_json(result)),
        "validated": esc(validated_json(result)),
        "rejected": rejected_table(result),
        "ungrounded": _ungrounded_note(result),
        "source": source_html(source, result.get("fields", []) + result.get("rejected", [])),
    }


def _ungrounded_note(result):
    bad = result.get("ungrounded_numbers") or []
    if not bad:
        return ('<p class="ok">Cross-check: every number in the validated brief also appears '
                'in the page.</p>')
    return ('<p class="warn">Cross-check: these numbers in the brief were not found in the '
            'page: <code>%s</code></p>' % esc(", ".join(bad)))


def page(template, **values):
    out = template
    for key, value in values.items():
        out = out.replace("{{%s}}" % key, value)
    return out


def tour_bar(tour):
    """The guided-tour strip used by the demo pages (/?demo=N)."""
    nav = []
    if tour.get("prev") is not None:
        nav.append('<a class="btn" href="%s">&larr; previous</a>' % esc(tour["prev"]))
    if tour.get("next") is not None:
        nav.append('<a class="btn btn-primary" href="%s">next &rarr;</a>' % esc(tour["next"]))
    return (
        '<div class="tour">'
        '<span class="tour-step">guided tour %d/%d</span>'
        '<span class="tour-title">%s</span>'
        '<span class="tour-note">%s</span>'
        '<span class="tour-nav">%s<a class="btn" href="/api/demo">steps as JSON</a></span>'
        '</div>' % (tour.get("n", 0), tour.get("total", 0), esc(tour.get("title", "")),
                    esc(tour.get("note", "")), "".join(nav)))
