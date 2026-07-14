"""Utility date condivise per ricevute e corrispettivi (BE-3.1)."""
import re
from datetime import date, datetime, time
from typing import Optional, Union
from zoneinfo import ZoneInfo

from src.models.order import Order

ROME = ZoneInfo("Europe/Rome")
UTC = ZoneInfo("UTC")
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def parse_emission_input(
    value: Optional[Union[str, date, datetime]] = None,
) -> Optional[Union[date, datetime]]:
    """
    Parsing input API `data_emissione` prima della normalizzazione.

    - `YYYY-MM-DD` → `date` (ora corrente Europe/Rome in normalizzazione)
    - ISO datetime con o senza offset/Z → `datetime`
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if _DATE_ONLY_RE.match(raw):
            return date.fromisoformat(raw)
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        return datetime.fromisoformat(raw)
    raise TypeError(
        f"data_emissione non valida: atteso date, datetime o stringa ISO, "
        f"ricevuto {type(value).__name__}"
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


def emission_to_rome(value: Union[date, datetime]) -> datetime:
    """Converte emissione persistita (UTC naive) o `date` in datetime Europe/Rome."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, time.min, tzinfo=ROME)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ROME)


def emission_for_pdf(value: Union[date, datetime]) -> datetime:
    """Normalizza `data_emissione` per layout PDF (datetime timezone-aware Rome)."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, time.min, tzinfo=ROME)
    return emission_to_rome(value)


def format_emission_datetime(
    value: Union[date, datetime], *, with_time: bool = True
) -> str:
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
