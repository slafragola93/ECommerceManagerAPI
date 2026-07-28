"""Validazione XML FatturaPA contro lo schema XSD ufficiale v1.2."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from lxml import etree

logger = logging.getLogger(__name__)

FATTURAPA_NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

# resources/fatturapa/xsd/ — root progetto = parents[3] da src/services/external/
_XSD_DIR = Path(__file__).resolve().parents[3] / "resources" / "fatturapa" / "xsd"
_SCHEMA_FILENAME = "Schema_del_file_xml_FatturaPA_versione_1.2.xsd"


def get_xsd_path() -> Path:
    """Percorso assoluto dello schema FatturaPA v1.2 vendored."""
    return _XSD_DIR / _SCHEMA_FILENAME


@lru_cache(maxsize=1)
def _load_schema() -> etree.XMLSchema:
    schema_path = get_xsd_path()
    if not schema_path.is_file():
        raise FileNotFoundError(
            f"Schema XSD FatturaPA non trovato: {schema_path}. "
            "Verificare resources/fatturapa/xsd/"
        )
    # base_url consente di risolvere xmldsig-core-schema.xsd nella stessa cartella
    parser = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)
    with schema_path.open("rb") as fh:
        schema_doc = etree.parse(fh, parser)
    return etree.XMLSchema(schema_doc)


def validate_fatturapa_xml(xml_content: Union[str, bytes]) -> Dict[str, Any]:
    """
    Valida l'XML generato contro lo XSD ufficiale FatturaPA v1.2.

    Returns:
        ``{"valid": bool, "errors": [{"field", "message", "rule", "value"}, ...]}``
    """
    errors: List[Dict[str, Any]] = []
    try:
        if isinstance(xml_content, str):
            xml_bytes = xml_content.encode("utf-8")
        else:
            xml_bytes = xml_content

        parser = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)
        doc = etree.fromstring(xml_bytes, parser)
        schema = _load_schema()

        if schema.validate(doc):
            return {"valid": True, "errors": []}

        for err in schema.error_log:
            errors.append(
                {
                    "field": f"XSD:line:{err.line}",
                    "message": err.message,
                    "rule": "xsd",
                    "value": err.path or None,
                }
            )
    except etree.XMLSyntaxError as exc:
        errors.append(
            {
                "field": "XSD:syntax",
                "message": str(exc),
                "rule": "xsd_syntax",
                "value": None,
            }
        )
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        errors.append(
            {
                "field": "XSD:schema",
                "message": str(exc),
                "rule": "xsd_schema_missing",
                "value": None,
            }
        )
    except Exception as exc:  # pragma: no cover - errori imprevisti schema/lib
        logger.exception("Errore validazione XSD FatturaPA")
        errors.append(
            {
                "field": "XSD:internal",
                "message": str(exc),
                "rule": "xsd_internal",
                "value": None,
            }
        )

    return {"valid": len(errors) == 0, "errors": errors}


def clear_schema_cache() -> None:
    """Invalida la cache dello schema (test / reload)."""
    _load_schema.cache_clear()
