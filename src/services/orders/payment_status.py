"""
Helper per sincronizzare lo stato is_payed dell'ordine con i pagamenti registrati.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.order import Order
from src.models.order_payment import OrderPayment


def compute_payment_summary(order: Order, payments: list[OrderPayment]) -> dict:
    """Calcola summary pagamenti rispetto al totale ordine."""
    total_scheduled = sum(float(p.amount or 0) for p in payments)
    total_paid = sum(float(p.amount or 0) for p in payments if p.is_paid)
    order_total = float(order.total_price_with_tax or 0)
    return {
        "total_scheduled": round(total_scheduled, 5),
        "total_paid": round(total_paid, 5),
        "remaining_amount": round(order_total - total_paid, 5),
    }


def sync_order_payment_status(
    session: Session,
    order_id: int,
    *,
    force_unpaid: bool = False,
    commit: bool = True,
) -> None:
    """
    Imposta order.is_payed = False quando la copertura è insufficiente.

    Non imposta mai is_payed=True (resta decisione manuale via PATCH).

    - force_unpaid: forza is_payed=False (es. nuovo pagamento non saldato)
    - Se esistono order_payments e total_paid < totale ordine → is_payed=False
    - Se non esistono order_payments e non force_unpaid → no-op (legacy)
    """
    order = session.query(Order).filter(Order.id_order == order_id).first()
    if not order or not order.is_payed:
        return

    if force_unpaid:
        order.is_payed = False
        if commit:
            session.commit()
        else:
            session.flush()
        return

    payments = (
        session.query(OrderPayment)
        .filter(OrderPayment.id_order == order_id)
        .all()
    )
    if not payments:
        return

    total_paid = sum(float(p.amount or 0) for p in payments if p.is_paid)
    order_total = float(order.total_price_with_tax or 0)
    if total_paid < order_total:
        order.is_payed = False
        if commit:
            session.commit()
        else:
            session.flush()


def mark_order_unpaid_if_total_increased(
    session: Session,
    order: Order,
    previous_total: float,
    *,
    commit: bool = True,
) -> None:
    """Se l'ordine era pagato e il totale è aumentato, marca come non pagato."""
    if not order or not order.is_payed:
        return
    new_total = float(order.total_price_with_tax or 0)
    if new_total > float(previous_total or 0):
        order.is_payed = False
        if commit:
            session.commit()
        else:
            session.flush()
