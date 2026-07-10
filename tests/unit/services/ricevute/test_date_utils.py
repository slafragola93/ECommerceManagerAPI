"""Test utility date emissione ricevute."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.services.ricevute.date_utils import (
    emission_to_rome,
    format_emission_datetime,
    normalize_emission_datetime,
    utc_naive_end_of_day,
    utc_naive_start_of_day,
)

ROME = ZoneInfo("Europe/Rome")
UTC = ZoneInfo("UTC")


def test_normalize_emission_datetime_default_now():
    result = normalize_emission_datetime(None)
    assert isinstance(result, datetime)
    assert result.tzinfo is None


def test_normalize_emission_datetime_from_date():
    result = normalize_emission_datetime(date(2026, 7, 8))
    local = emission_to_rome(result)
    assert local.date() == date(2026, 7, 8)


def test_normalize_emission_datetime_from_naive_datetime():
    naive = datetime(2026, 7, 8, 14, 30)
    result = normalize_emission_datetime(naive)
    local = emission_to_rome(result)
    assert local.hour == 14
    assert local.minute == 30


def test_format_emission_datetime_includes_time():
    stored = (
        datetime(2026, 7, 8, 12, 30, tzinfo=ROME)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
    assert format_emission_datetime(stored) == "08/07/2026 12:30"


def test_utc_naive_day_bounds():
    start = utc_naive_start_of_day(date(2026, 7, 8))
    end = utc_naive_end_of_day(date(2026, 7, 8))
    assert emission_to_rome(start).date() == date(2026, 7, 8)
    assert emission_to_rome(end).date() == date(2026, 7, 8)
    assert end > start
