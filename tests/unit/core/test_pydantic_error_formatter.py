"""Regressione: errori Pydantic con ctx.error (ValueError) devono essere JSON-serializzabili."""
import json

from pydantic import BaseModel, ValidationError, model_validator

from src.core.pydantic_error_formatter import PydanticErrorFormatter
from src.schemas.fiscal_document_schema import CreditNoteCreateSchema


class _ModelWithRootValidator(BaseModel):
    flag: bool = False

    @model_validator(mode="after")
    def boom(self):
        if self.flag:
            raise ValueError("errore di esempio")
        return self


class TestPydanticErrorFormatterJsonSafe:
    def test_value_error_in_ctx_is_json_serializable(self):
        try:
            _ModelWithRootValidator(flag=True)
        except ValidationError as exc:
            formatted = PydanticErrorFormatter.format(exc.errors())

        json.dumps(formatted)  # non deve sollevare TypeError
        assert formatted["status_code"] == 422
        raw = formatted["details"]["validation_errors"]
        assert isinstance(raw[0]["ctx"]["error"], str)

    def test_credit_note_partial_without_items_formats_as_422(self):
        try:
            CreditNoteCreateSchema(
                id_invoice=1,
                reason="test",
                is_partial=True,
                include_shipping=False,
            )
        except ValidationError as exc:
            formatted = PydanticErrorFormatter.format(exc.errors())

        json.dumps(formatted)
        assert formatted["status_code"] == 422
        assert (
            "items" in formatted["message"].lower()
            or "spedizione" in formatted["message"].lower()
        )
