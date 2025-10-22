from datetime import datetime
from typing import Any

from fastapi import HTTPException


def edit_entity(entity, entity_schema):
    """ Recupero dei dati e modifica dell'entità """
    # Recupera i campi modificati
    entity_updated = entity_schema.model_dump(exclude_unset=True)  # Esclude i campi non impostati

    # Set su ogni proprietà
    for key, value in entity_updated.items():
        if hasattr(entity, key) and value is not None:
            setattr(entity, key, value)


@staticmethod
def document_number_generator(last_document_number):
    if last_document_number is None:
        return 1
    return last_document_number + 1

@staticmethod
def validate_format_date(date: str):
    if date:
        try:
            datetime.strptime(date, '%Y-%m-%d')
            return True
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Formato data non valido: {date}. Formato atteso: YYYY-MM-DD")


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int, returning default if conversion fails"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float, returning default if conversion fails"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def sql_value(value: Any, null_value: str = "NULL") -> str:
    """Convert value to SQL-safe string representation"""
    if value is None:
        return null_value
    elif isinstance(value, str):
        return f"'{value.replace(chr(39), chr(39) + chr(39))}'"  # Escape single quotes
    else:
        return str(value)


def generate_preventivo_reference(document_number: str) -> str:
    """Genera reference automatica per preventivo con formato PRV+document_number"""
    return f"PRV{document_number}"


def calculate_price_with_tax(base_price: float, tax_percentage: float, quantity: int = 1) -> float:
    """
    Calcola il prezzo totale con tasse applicate
    
    Args:
        base_price: Prezzo base del prodotto
        tax_percentage: Percentuale della tassa (es. 22 per 22%)
        quantity: Quantità del prodotto (default: 1)
    
    Returns:
        float: Prezzo totale con tasse applicate
    """
    if base_price is None or base_price < 0:
        return 0.0
    
    if tax_percentage is None or tax_percentage < 0:
        tax_percentage = 0.0
    
    if quantity is None or quantity <= 0:
        quantity = 1
    
    # Calcola il prezzo base totale
    total_base_price = base_price * quantity
    
    # Applica la tassa
    total_price_with_tax = total_base_price * (1 + tax_percentage / 100)
    
    return round(total_price_with_tax, 2)


def calculate_order_total_with_taxes(order_details: list, tax_percentages: dict = None) -> float:
    """
    Calcola il totale dell'ordine con tasse applicate
    
    Args:
        order_details: Lista di OrderDetail objects
        tax_percentages: Dizionario {id_tax: percentage} con le percentuali delle tasse
    
    Returns:
        float: Totale ordine con tasse applicate
    """
    if not order_details:
        return 0.0
    
    total_with_taxes = 0.0
    
    for order_detail in order_details:
        # Usa la tassa specifica dell'order_detail
        current_tax_percentage = 0.0
        if hasattr(order_detail, 'id_tax') and order_detail.id_tax and tax_percentages:
            current_tax_percentage = tax_percentages.get(order_detail.id_tax, 0.0)
        
        # Calcola il prezzo con tasse per questo order_detail
        price_with_tax = calculate_price_with_tax(
            base_price=order_detail.product_price or 0.0,
            tax_percentage=current_tax_percentage,
            quantity=order_detail.product_qty or 1
        )
        
        total_with_taxes += price_with_tax
    
    return round(total_with_taxes, 2)


def calculate_order_totals(order_details: list, tax_percentages: dict = None) -> dict:
    """
    Calcola tutti i totali di un ordine (prezzo, peso, sconti) dinamicamente
    
    Args:
        order_details: Lista di OrderDetail objects
        tax_percentages: Dizionario {id_tax: percentage} con le percentuali delle tasse
    
    Returns:
        dict: Dizionario con i totali calcolati
    """
    if not order_details:
        return {
            'total_price': 0.0,
            'total_weight': 0.0,
            'total_discounts': 0.0,
            'total_price_with_tax': 0.0
        }
    
    total_price_base = 0.0
    total_weight = 0.0
    total_discounts = 0.0
    total_price_with_tax = 0.0
    
    for order_detail in order_details:
        # Calcola peso totale
        weight = (order_detail.product_weight or 0.0) * (order_detail.product_qty or 1)
        total_weight += weight
        
        # Calcola prezzo base
        price_base = (order_detail.product_price or 0.0) * (order_detail.product_qty or 1)
        
        # Applica sconti
        discount_amount = 0.0
        if order_detail.reduction_percent and order_detail.reduction_percent > 0:
            discount_amount = calculate_amount_with_percentage(price_base, order_detail.reduction_percent)
        elif order_detail.reduction_amount and order_detail.reduction_amount > 0:
            discount_amount = order_detail.reduction_amount
        
        price_after_discount = price_base - discount_amount
        total_discounts += discount_amount
        total_price_base += price_after_discount
        
        # Calcola prezzo con tasse
        tax_percentage = 0.0
        if hasattr(order_detail, 'id_tax') and order_detail.id_tax and tax_percentages:
            tax_percentage = tax_percentages.get(order_detail.id_tax, 0.0)
        
        price_with_tax = price_after_discount * (1 + tax_percentage / 100)
        total_price_with_tax += price_with_tax
    
    return {
        'total_price': round(total_price_base, 2),
        'total_weight': round(total_weight, 2),
        'total_discounts': round(total_discounts, 2),
        'total_price_with_tax': round(total_price_with_tax, 2)
    }


def apply_order_totals_to_order(order, totals: dict, use_tax_included: bool = True) -> None:
    """
    Applica i totali calcolati a un oggetto Order
    
    Args:
        order: Oggetto Order da aggiornare
        totals: Dizionario con i totali calcolati
        use_tax_included: Parametro deprecato, mantiene entrambi i valori
    """
    # Assegna sempre entrambi i campi
    order.total_price_tax_excl = totals['total_price']  # Prezzo base senza tasse
    order.total_paid = totals['total_price_with_tax']  # Prezzo con tasse incluse
    
    order.total_weight = totals['total_weight']
    order.total_discounts = totals['total_discounts']


def calculate_amount_with_percentage(amount: float, percentage: float) -> float:
    """
    Calcola l'importo risultante applicando una percentuale
    
    Args:
        amount: Importo base
        percentage: Percentuale da applicare (es. 22 per 22%)
    
    Returns:
        float: Importo calcolato (amount × percentage / 100)
    
    Esempio:
        calculate_amount_with_percentage(100, 22) → 22.0
        calculate_amount_with_percentage(50.5, 10) → 5.05
    """
    return amount * (percentage / 100)