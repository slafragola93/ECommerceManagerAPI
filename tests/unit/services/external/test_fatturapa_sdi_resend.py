"""Regole send-to-sdi / retry-send / generate-xml dopo NS."""
from types import SimpleNamespace

from src.services.external.fatturapa_sdi_resend import (
    api_sdi_send_disabled_reason,
    generate_xml_block_reason,
    invoice_edit_block_reason,
    is_sdi_api_send_enabled,
    reset_xml_block_reason,
    retry_send_block_reason,
    send_to_sdi_block_reason,
)


def _doc(**kwargs):
    defaults = {
        "is_electronic": True,
        "status": "generated",
        "sdi_status": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestSendToSdiBlock:
    def test_generated_ok(self):
        assert send_to_sdi_block_reason(_doc()) is None

    def test_uploaded_ok(self):
        assert send_to_sdi_block_reason(_doc(status="uploaded")) is None

    def test_error_ok(self):
        assert send_to_sdi_block_reason(_doc(status="error")) is None

    def test_scartata_must_use_retry(self):
        reason = send_to_sdi_block_reason(_doc(status="sent", sdi_status="scartata"))
        assert reason is not None
        assert "retry-send" in reason

    def test_consegnata_blocked(self):
        reason = send_to_sdi_block_reason(_doc(status="sent", sdi_status="consegnata"))
        assert reason is not None
        assert "già evaso" in reason

    def test_mancata_consegna_not_resendable(self):
        reason = send_to_sdi_block_reason(
            _doc(status="sent", sdi_status="mancata_consegna")
        )
        assert reason is not None

    def test_sent_waiting_notification_blocked(self):
        reason = send_to_sdi_block_reason(_doc(status="sent", sdi_status=None))
        assert reason is not None
        assert "attesa" in reason

    def test_pending_blocked(self):
        reason = send_to_sdi_block_reason(_doc(status="pending"))
        assert reason is not None


class TestRetrySendBlock:
    def test_scartata_ok_when_api_send_enabled(self, monkeypatch):
        monkeypatch.setenv("FATTURAPA_SDI_API_SEND_ENABLED", "true")
        assert retry_send_block_reason(_doc(sdi_status="scartata")) is None

    def test_blocked_when_api_send_disabled(self, monkeypatch):
        monkeypatch.setenv("FATTURAPA_SDI_API_SEND_ENABLED", "false")
        reason = retry_send_block_reason(_doc(sdi_status="scartata"))
        assert reason is not None
        assert "disabilitato" in reason

    def test_not_scartata_blocked(self, monkeypatch):
        monkeypatch.setenv("FATTURAPA_SDI_API_SEND_ENABLED", "true")
        reason = retry_send_block_reason(_doc(sdi_status="consegnata"))
        assert reason is not None

    def test_non_electronic_blocked(self, monkeypatch):
        monkeypatch.setenv("FATTURAPA_SDI_API_SEND_ENABLED", "true")
        reason = retry_send_block_reason(
            _doc(is_electronic=False, sdi_status="scartata")
        )
        assert reason is not None


class TestGenerateXmlBlock:
    def test_scartata_redirects_to_retry_when_api_on(self):
        reason = generate_xml_block_reason(
            _doc(sdi_status="scartata"), api_send_enabled=True
        )
        assert reason is not None
        assert "retry-send" in reason

    def test_scartata_allowed_when_api_off(self):
        assert (
            generate_xml_block_reason(
                _doc(sdi_status="scartata"), api_send_enabled=False
            )
            is None
        )

    def test_other_ok(self):
        assert generate_xml_block_reason(_doc()) is None


class TestInvoiceEditAndResetXml:
    def test_generated_editable(self):
        assert invoice_edit_block_reason(_doc(status="generated")) is None

    def test_scartata_editable(self):
        assert invoice_edit_block_reason(_doc(status="sent", sdi_status="scartata")) is None

    def test_consegnata_not_editable(self):
        reason = invoice_edit_block_reason(
            _doc(status="generated", sdi_status="consegnata")
        )
        assert reason is not None
        assert "evaso" in reason

    def test_reset_xml_blocked_when_issued(self):
        reason = reset_xml_block_reason(
            _doc(status="generated", sdi_status="consegnata", xml_content="<x/>")
        )
        assert reason is not None

    def test_reset_xml_ok_when_generated(self):
        assert (
            reset_xml_block_reason(_doc(status="generated", xml_content="<x/>")) is None
        )

    def test_generate_blocked_when_consegnata(self):
        reason = generate_xml_block_reason(
            _doc(sdi_status="consegnata"), api_send_enabled=False
        )
        assert reason is not None


class TestApiSendFlag:
    def test_default_is_enabled(self, monkeypatch):
        monkeypatch.delenv("FATTURAPA_SDI_API_SEND_ENABLED", raising=False)
        assert is_sdi_api_send_enabled() is True

    def test_true_enables(self, monkeypatch):
        monkeypatch.setenv("FATTURAPA_SDI_API_SEND_ENABLED", "true")
        assert is_sdi_api_send_enabled() is True

    def test_blocks_only_real_sdi_send(self, monkeypatch):
        monkeypatch.setenv("FATTURAPA_SDI_API_SEND_ENABLED", "false")
        assert api_sdi_send_disabled_reason(True) is not None
        assert api_sdi_send_disabled_reason(False) is None
