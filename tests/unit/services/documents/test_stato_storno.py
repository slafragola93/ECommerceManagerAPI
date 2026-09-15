"""Calcolo stato_storno: non_stornata / parziale / totale."""
from src.services.documents.stato_storno import (
    STATO_STORNO_NON,
    STATO_STORNO_PARZIALE,
    STATO_STORNO_TOTALE,
    residual_stornabile_zero,
    resolve_stato_storno,
)


def test_resolve_non_stornata_without_credit_notes():
    assert (
        resolve_stato_storno(
            has_credit_notes=False,
            has_total_credit_note=False,
            residual_zero=True,
        )
        == STATO_STORNO_NON
    )


def test_resolve_totale_if_total_credit_note():
    assert (
        resolve_stato_storno(
            has_credit_notes=True,
            has_total_credit_note=True,
            residual_zero=False,
        )
        == STATO_STORNO_TOTALE
    )


def test_resolve_totale_if_residual_zero():
    assert (
        resolve_stato_storno(
            has_credit_notes=True,
            has_total_credit_note=False,
            residual_zero=True,
        )
        == STATO_STORNO_TOTALE
    )


def test_resolve_parziale_if_residual_remains():
    assert (
        resolve_stato_storno(
            has_credit_notes=True,
            has_total_credit_note=False,
            residual_zero=False,
        )
        == STATO_STORNO_PARZIALE
    )


def test_residual_zero_requires_qty_and_shipping():
    qtys = {10: 2.0}
    assert residual_stornabile_zero(
        invoice_includes_shipping=True,
        shipping_already_refunded=False,
        invoice_qtys=qtys,
        refunded_qtys={10: 2.0},
    ) is False
    assert residual_stornabile_zero(
        invoice_includes_shipping=True,
        shipping_already_refunded=True,
        invoice_qtys=qtys,
        refunded_qtys={10: 2.0},
    ) is True
    assert residual_stornabile_zero(
        invoice_includes_shipping=False,
        shipping_already_refunded=False,
        invoice_qtys=qtys,
        refunded_qtys={10: 2.0},
    ) is True
    assert residual_stornabile_zero(
        invoice_includes_shipping=False,
        shipping_already_refunded=False,
        invoice_qtys=qtys,
        refunded_qtys={10: 1.0},
    ) is False
