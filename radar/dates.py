"""Deterministic date and time normalisation for Deadline Radar.

A language model is allowed to *read* dates out of messy prose. It is never
trusted to do the arithmetic: every date that reaches the brief or the calendar
is re-parsed here, in plain Python, from the date string the model claims to
have seen plus the source page it was given.

Handled formats (all unit tested):

    2026-10-26          26/10/2026          2026年10月26日
    October 26, 2026    Oct 26 2026         26 October 2026
    10月26日 5:00pm ET   Sep 22nd at 5:00 PM ET   5pm EST on 26 October 2026
    September 22 - October 26, 2026

Everything is standard library only.
"""

import datetime
import re

MONTHS = {
    "january": 1, "jan": 1, "jan.": 1,
    "february": 2, "feb": 2, "feb.": 2,
    "march": 3, "mar": 3, "mar.": 3,
    "april": 4, "apr": 4, "apr.": 4,
    "may": 5,
    "june": 6, "jun": 6, "jun.": 6,
    "july": 7, "jul": 7, "jul.": 7,
    "august": 8, "aug": 8, "aug.": 8,
    "september": 9, "sept": 9, "sep": 9, "sep.": 9,
    "october": 10, "oct": 10, "oct.": 10,
    "november": 11, "nov": 11, "nov.": 11,
    "december": 12, "dec": 12, "dec.": 12,
}

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]

# name -> (standard UTC offset, daylight UTC offset). No tz database needed.
ZONES = {
    "America/New_York": (-5, -4),
    "America/Chicago": (-6, -5),
    "America/Denver": (-7, -6),
    "America/Los_Angeles": (-8, -7),
    "UTC": (0, 0),
    "Asia/Shanghai": (8, 8),
}

TZ_ALIASES = {
    "et": "America/New_York", "est": "America/New_York", "edt": "America/New_York",
    "eastern": "America/New_York", "eastern time": "America/New_York",
    "us/eastern": "America/New_York", "new york": "America/New_York",
    "ct": "America/Chicago", "cdt": "America/Chicago", "central": "America/Chicago",
    "mt": "America/Denver", "mdt": "America/Denver", "mountain": "America/Denver",
    "pt": "America/Los_Angeles", "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles",
    "pacific": "America/Los_Angeles", "us/pacific": "America/Los_Angeles",
    "utc": "UTC", "gmt": "UTC", "z": "UTC",
    "cst china": "Asia/Shanghai", "china standard time": "Asia/Shanghai",
    "beijing time": "Asia/Shanghai", "asia/shanghai": "Asia/Shanghai", "北京时间": "Asia/Shanghai",
}

YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

_ISO_RE = re.compile(
    r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})"
    r"(?:[T ](?P<h>\d{1,2}):(?P<mi>\d{2})(?::(?P<s>\d{2}))?\s*(?P<ap>am|pm)?)?",
    re.I)
_MONTH_FIRST_RE = re.compile(
    r"(?<![\d:])(?P<mon>[A-Za-z]{3,9})\.?[\s,]+(?P<d>\d{1,2})(?![\d])(?:st|nd|rd|th)?(?:\s*,)?(?:\s+(?P<y>\d{4})(?!\d))?",
    re.I)
_DAY_FIRST_RE = re.compile(
    r"(?<![\d])(?P<d>\d{1,2})(?![\d])(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<mon>[A-Za-z]{3,9})\.?(?:\s*,)?(?:\s+(?P<y>\d{4})(?!\d))?",
    re.I)
_SLASH_RE = re.compile(r"(?P<a>\d{1,2})/(?P<b>\d{1,2})/(?P<y>\d{4})")
_CJK_RE = re.compile(r"(?:(?P<y>\d{4})\s*年\s*)?(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日")
_TIME_RE = re.compile(r"(?<![\d:])(?P<h>\d{1,2})(?::(?P<mi>\d{2}))?\s*(?P<ap>am|pm)?(?![\d:])", re.I)
_TZ_RE = re.compile(
    r"\b(US/Eastern|US/Pacific|Eastern\s+Time|Central\s+Time|Mountain\s+Time|Pacific\s+Time|"
    r"ET|EST|EDT|CT|CDT|MT|MDT|PT|PST|PDT|UTC|GMT)\b|(北京时间|中国标准时间)",
    re.I)
_RANGE_SPLIT_RE = re.compile(r"\s*(?:--|-|–|—|~|to|through|until|至)\s*", re.I)


def _nth_weekday(year, month, weekday, n):
    """weekday: Monday=0 .. Sunday=6. n is 1-based."""
    first = datetime.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + datetime.timedelta(days=offset + 7 * (n - 1))


def us_dst_active(day):
    """US DST rule: 2nd Sunday in March -> 1st Sunday in November."""
    if day.month in (4, 5, 6, 7, 8, 9, 10):
        return True
    if day.month in (12, 1, 2):
        return False
    if day.month == 3:
        return day >= _nth_weekday(day.year, 3, 6, 2)
    return day < _nth_weekday(day.year, 11, 6, 1)


