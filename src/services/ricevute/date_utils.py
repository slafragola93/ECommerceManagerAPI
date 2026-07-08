"""Utility date condivise per ricevute e corrispettivi (BE-3.1)."""
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from src.models.order import Order

ROME = ZoneInfo("Europe/Rome")


def resolve_order_payment_date(order: Order) -> date:
    """
    Data incasso ricevuta = data pagamento ordine (DATE).

    Fallback: giorno di `date_add` in timezone Europe/Rome se pagamento
    registrato ma `payment_date` assente.
    """
    if order.payment_date is not None:
        return order.payment_date
    if order.is_payed and order.date_add is not None:
        dt = order.date_add
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            return dt.astimezone(ROME).date()
        if isinstance(dt, date):
            return dt
    raise ValueError(
        "Impossibile determinare la data incasso: ordine senza payment_date"
    )
