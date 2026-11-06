"""Tests for nldate.parse."""

from datetime import date

import pytest

from nldate import parse

TODAY = date(2025, 11, 6)  # Thursday


def test_today() -> None:
    assert parse("today", today=TODAY) == TODAY


def test_tomorrow_yesterday() -> None:
    assert parse("tomorrow", today=TODAY) == date(2025, 11, 7)
    assert parse("yesterday", today=TODAY) == date(2025, 11, 5)


def test_absolute_named_date() -> None:
    assert parse("December 1st, 2025", today=TODAY) == date(2025, 12, 1)
    assert parse("December 1, 2025", today=TODAY) == date(2025, 12, 1)


def test_iso_and_numeric() -> None:
    assert parse("2025-12-01", today=TODAY) == date(2025, 12, 1)
    assert parse("12/1/2025", today=TODAY) == date(2025, 12, 1)


def test_next_weekday() -> None:
    # TODAY is Thursday; next Tuesday is Nov 11
    assert parse("next Tuesday", today=TODAY) == date(2025, 11, 11)


def test_last_weekday() -> None:
    assert parse("last Monday", today=TODAY) == date(2025, 11, 3)


def test_days_before_absolute() -> None:
    assert parse("5 days before December 1st, 2025", today=TODAY) == date(2025, 11, 26)


def test_duration_after_relative() -> None:
    # yesterday = Nov 5, 2025; +1 year +2 months = Jan 5, 2027
    assert parse("1 year and 2 months after yesterday", today=TODAY) == date(2027, 1, 5)


def test_in_n_days_and_from() -> None:
    assert parse("in 3 days", today=TODAY) == date(2025, 11, 9)
    assert parse("two weeks from tomorrow", today=TODAY) == date(2025, 11, 21)


def test_ago() -> None:
    assert parse("3 days ago", today=TODAY) == date(2025, 11, 3)


def test_empty_and_invalid_raise() -> None:
    with pytest.raises(ValueError):
        parse("", today=TODAY)
    with pytest.raises(ValueError):
        parse("   ", today=TODAY)
    with pytest.raises(ValueError):
        parse("not a date", today=TODAY)


def test_defaults_today_parameter() -> None:
    # When today is omitted, result for "today" should be the real current date.
    assert parse("today") == date.today()
