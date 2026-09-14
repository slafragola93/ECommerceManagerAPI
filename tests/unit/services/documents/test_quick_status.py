import json

from src.services.documents.quick_status import (
    extract_identificativo_sdi,
    fiscal_lifecycle_from_doc,
    fiscal_quick_status_from_doc,
    map_fiscal_fatturapa_status,
    map_purchase_fatturapa_status,
    map_ricevuta_fatturapa_status,
    ricevuta_quick_status_from_entity,
)


class _Doc:
    def __init__(self, **kwargs):
        self.is_electronic = kwargs.get("is_electronic", True)
        self.status = kwargs.get("status", "pending")
        self.upload_result = kwargs.get("upload_result")
        self.mail_status = kwargs.get("mail_status")
        self.mail_error_message = kwargs.get("mail_error_message")
        self.sdi_status = kwargs.get("sdi_status")
        self.identificativo_sdi = kwargs.get("identificativo_sdi")


def test_fiscal_pending_is_null():
    status, err, sdi = map_fiscal_fatturapa_status(
        is_electronic=True, status="pending"
    )
    assert status is None
    assert err is None
    assert sdi is None


def test_fiscal_uploaded_and_sent():
    assert map_fiscal_fatturapa_status(is_electronic=True, status="uploaded")[0] == (
        "uploaded"
    )
    assert map_fiscal_fatturapa_status(is_electronic=True, status="sent")[0] == "sent"


def test_fiscal_error_with_message():
    payload = json.dumps({"status": "error", "message": "CAP non valido"})
    status, err, _ = map_fiscal_fatturapa_status(
        is_electronic=True, status="error", upload_result=payload
    )
    assert status == "error"
    assert "CAP" in (err or "")


def test_fiscal_non_electronic_null():
    status, err, _ = map_fiscal_fatturapa_status(
        is_electronic=False, status="issued"
    )
    assert status is None
    assert err is None


def test_extract_identificativo_sdi():
    payload = json.dumps({"sdi_id": "ABC123"})
    assert extract_identificativo_sdi(payload) == "ABC123"


def test_purchase_with_sdi_is_sent():
    status, err, sdi = map_purchase_fatturapa_status("SDI-99")
    assert status == "sent"
    assert err is None
    assert sdi == "SDI-99"


def test_purchase_without_sdi_null():
    assert map_purchase_fatturapa_status(None)[0] is None


def test_ricevuta_always_null_fatturapa():
    assert map_ricevuta_fatturapa_status() == (None, None, None)
    qs = ricevuta_quick_status_from_entity(None)
    assert qs["fatturapa_status"] is None
    assert qs["identificativo_sdi"] is None
    assert qs["mail_status"] is None


def test_fiscal_generated_with_rc_is_sent():
    status, err, _ = map_fiscal_fatturapa_status(
        is_electronic=True, status="generated", sdi_status="consegnata"
    )
    assert status == "sent"
    assert err is None


def test_fiscal_scartata_is_error():
    status, err, _ = map_fiscal_fatturapa_status(
        is_electronic=True, status="generated", sdi_status="scartata"
    )
    assert status == "error"
    assert "Scartata" in (err or "")


def test_fiscal_quick_status_from_doc_includes_mail_null():
    qs = fiscal_quick_status_from_doc(_Doc(status="uploaded"))
    assert qs["fatturapa_status"] == "uploaded"
    assert qs["mail_status"] is None


def test_status_is_not_a_copy_of_fatturapa_status():
    """status=generated resta workflow; fatturapa_status può essere sent/error/null."""
    pending = fiscal_quick_status_from_doc(_Doc(status="pending"))
    assert pending["fatturapa_status"] is None

    generated = fiscal_quick_status_from_doc(_Doc(status="generated"))
    assert generated["fatturapa_status"] is None

    after_rc = fiscal_quick_status_from_doc(
        _Doc(status="generated", sdi_status="consegnata")
    )
    assert after_rc["fatturapa_status"] == "sent"


def test_lifecycle_matches_flat_fields():
    doc = _Doc(
        status="generated",
        sdi_status="scartata",
        identificativo_sdi="111",
        mail_status="error",
        mail_error_message="SMTP fail",
    )
    qs = fiscal_quick_status_from_doc(doc)
    life = fiscal_lifecycle_from_doc(doc, qs)
    assert life["status"] == "generated"
    assert life["fatturapa"]["status"] == qs["fatturapa_status"] == "error"
    assert life["fatturapa"]["error_message"] == qs["fatturapa_error_message"]
    assert life["fatturapa"]["identificativo_sdi"] == "111"
    assert life["sdi"]["status"] == "scartata"
    assert life["mail"]["status"] == "error"
    assert life["mail"]["error_message"] == "SMTP fail"
