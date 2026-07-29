from decimal import Decimal
from pathlib import Path

from src.services.external.fatturapa_inbound_parser import parse_fatturapa_inbound

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fatturapa_inbound"


def test_parse_td01_header_and_lines():
    xml = (FIXTURES / "td01_sample.xml").read_text(encoding="utf-8")
    parsed = parse_fatturapa_inbound(xml)

    assert parsed["tipo_documento"] == "TD01"
    assert parsed["numero_documento"] == "123/2026"
    assert str(parsed["data_documento"]) == "2026-07-15"
    assert parsed["fornitore_denominazione"] == "Fornitore Test SpA"
    assert parsed["fornitore_piva"] == "IT01234567890"
    assert parsed["importo_totale"] == Decimal("1220.00")
    assert parsed["fattura_collegata_numero"] is None

    assert len(parsed["details"]) == 2
    assert parsed["details"][0]["descrizione"] == "Abbonamento hosting annuale"
    assert parsed["details"][0]["quantita"] == Decimal("1.00")
    assert parsed["details"][1]["codice_articolo"] == "SKU-001"
    assert parsed["details"][1]["unita_misura"] == "NR"


def test_parse_td04_with_linked_invoice():
    xml = (FIXTURES / "td04_sample.xml").read_text(encoding="utf-8")
    parsed = parse_fatturapa_inbound(xml)

    assert parsed["tipo_documento"] == "TD04"
    assert parsed["numero_documento"] == "NC-5/2026"
    assert parsed["fornitore_denominazione"] == "Fornitore NC Srl"
    assert parsed["fattura_collegata_numero"] == "123/2026"
    assert str(parsed["fattura_collegata_data"]) == "2026-07-15"
    assert len(parsed["details"]) == 2
    assert parsed["details"][1]["natura"] == "N1"


def test_parse_empty_returns_defaults():
    parsed = parse_fatturapa_inbound("")
    assert parsed["details"] == []
    assert parsed["tipo_documento"] is None
