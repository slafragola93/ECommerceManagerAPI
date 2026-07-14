"""Test utility date emissione ricevute."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from src.schemas.ricevuta_schema import RicevutaCreateSchema
from src.services.ricevute.date_utils import (
    emission_for_pdf,
    emission_to_rome,
    format_emission_datetime,
    normalize_emission_datetime,
    parse_emission_input,
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


@pytest.mark.parametrize(
    "raw,expected_type",
    [
        ("2026-07-08", date),
        ("2026-07-08T14:30:00", datetime),
        ("2026-07-08T14:30:00Z", datetime),
        (date(2026, 7, 8), date),
        (datetime(2026, 7, 8, 14, 30), datetime),
    ],
)
def test_parse_emission_input(raw, expected_type):
    parsed = parse_emission_input(raw)
    assert isinstance(parsed, expected_type)


def test_emission_to_rome_accepts_date_object():
    local = emission_to_rome(date(2026, 7, 8))
    assert local.tzinfo == ROME
    assert local.date() == date(2026, 7, 8)
    assert local.hour == 0
    assert local.minute == 0


def test_format_emission_datetime_accepts_date_object():
    assert format_emission_datetime(date(2026, 7, 8)) == "08/07/2026 00:00"


def test_emission_for_pdf_from_date_and_stored_datetime():
    from_date = emission_for_pdf(date(2026, 7, 8))
    assert from_date.tzinfo == ROME
    assert from_date.date() == date(2026, 7, 8)
    assert from_date.hour == 0
    assert from_date.minute == 0

    stored = (
        datetime(2026, 7, 8, 12, 30, tzinfo=ROME)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
    from_stored = emission_for_pdf(stored)
    assert from_stored.tzinfo == ROME
    assert from_stored.hour == 12
    assert from_stored.minute == 30


def test_create_schema_parses_date_only_string_as_date():
    schema = RicevutaCreateSchema.model_validate(
        {"id_order": 1, "data_emissione": "2026-07-08"}
    )
    assert isinstance(schema.data_emissione, date)
    assert not isinstance(schema.data_emissione, datetime)


def test_create_schema_parses_iso_datetime_string():
    schema = RicevutaCreateSchema.model_validate(
        {"id_order": 1, "data_emissione": "2026-07-08T14:30:00"}
    )
    assert isinstance(schema.data_emissione, datetime)
    assert schema.data_emissione.hour == 14
    assert schema.data_emissione.minute == 30