def utc_offset(zone, day):
    if zone not in ZONES:
        return 0
    std, dst = ZONES[zone]
    if std == dst:
        return std
    return dst if us_dst_active(day) else std


def format_offset(offset):
    sign = "+" if offset >= 0 else "-"
    return "%s%02d:%02d" % (sign, abs(offset), 0)


def year_hints(text):
    """Distinct 4-digit years mentioned anywhere in the page, in order."""
    seen = []
    for m in YEAR_RE.finditer(text or ""):
        y = int(m.group(0))
        if y not in seen:
            seen.append(y)
    return seen


def choose_year(month, day, hints, default_year=None, reference=None):
    """Pick a year for a date that was written without one.

    Rules, in order:
      1. a single year mentioned on the page wins;
      2. otherwise the year of the closest mention on or after the reference
         date (a prospectus says "2026" six times and "deadline 15 March");
      3. otherwise `default_year`;
      4. otherwise None -> the caller reports "page does not state".
    """
    if hints:
        try:
            if reference is not None and len(hints) > 1:
                after = [y for y in hints if y >= reference.year]
                if after:
                    return min(after)
                return max(hints)
            if reference is not None:
                y = hints[0]
                cand = datetime.date(y, month, day) if _valid(y, month, day) else None
                if cand is not None and cand < reference:
                    return y + 1
                return y
            return max(hints)
        except (ValueError, TypeError):
            return hints[0]
    return default_year


def _valid(y, m, d):
    try:
        datetime.date(y, m, d)
        return True
    except ValueError:
        return False


def _month(name):
    return MONTHS.get((name or "").lower().strip())


def _apply_ampm(hour, ap):
    if not ap:
        return hour
    ap = ap.lower()
    if ap == "pm" and hour < 12:
        return hour + 12
    if ap == "am" and hour == 12:
        return 0
    return hour


def _find_time(text):
    """First clock time in the token, with its timezone if one sits next to it."""
    for m in _TIME_RE.finditer(text):
        h = int(m.group("h"))
        mi = int(m.group("mi") or 0)
        ap = m.group("ap")
        if not ap and not m.group("mi"):
            # "5" alone, or a bare year such as 2026, is not a time.
            continue
        if h > 23 or mi > 59:
            continue
        tail = text[m.end():m.end() + 26]
        tzm = _TZ_RE.search(tail)
        zone = None
        if tzm:
            zone = _tz_alias(tzm)
        return {"hour": _apply_ampm(h, ap), "minute": mi, "zone": zone}
    # "5:00pm" written before the date, or a timezone with no clock time
    tzm = _TZ_RE.search(text)
    zone = _tz_alias(tzm) if tzm else None
    return {"hour": None, "minute": None, "zone": zone}


def _tz_alias(match):
    """The zone name out of a _TZ_RE match (Latin alternatives first, then CJK)."""
    return TZ_ALIASES.get((match.group(1) or match.group(2)).lower().replace("  ", " "))


def _zone(name):
    if not name:
        return "UTC"
    return TZ_ALIASES.get(name.lower().replace("  ", " "), name)


def _clause(text, m):
    """The date token's own clause, before and after it, so a time found there
    belongs to this date and not to the next bullet point."""
    before = text[max(0, m.start() - 30):m.start()]
    for i in range(len(before) - 1, -1, -1):
        if before[i] in "\n;.":
            before = before[i + 1:]
            break
    after = text[m.end():m.end() + 48]
    for i, ch in enumerate(after):
        if ch in "\n;.":
            after = after[:i]
            break
    return before, after


def _time_for(text, m):
    before, after = _clause(text, m)
    got = _find_time(after)
    if got["hour"] is not None or got["zone"] is not None:
        return got
    got2 = _find_time(before)
    if got2["hour"] is not None or got2["zone"] is not None:
        return got2
    return got


def _iso_parse(m, hints, default_year, reference):
    y = int(m.group("y"))
    mo = int(m.group("m"))
    d = int(m.group("d"))
    if not _valid(y, mo, d):
        return None
    hm = _find_time(m.group(0))
    hour = hm["hour"] if m.group("h") else hm["hour"]
    hm = _find_time(m.group(0))
    if m.group("h"):
        hour = _apply_ampm(int(m.group("h")), m.group("ap"))
        minute = int(m.group("mi") or 0)
    else:
        hour, minute = hm["hour"], hm["minute"]
    return _build(y, mo, d, hour, minute, hm["zone"], False, m.group(0))


def _build(year, month, day, hour, minute, zone, year_inferred, raw):
    if not _valid(year, month, day):
        return None
    has_time = hour is not None
    hour = hour if hour is not None else 0
    minute = minute or 0
    zone = _zone(zone)
    off = utc_offset(zone, datetime.date(year, month, day))
    naive = datetime.datetime(year, month, day, hour, minute)
    aware = naive.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=off)))
    utc = aware.astimezone(datetime.timezone.utc)
    return {
        "iso": aware.isoformat(),
        "utc": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": "%04d-%02d-%02d" % (year, month, day),
        "display": _display(year, month, day, hour, minute, has_time),
        "time_display": ("%02d:%02d" % (hour, minute)) if has_time else None,
        "zone": zone,
        "offset": format_offset(off),
        "has_time": has_time,
        "precision": "minute" if has_time else "day",
        "year_inferred": year_inferred,
        "raw": raw.strip(),
    }


