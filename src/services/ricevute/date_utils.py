"""Utility date condivise per ricevute e corrispettivi (BE-3.1)."""
from datetime import date, datetime, time
from typing import Optional, Union
from zoneinfo import ZoneInfo

from src.models.order import Order

ROME = ZoneInfo("Europe/Rome")
UTC = ZoneInfo("UTC")


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


def normalize_emission_datetime(
    value: Optional[Union[date, datetime]] = None,
) -> datetime:
    """
    Normalizza data/ora emissione per persistenza (UTC naive, come `Order.date_add`).

    - `None` → adesso in Europe/Rome
    - `date` → stesso giorno con ora corrente Rome
    - `datetime` naive → interpretato come Europe/Rome
    """
    if value is None:
        local = datetime.now(ROME)
    elif isinstance(value, date) and not isinstance(value, datetime):
        local = datetime.combine(value, datetime.now(ROME).time(), tzinfo=ROME)
    else:
        local = value
        if local.tzinfo is None:
            local = local.replace(tzinfo=ROME)
        else:
            local = local.astimezone(ROME)
    return local.astimezone(UTC).replace(tzinfo=None)


def emission_to_rome(value: datetime) -> datetime:
    """Converte emissione persistita (UTC naive) in datetime Europe/Rome."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ROME)


def format_emission_datetime(value: datetime, *, with_time: bool = True) -> str:
    """Formato UI/PDF: gg/mm/aaaa [hh:mm] in timezone Europe/Rome."""
    local = emission_to_rome(value)
    fmt = "%d/%m/%Y %H:%M" if with_time else "%d/%m/%Y"
    return local.strftime(fmt)


def utc_naive_start_of_day(day: date) -> datetime:
    """Inizio giornata locale (Rome) come UTC naive — filtri repository."""
    return (
        datetime.combine(day, time.min, tzinfo=ROME)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )


def utc_naive_end_of_day(day: date) -> datetime:
    """Fine giornata locale (Rome) come UTC naive — filtri repository."""
    return (
        datetime.combine(day, time(23, 59, 59, 999999), tzinfo=ROME)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
