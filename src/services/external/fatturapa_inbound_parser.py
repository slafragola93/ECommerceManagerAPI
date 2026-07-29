"""Parser XML FatturaPA inbound (ciclo passivo / documenti ricevuti)."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from src.services.external.fatturapa_filename import local_tag

logger = logging.getLogger(__name__)


def _text(element: Optional[ET.Element]) -> Optional[str]:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def _find_child(parent: ET.Element, name: str) -> Optional[ET.Element]:
    for child in parent:
        if local_tag(child) == name:
            return child
    return None


def _find_all(parent: ET.Element, name: str) -> List[ET.Element]:
    return [child for child in parent if local_tag(child) == name]


def _find_desc(root: ET.Element, name: str) -> Optional[ET.Element]:
    for element in root.iter():
        if local_tag(element) == name:
            return element
    return None


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_decimal(value: Optional[str]) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(value.replace(",", ".").strip())
    except (InvalidOperation, AttributeError):
        return None


def _extract_cedente(root: ET.Element) -> Dict[str, Optional[str]]:
    cedente = _find_desc(root, "CedentePrestatore")
    if cedente is None:
        return {"fornitore_denominazione": None, "fornitore_piva": None}

    dati = _find_child(cedente, "DatiAnagrafici") or cedente
    anagrafica = _find_child(dati, "Anagrafica")
    denominazione = None
    if anagrafica is not None:
        denominazione = _text(_find_child(anagrafica, "Denominazione"))
        if not denominazione:
            nome = _text(_find_child(anagrafica, "Nome")) or ""
            cognome = _text(_find_child(anagrafica, "Cognome")) or ""
            denominazione = f"{nome} {cognome}".strip() or None

    id_fiscale = _find_child(dati, "IdFiscaleIVA")
    piva = None
    if id_fiscale is not None:
        paese = _text(_find_child(id_fiscale, "IdPaese")) or ""
        codice = _text(_find_child(id_fiscale, "IdCodice")) or ""
        if codice:
            piva = f"{paese}{codice}" if paese else codice

    if not piva:
        piva = _text(_find_child(dati, "CodiceFiscale"))

    return {
        "fornitore_denominazione": denominazione,
        "fornitore_piva": piva,
    }


def _extract_dati_generali(root: ET.Element) -> Dict[str, Any]:
    doc = _find_desc(root, "DatiGeneraliDocumento")
    result: Dict[str, Any] = {
        "tipo_documento": None,
        "numero_documento": None,
        "data_documento": None,
        "importo_totale": None,
        "fattura_collegata_numero": None,
        "fattura_collegata_data": None,
    }
    if doc is not None:
        result["tipo_documento"] = _text(_find_child(doc, "TipoDocumento"))
        result["numero_documento"] = _text(_find_child(doc, "Numero"))
        result["data_documento"] = _parse_date(_text(_find_child(doc, "Data")))
        result["importo_totale"] = _parse_decimal(
            _text(_find_child(doc, "ImportoTotaleDocumento"))
        )

    collegata = _find_desc(root, "DatiFattureCollegate")
    if collegata is not None:
        result["fattura_collegata_numero"] = _text(_find_child(collegata, "IdDocumento"))
        result["fattura_collegata_data"] = _parse_date(
            _text(_find_child(collegata, "Data"))
        )

    return result


def _extract_linee(root: ET.Element) -> List[Dict[str, Any]]:
    lines: List[Dict[str, Any]] = []
    for linea in root.iter():
        if local_tag(linea) != "DettaglioLinee":
            continue

        codice_articolo = None
        codice_nodes = _find_all(linea, "CodiceArticolo")
        if codice_nodes:
            codice_articolo = _text(_find_child(codice_nodes[0], "CodiceValore"))

        numero_raw = _text(_find_child(linea, "NumeroLinea"))
        try:
            numero_linea = int(numero_raw) if numero_raw else len(lines) + 1
        except ValueError:
            numero_linea = len(lines) + 1

        quantita = _parse_decimal(_text(_find_child(linea, "Quantita")))
        if quantita is None:
            quantita = Decimal("1")

        lines.append(
            {
                "numero_linea": numero_linea,
                "descrizione": _text(_find_child(linea, "Descrizione")),
                "codice_articolo": codice_articolo,
                "quantita": quantita,
                "unita_misura": _text(_find_child(linea, "UnitaMisura")),
                "prezzo_unitario": _parse_decimal(
                    _text(_find_child(linea, "PrezzoUnitario"))
                ),
                "prezzo_totale": _parse_decimal(
                    _text(_find_child(linea, "PrezzoTotale"))
                ),
                "aliquota_iva": _parse_decimal(
                    _text(_find_child(linea, "AliquotaIVA"))
                ),
                "natura": _text(_find_child(linea, "Natura")),
            }
        )
    return lines


def parse_fatturapa_inbound(xml_content: str) -> Dict[str, Any]:
    """
    Estrae header consultazione + righe DettaglioLinee da XML FatturaPA.

    Returns:
        Dict con chiavi header e lista ``details``.
    """
    empty: Dict[str, Any] = {
        "tipo_documento": None,
        "numero_documento": None,
        "data_documento": None,
        "fornitore_denominazione": None,
        "fornitore_piva": None,
        "importo_totale": None,
        "fattura_collegata_numero": None,
        "fattura_collegata_data": None,
        "details": [],
    }
    if not xml_content or not xml_content.strip():
        return empty

    content = xml_content.strip()
    if not content.startswith("<"):
        start = content.find("<?xml")
        if start < 0:
            start = content.find("<")
        if start >= 0:
            content = content[start:]
        else:
            logger.warning("Contenuto non XML: parsing inbound saltato")
            return empty

    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        logger.warning("XML FatturaPA inbound non valido: %s", exc)
        return empty

    result = dict(empty)
    result.update(_extract_cedente(root))
    result.update(_extract_dati_generali(root))
    result["details"] = _extract_linee(root)
    return result
