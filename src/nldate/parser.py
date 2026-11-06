"""Parse natural-language date strings into ``datetime.date`` objects."""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

_WORD_NUMBERS: dict[str, int] = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_MONTHS: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_WEEKDAYS: dict[str, int] = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

_UNIT_ALIASES: dict[str, str] = {
    "day": "days",
    "days": "days",
    "week": "weeks",
    "weeks": "weeks",
    "month": "months",
    "months": "months",
    "year": "years",
    "years": "years",
}


def parse(s: str, today: date | None = None) -> date:
    """Parse a natural-language date string into a ``date``.

    Raises:
        ValueError: If ``s`` is empty or not a recognized date expression.
    """
    if today is None:
        today = date.today()

    if not isinstance(s, str) or not s.strip():
        raise ValueError("empty or invalid date string")

    text = _normalize(s)
    try:
        return _parse_normalized(text, today)
    except ValueError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"could not parse date: {s!r}") from exc


def _normalize(s: str) -> str:
    text = s.strip().lower()
    text = text.replace(",", " ")
    # Drop abbreviation periods (e.g. "Dec." -> "Dec").
    text = text.replace(".", " ")
    text = re.sub(r"\s+", " ", text)
    # Drop leading "on " / "the " noise that often wraps dates.
    text = re.sub(r"^(on|the)\s+", "", text)
    return text.strip()


def _parse_normalized(text: str, today: date) -> date:
    # "<duration> before|after <anchor>"
    m = re.fullmatch(
        r"(.+?)\s+(before|after)\s+(.+)",
        text,
    )
    if m:
        duration_text, direction, anchor_text = m.groups()
        anchor = _parse_normalized(anchor_text, today)
        delta = _parse_duration(duration_text)
        return _apply_duration(anchor, delta, sign=-1 if direction == "before" else 1)

    # "<duration> from <anchor>" / "<duration> from now"
    m = re.fullmatch(r"(.+?)\s+from\s+(.+)", text)
    if m:
        duration_text, anchor_text = m.groups()
        if anchor_text == "now":
            anchor = today
        else:
            anchor = _parse_normalized(anchor_text, today)
        delta = _parse_duration(duration_text)
        return _apply_duration(anchor, delta, sign=1)

    # "in <duration>" / "in <duration> from now"
    m = re.fullmatch(r"in\s+(.+?)(?:\s+from\s+now)?", text)
    if m:
        delta = _parse_duration(m.group(1))
        return _apply_duration(today, delta, sign=1)

    # "<duration> ago"
    m = re.fullmatch(r"(.+?)\s+ago", text)
    if m:
        delta = _parse_duration(m.group(1))
        return _apply_duration(today, delta, sign=-1)

    # Simple relative keywords
    if text == "today":
        return today
    if text == "tomorrow":
        return today + timedelta(days=1)
    if text == "yesterday":
        return today - timedelta(days=1)
    if text in {"day after tomorrow", "the day after tomorrow"}:
        return today + timedelta(days=2)
    if text in {"day before yesterday", "the day before yesterday"}:
        return today - timedelta(days=2)

    # next/last/this week|month|year
    m = re.fullmatch(r"(next|last|this)\s+(week|month|year)", text)
    if m:
        return _relative_period(m.group(1), m.group(2), today)

    # next/last/this <weekday>
    m = re.fullmatch(r"(next|last|this)\s+([a-z]+)", text)
    if m and m.group(2) in _WEEKDAYS:
        return _relative_weekday(m.group(1), _WEEKDAYS[m.group(2)], today)

    # bare weekday -> next occurrence (today counts)
    if text in _WEEKDAYS:
        return _relative_weekday("this", _WEEKDAYS[text], today)

    absolute = _try_parse_absolute(text, today)
    if absolute is not None:
        return absolute

    raise ValueError(f"unrecognized date: {text!r}")


def _parse_number(token: str) -> int:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    if token in _WORD_NUMBERS:
        return _WORD_NUMBERS[token]
    # compound like "twenty one" / "twenty-one"
    token = token.replace("-", " ")
    parts = token.split()
    if len(parts) == 2 and parts[0] in _WORD_NUMBERS and parts[1] in _WORD_NUMBERS:
        return _WORD_NUMBERS[parts[0]] + _WORD_NUMBERS[parts[1]]
    raise ValueError(f"not a number: {token!r}")


