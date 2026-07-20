"""Test naming file XML FatturaPA."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from src.services.external.fatturapa_filename import (
    build_fatturapa_filename,
    extract_dati_trasmissione,
    normalize_id_codice,
    resolve_fatturapa_filename_from_xml,
)

REFERENCE_ZIP = Path(r"c:\Users\webmarke22\.docker\Downloads\ITIT08632861210_101164.zip")

REFERENCE_XML_SNIPPET = """<?xml version="1.0" encoding="utf-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2" versione="FPR12">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <IdTrasmittente>
        <IdPaese>IT</IdPaese>
        <IdCodice>08632861210</IdCodice>
      </IdTrasmittente>
      <ProgressivoInvio>101164</ProgressivoInvio>
    </DatiTrasmissione>
  </FatturaElettronicaHeader>
</p:FatturaElettronica>
"""


class TestFatturapaFilename:
    def test_normalize_id_codice_strips_country_prefix(self):
        assert normalize_id_codice("IT08632861210") == "08632861210"
        assert normalize_id_codice("08632861210") == "08632861210"

    def test_build_fatturapa_filename_official_format(self):
        assert build_fatturapa_filename("IT", "08632861210", "101164") == (
            "IT08632861210_101164.xml"
        )
        assert build_fatturapa_filename("IT", "IT08632861210", "000001") == (
            "IT08632861210_000001.xml"
        )

    def test_extract_dati_trasmissione_from_snippet(self):
        paese, codice, progressivo = extract_dati_trasmissione(REFERENCE_XML_SNIPPET)
        assert paese == "IT"
        assert codice == "08632861210"
        assert progressivo == "101164"

    def test_resolve_filename_from_snippet(self):
        assert resolve_fatturapa_filename_from_xml(REFERENCE_XML_SNIPPET) == (
            "IT08632861210_101164.xml"
        )

    @pytest.mark.skipif(not REFERENCE_ZIP.exists(), reason="ZIP di riferimento non presente")
    def test_resolve_filename_from_reference_zip(self):
        with zipfile.ZipFile(REFERENCE_ZIP) as archive:
            xml_name = archive.namelist()[0]
            xml_content = archive.read(xml_name).decode("utf-8")

        resolved = resolve_fatturapa_filename_from_xml(
            xml_content,
            fallback_filename=xml_name,
        )
        assert resolved == "IT08632861210_101164.xml"
        paese, codice, progressivo = extract_dati_trasmissione(xml_content)
        assert (paese, codice, progressivo) == ("IT", "08632861210", "101164")
