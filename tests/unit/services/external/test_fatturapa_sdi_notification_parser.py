from pathlib import Path

from src.services.external.fatturapa_sdi_notification_parser import (
    extract_progressivo_from_filename,
    is_sdi_notification_entry,
    parse_sdi_notification,
)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fatturapa_sdi"


def test_parse_rc():
    parsed = parse_sdi_notification((FIXTURES / "rc_sample.xml").read_text(encoding="utf-8"))
    assert parsed["notification_type"] == "RC"
    assert parsed["sdi_status"] == "consegnata"
    assert parsed["identificativo_sdi"] == "1111111111"
    assert parsed["progressivo_invio"] == "000001"


def test_parse_ns():
    parsed = parse_sdi_notification((FIXTURES / "ns_sample.xml").read_text(encoding="utf-8"))
    assert parsed["notification_type"] == "NS"
    assert parsed["sdi_status"] == "scartata"
    assert "00300" in (parsed["message"] or "")


def test_parse_mc():
    parsed = parse_sdi_notification((FIXTURES / "mc_sample.xml").read_text(encoding="utf-8"))
    assert parsed["notification_type"] == "MC"
    assert parsed["sdi_status"] == "mancata_consegna"


def test_parse_ne_accepted():
    parsed = parse_sdi_notification((FIXTURES / "ne_ec01_sample.xml").read_text(encoding="utf-8"))
    assert parsed["notification_type"] == "NE"
    assert parsed["sdi_status"] == "accettata"


def test_parse_ne_rejected():
    parsed = parse_sdi_notification((FIXTURES / "ne_ec02_sample.xml").read_text(encoding="utf-8"))
    assert parsed["sdi_status"] == "rifiutata"


def test_parse_dt():
    parsed = parse_sdi_notification((FIXTURES / "dt_sample.xml").read_text(encoding="utf-8"))
    assert parsed["notification_type"] == "DT"
    assert parsed["sdi_status"] == "decorrenza_termini"


def test_at_alias_from_filename():
    parsed = parse_sdi_notification(
        None, nome_file="IT08632861210_000009_AT_001.xml", identificativo_sdi="99"
    )
    assert parsed["notification_type"] == "DT"
    assert parsed["sdi_status"] == "decorrenza_termini"


def test_progressivo_from_notification_filename():
    assert extract_progressivo_from_filename("IT08632861210_000099_RC_001.xml") == (
        "000099"
    )


def test_acquisto_entries_are_ignored():
    assert is_sdi_notification_entry({"Direzione": "Acquisto", "Tipo": "Notifica"}) is False
    assert is_sdi_notification_entry(
        {"Direzione": "Vendita", "Tipo": "Notifica", "NomeFile": "IT08632861210_000001_RC_001.xml"}
    ) is True
