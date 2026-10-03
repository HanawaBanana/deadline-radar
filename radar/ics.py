"""Calendar output: a plain RFC 5545 .ics file, no dependencies.

Only events the validator accepted are written, so the calendar can never
contain a date the page did not state. Deadlines get three reminders
(one week, one day, two hours before).
"""

import datetime

PRODID = "-//Deadline Radar//Validated brief//EN"
UID_DOMAIN = "deadline-radar.local"


def escape(text):
    out = str(text or "")
    out = out.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return out.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def fold(line):
    """RFC 5545 line folding at 75 octets, UTF-8 safe."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    parts = []
    current = b""
    for ch in line:
        chunk = ch.encode("utf-8")
        limit = 75 if not parts else 74
        if len(current) + len(chunk) > limit:
            parts.append(current)
            current = b" " + chunk
        else:
            current += chunk
    if current:
        parts.append(current)
    return "\r\n".join(p.decode("utf-8") for p in parts)


def build(result, calendar_name="Deadline Radar"):
    """Render the validated events of an analysis result as an .ics string."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:" + PRODID,
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + escape(calendar_name),
        "X-WR-TIMEZONE:UTC",
    ]
    for event in result.get("events", []):
        lines.append("BEGIN:VEVENT")
        lines.append("UID:" + event["uid"])
        lines.append("DTSTAMP:" + now)
        if event.get("all_day") or not event.get("utc"):
            lines.append("DTSTART;VALUE=DATE:" + event["start"])
            end = event.get("end") or event["start"]
            lines.append("DTEND;VALUE=DATE:" + end)
        else:
            stamp = event["utc"].replace("-", "").replace(":", "")
            if not stamp.endswith("Z"):
                stamp += "Z"
            lines.append("DTSTART:" + stamp)
            lines.append("DTEND:" + stamp)
        lines.append("SUMMARY:" + escape(event["summary"]))
        lines.append("DESCRIPTION:" + escape(event.get("description", "")))
        lines.append("TRANSP:TRANSPARENT")
        lines.append("STATUS:CONFIRMED")
        lines.append("CATEGORIES:Deadline Radar")
        for alarm in event.get("alarms", []):
            lines.append("BEGIN:VALARM")
            lines.append("ACTION:DISPLAY")
            lines.append("DESCRIPTION:" + escape(event["summary"]))
            lines.append("TRIGGER:" + alarm)
            lines.append("END:VALARM")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


def filename(result):
    title = (result.get("brief") or {}).get("title") or "deadline-radar"
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(title).lower())
    while "--" in slug:
        slug = slug.replace("--", "-")
    return (slug.strip("-") or "deadline-radar")[:48] + "-deadlines.ics"
