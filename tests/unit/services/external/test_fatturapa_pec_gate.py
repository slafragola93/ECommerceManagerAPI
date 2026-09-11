"""Gate PEC prima di send_to_sdi=true."""
from src.services.external.fatturapa_pec_gate import (
    extract_sdi_recapito,
    pec_gate_error,
)

XML_XXXXXXX_NO_PEC = """<?xml version="1.0"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <CodiceDestinatario>XXXXXXX</CodiceDestinatario>
    </DatiTrasmissione>
  </FatturaElettronicaHeader>
</p:FatturaElettronica>
"""

XML_XXXXXXX_WITH_PEC = """<?xml version="1.0"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <CodiceDestinatario>XXXXXXX</CodiceDestinatario>
      <PECDestinatario>cliente@pec.example.com</PECDestinatario>
    </DatiTrasmissione>
  </FatturaElettronicaHeader>
</p:FatturaElettronica>
"""

XML_B2C_NO_PEC = """<?xml version="1.0"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <CodiceDestinatario>0000000</CodiceDestinatario>
    </DatiTrasmissione>
  </FatturaElettronicaHeader>
</p:FatturaElettronica>
"""

XML_SDI_CODE = """<?xml version="1.0"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <CodiceDestinatario>ABC1234</CodiceDestinatario>
    </DatiTrasmissione>
  </FatturaElettronicaHeader>
</p:FatturaElettronica>
"""

XML_BAD_PEC = """<?xml version="1.0"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <CodiceDestinatario>XXXXXXX</CodiceDestinatario>
      <PECDestinatario>not-an-email</PECDestinatario>
    </DatiTrasmissione>
  </FatturaElettronicaHeader>
</p:FatturaElettronica>
"""


def test_extract_codice_and_pec():
    codice, pec = extract_sdi_recapito(XML_XXXXXXX_WITH_PEC)
    assert codice == "XXXXXXX"
    assert pec == "cliente@pec.example.com"


def test_block_xxxxxxx_without_pec():
    error = pec_gate_error(XML_XXXXXXX_NO_PEC)
    assert error is not None
    assert error["rule"] == "pec_gate"
    assert error["field"] == "PECDestinatario"


def test_allow_xxxxxxx_with_pec():
    assert pec_gate_error(XML_XXXXXXX_WITH_PEC) is None


def test_allow_b2c_0000000_without_pec():
    assert pec_gate_error(XML_B2C_NO_PEC) is None


def test_allow_seven_char_sdi_code_without_pec():
    assert pec_gate_error(XML_SDI_CODE) is None


def test_block_invalid_pec_format():
    error = pec_gate_error(XML_BAD_PEC)
    assert error is not None
    assert error["rule"] == "pec_gate_formato"
