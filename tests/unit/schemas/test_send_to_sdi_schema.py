"""Validazione SendToSdiSchema + retrocompat boolean grezzo."""
from src.schemas.fiscal_document_schema import (
    SendToSdiSchema,
    resolve_send_to_sdi_flag,
)


class TestSendToSdiSchema:
    def test_default_is_false(self):
        assert SendToSdiSchema().send_to_sdi is False

    def test_object_true(self):
        schema = SendToSdiSchema.model_validate({"send_to_sdi": True})
        assert schema.send_to_sdi is True

    def test_resolve_object_false(self):
        assert resolve_send_to_sdi_flag(SendToSdiSchema(send_to_sdi=False)) is False

    def test_resolve_object_true(self):
        assert resolve_send_to_sdi_flag(SendToSdiSchema(send_to_sdi=True)) is True

    def test_resolve_raw_boolean(self):
        assert resolve_send_to_sdi_flag(True) is True
        assert resolve_send_to_sdi_flag(False) is False

    def test_resolve_none_is_false(self):
        assert resolve_send_to_sdi_flag(None) is False