def _display(year, month, day, hour, minute, has_time):
    out = "%s %d, %d" % (MONTH_NAMES[month], day, year)
    if has_time:
        suffix = "AM" if hour < 12 else "PM"
        h12 = hour % 12 or 12
        out += " at %d:%02d %s" % (h12, minute, suffix)
    return out


def parse(text, hints=None, default_year=None, reference=None):
    """Parse the first date in `text`. Returns a normalised dict or None."""
    if not text or not isinstance(text, str):
        return None
    hints = year_hints(text) if hints is None else hints

    m = _ISO_RE.search(text)
    if m:
        got = _iso_parse(m, hints, default_year, reference)
        if got:
            return got

    for regex, month_first in ((_MONTH_FIRST_RE, True), (_DAY_FIRST_RE, False)):
        m = regex.search(text)
        if not m:
            continue
        mon = _month(m.group("mon"))
        if mon is None:
            continue
        day = int(m.group("d"))
        raw_y = m.group("y")
        inferred = raw_y is None
        year = int(raw_y) if raw_y else choose_year(mon, day, hints, default_year, reference)
        if year is None:
            # no year anywhere: keep the month/day, flag the gap
            tm = _time_for(text, m)
            return {
                "iso": None, "utc": None, "date": None,
                "display": "month/day known, year not stated",
                "time_display": None, "zone": tm["zone"], "offset": None,
                "has_time": tm["hour"] is not None,
                "year_inferred": True, "year_missing": True,
                "month": mon, "day": day,
                "raw": m.group(0).strip(),
            }
        tm = _time_for(text, m)
        got = _build(year, mon, day, tm["hour"], tm["minute"], tm["zone"], inferred, m.group(0))
        if got:
            got["year_missing"] = False
            return got

    m = _CJK_RE.search(text)
    if m:
        mo = int(m.group("m"))
        d = int(m.group("d"))
        raw_y = m.group("y")
        inferred = raw_y is None
        year = int(raw_y) if raw_y else choose_year(mo, d, hints, default_year, reference)
        tm = _time_for(text, m)
        if tm["hour"] is None and tm["zone"] is None:
            pre = _find_time(text[:m.start()])
            if pre["hour"] is not None:
                tm = pre
        if year is None:
            return {
                "iso": None, "utc": None, "date": None,
                "display": "month/day known, year not stated",
                "time_display": None, "zone": tm["zone"], "offset": None,
                "has_time": tm["hour"] is not None,
                "year_inferred": True, "year_missing": True,
                "month": mo, "day": d, "raw": m.group(0).strip(),
            }
        got = _build(year, mo, d, tm["hour"], tm["minute"], tm["zone"], inferred, m.group(0))
        if got:
            got["year_missing"] = False
            return got

    m = _SLASH_RE.search(text)
    if m:
        a, b = int(m.group("a")), int(m.group("b"))
        year = int(m.group("y"))
        month, day = (a, b) if a <= 12 else (b, a)
        tm = _time_for(text, m)
        got = _build(year, month, day, tm["hour"], tm["minute"], tm["zone"], False, m.group(0))
        if got:
            got["year_missing"] = False
            got["ambiguous_order"] = True
            return got
    return None


def parse_range(text, hints=None, default_year=None, reference=None):
    """Parse "September 22 - October 26, 2026" and friends."""
    if not text or not isinstance(text, str):
        return None
    parts = _RANGE_SPLIT_RE.split(text, 1)
    if len(parts) != 2:
        return None
    left, right = parts[0].strip(), parts[1].strip()
    if not left or not right:
        return None
    end = parse(right, hints=hints, default_year=default_year, reference=reference)
    if not end:
        return None
    start = parse(left, hints=hints,
                  default_year=end["date"][:4] if end.get("date") else default_year,
                  reference=reference)
    if not start:
        return None
    return {"start": start, "end": end}


def mentions(text, hints=None, default_year=None, reference=None):
    """Every date token in `text`, in order, each parsed on its own.

    The validator uses this to tell "the page states one thing and the model
    wrote another" apart from "the quote contains several dates and there is
    nothing to compare against".
    """
    spans = []
    for regex in (_ISO_RE, _CJK_RE, _MONTH_FIRST_RE, _DAY_FIRST_RE, _SLASH_RE):
        for m in regex.finditer(text or ""):
            if any(m.start() >= s[0] and m.start() < s[1] for s in spans):
                continue
            spans.append((m.start(), m.end()))
    out = []
    for start, end in sorted(spans):
        chunk = (text or "")[start:min(len(text), end + 30)]
        got = parse(chunk, hints=hints, default_year=default_year, reference=reference)
        if got:
            got["at"] = start
            out.append(got)
    return out
