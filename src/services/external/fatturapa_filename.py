"""Utility nome file XML FatturaPA (formato SDI).

Regola ufficiale:
    [IdPaese][IdCodice]_[ProgressivoInvio].xml

Esempio: IdPaese=IT, IdCodice=08632861210, ProgressivoInvio=101164
         → IT08632861210_101164.xml
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Optional, Tuple

FATTURAPA_NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"


def local_tag(element: ET.Element) -> str:
    tag = element.tag
    return tag.split("}")[-1] if "}" in tag else tag


def normalize_id_codice(value: Optional[str]) -> str:
    """Normalizza IdCodice trasmittente (11 cifre P.IVA IT, senza prefisso paese)."""
    cleaned = re.sub(r"\s+", "", (value or "")).upper()
    if cleaned.startswith("IT"):
        cleaned = cleaned[2:]
    return cleaned


def build_fatturapa_filename(
    id_paese: str,
    id_codice: str,
    progressivo_invio: str,
) -> str:
    paese = (id_paese or "IT").strip().upper()
    codice = normalize_id_codice(id_codice)
    progressivo = re.sub(r"[^\w.-]", "", str(progressivo_invio or "").strip())
    if not paese or not codice or not progressivo:
        raise ValueError("IdPaese, IdCodice e ProgressivoInvio sono obbligatori")
    return f"{paese}{codice}_{progressivo}.xml"


def extract_dati_trasmissione(xml_content: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Estrae IdPaese, IdCodice (trasmittente) e ProgressivoInvio dall'XML."""
    root = ET.fromstring(xml_content)

    id_paese: Optional[str] = None
    id_codice: Optional[str] = None
    progressivo: Optional[str] = None
    in_dati_trasmissione = False
    in_id_trasmittente = False

    for element in root.iter():
        tag = local_tag(element)

        if tag == "DatiTrasmissione":
            in_dati_trasmissione = True
            continue

        if not in_dati_trasmissione:
            continue

        if tag == "IdTrasmittente":
            in_id_trasmittente = True
            continue

        if in_id_trasmittente:
            if tag == "IdPaese" and element.text:
                id_paese = element.text.strip()
            elif tag == "IdCodice" and element.text:
                id_codice = element.text.strip()
            elif tag not in {"IdPaese", "IdCodice"}:
                in_id_trasmittente = False

        if tag == "ProgressivoInvio" and element.text and progressivo is None:
            progressivo = element.text.strip()

    return id_paese, id_codice, progressivo


def ensure_xml_filename(filename: Optional[str], fallback: str = "fattura.xml") -> str:
    name = (filename or fallback).strip().replace("\\", "/").split("/")[-1]
    if not name.lower().endswith(".xml"):
        name = f"{name}.xml"
    return name


def resolve_fatturapa_filename_from_xml(
    xml_content: str,
    *,
    fallback_filename: Optional[str] = None,
    default_id_codice: Optional[str] = None,
) -> str:
    """
    Deriva il nome file SDI dal contenuto XML FatturaPA.
    Fallback su filename salvato in DB se il parsing fallisce.
    """
    try:
        id_paese, id_codice, progressivo = extract_dati_trasmissione(xml_content)
        if id_codice and progressivo:
            return build_fatturapa_filename(
                id_paese or "IT",
                id_codice or default_id_codice or "",
                progressivo,
            )
    except ET.ParseError:
        pass

    if fallback_filename:
        return ensure_xml_filename(fallback_filename)

    raise ValueError("Impossibile derivare il nome file XML FatturaPA")


def normalize_xml_bytes(xml_content: str) -> bytes:
    """Serializza l'XML in UTF-8 per export (senza BOM)."""
    return xml_content.encode("utf-8")