def _parse_duration(text: str) -> dict[str, int]:
    """Parse a duration like '5 days', '1 year and 2 months', 'two weeks'."""
    text = text.strip().lower()
    text = re.sub(r"\s+and\s+", " ", text)
    text = re.sub(r",", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Allow a trailing "time" as in "in three years time"
    text = re.sub(r"\s+time$", "", text)

    pattern = re.compile(
        r"([a-z0-9\-]+(?:\s+[a-z0-9\-]+)?)\s+"
        r"(days?|weeks?|months?|years?)"
    )
    matches = list(pattern.finditer(text))
    if not matches:
        raise ValueError(f"unrecognized duration: {text!r}")

    # Ensure the whole string is consumed by duration parts (allowing spaces).
    consumed = " ".join(m.group(0) for m in matches)
    if re.sub(r"\s+", " ", consumed) != text:
        # Also accept if leftover is empty after joining match spans.
        rebuilt = text
        for m in matches:
            rebuilt = rebuilt.replace(m.group(0), "", 1)
        if rebuilt.strip():
            raise ValueError(f"unrecognized duration: {text!r}")

    result: dict[str, int] = {"days": 0, "weeks": 0, "months": 0, "years": 0}
    for m in matches:
        amount = _parse_number(m.group(1))
        unit = _UNIT_ALIASES[m.group(2)]
        result[unit] += amount
    return result


def _apply_duration(base: date, delta: dict[str, int], *, sign: int) -> date:
    years = sign * delta.get("years", 0)
    months = sign * delta.get("months", 0)
    days = sign * (delta.get("days", 0) + 7 * delta.get("weeks", 0))
    result = _add_months(base, years * 12 + months)
    return result + timedelta(days=days)


def _add_months(base: date, months: int) -> date:
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _relative_weekday(modifier: str, target_weekday: int, today: date) -> date:
    current = today.weekday()
    if modifier == "next":
        # Always the weekday in the following week sense: strictly after today,
        # and if that day is later this week, still go to next week's occurrence
        # when "next" is used colloquially as "the coming <day>".
        # Common calendar-app behavior: next <weekday> is the soonest future
        # occurrence strictly after today (if today is that weekday, +7).
        days_ahead = (target_weekday - current) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)
    if modifier == "last":
        days_behind = (current - target_weekday) % 7
        if days_behind == 0:
            days_behind = 7
        return today - timedelta(days=days_behind)
    # "this" / bare weekday: soonest occurrence on or after today
    days_ahead = (target_weekday - current) % 7
    return today + timedelta(days=days_ahead)


def _relative_period(modifier: str, unit: str, today: date) -> date:
    if unit == "week":
        # Return the Monday of the referenced week (ISO-like, week starts Monday).
        monday = today - timedelta(days=today.weekday())
        if modifier == "this":
            return monday
        if modifier == "next":
            return monday + timedelta(days=7)
        return monday - timedelta(days=7)
    if unit == "month":
        if modifier == "this":
            return date(today.year, today.month, 1)
        if modifier == "next":
            return _add_months(date(today.year, today.month, 1), 1)
        return _add_months(date(today.year, today.month, 1), -1)
    # year
    if modifier == "this":
        return date(today.year, 1, 1)
    if modifier == "next":
        return date(today.year + 1, 1, 1)
    return date(today.year - 1, 1, 1)


def _strip_ordinal(day_text: str) -> int:
    day_text = day_text.lower()
    day_text = re.sub(r"(st|nd|rd|th)$", "", day_text)
    if not day_text.isdigit():
        raise ValueError(f"invalid day: {day_text!r}")
    return int(day_text)


def _try_parse_absolute(text: str, today: date) -> date | None:
    # Year-first: YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # Numeric: M/D/YYYY or M-D-YYYY (also D/M/YYYY when day > 12 is unambiguous)
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", text)
    if m:
        a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # Prefer US M/D/YYYY when both are plausible.
        if 1 <= a <= 12 and 1 <= b <= 31:
            try:
                return date(year, a, b)
            except ValueError:
                pass
        if 1 <= b <= 12 and 1 <= a <= 31:
            return date(year, b, a)
        raise ValueError(f"invalid numeric date: {text!r}")

    # Month name first: "december 1st 2025", "dec 1, 2025", "december 1"
    m = re.fullmatch(
        r"([a-z]+)\s+(\d{1,2}(?:st|nd|rd|th)?)\s*(\d{4})?",
        text,
    )
    if m and m.group(1) in _MONTHS:
        month = _MONTHS[m.group(1)]
        day = _strip_ordinal(m.group(2))
        year = int(m.group(3)) if m.group(3) else _infer_year(today, month, day)
        return date(year, month, day)

    # Day first: "1st december 2025", "1 december", "1st of december 2025"
    m = re.fullmatch(
        r"(\d{1,2}(?:st|nd|rd|th)?)\s+(?:of\s+)?([a-z]+)\s*(\d{4})?",
        text,
    )
    if m and m.group(2) in _MONTHS:
        day = _strip_ordinal(m.group(1))
        month = _MONTHS[m.group(2)]
        year = int(m.group(3)) if m.group(3) else _infer_year(today, month, day)
        return date(year, month, day)

    # Month Year only -> first of that month: "december 2025"
    m = re.fullmatch(r"([a-z]+)\s+(\d{4})", text)
    if m and m.group(1) in _MONTHS:
        return date(int(m.group(2)), _MONTHS[m.group(1)], 1)

    return None


def _infer_year(today: date, month: int, day: int) -> int:
    """Pick this year, or next year if the date has already passed."""
    try:
        candidate = date(today.year, month, day)
    except ValueError:
        # e.g. Feb 29 on non-leap year — try next year
        return today.year + 1
    if candidate < today:
        return today.year + 1
    return today.year
