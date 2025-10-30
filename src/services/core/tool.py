from datetime import datetime
from typing import Any
import random
import string

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


def format_datetime_ddmmyy_hhmm(dt: datetime | None) -> str | None:
    """Formatta una datetime in 'DD-MM-YYYY HH:mm'. Ritorna None se dt è None."""
    if dt is None:
        return None
    try:
        return dt.strftime('%d-%m-%Y %H:%M')
    except Exception:
        return None


def generate_internal_reference(country_iso_code: str, app_config_repository) -> str:
    """
    Genera un reference code sequenziale per ordini con formato: {ISO_CODE}{SEQUENTIAL_NUMBER}
    
    Args:
        country_iso_code: Codice ISO del paese (es. "IT", "DE")
        app_config_repository: Repository per AppConfiguration per gestire contatore globale
    
    Returns:
        str: Reference code generato (es. "IT001", "IT1000", "DE001")
    
    Esempio:
        generate_internal_reference("IT", repo) → "IT001"
        generate_internal_reference("DE", repo) → "IT002" (stesso counter globale)
        
    NOTA: Max 12 caratteri per internal_reference (potrebbe cambiare in futuro)
    """
    iso_code = country_iso_code.upper()
    config_key = "order_reference_counter_global"
    
    try:
        # Recupera o crea contatore globale
        counter_config = app_config_repository.get_by_name_and_category(
            name=config_key, 
            category="order_reference"
        )
        
        if not counter_config:
            # Crea nuovo contatore globale se non esiste
            counter_config = app_config_repository.create({
                "category": "order_reference",
                "name": config_key,
                "value": "0",
                "description": "Global sequential counter for order references"
            })
        
        # Incrementa contatore in modo thread-safe
        current_value = int(counter_config.value)
        new_value = current_value + 1
        
        # Aggiorna contatore
        counter_config.value = str(new_value)
        app_config_repository.update(counter_config)
        
        # Genera reference: ISO_CODE + numero sequenziale globale
        reference = f"{iso_code}{new_value:03d}"  # Formato: IT001, IT002, etc.
        
        # Se supera 999, usa formato senza padding: IT1000, IT1001, etc.
        if new_value > 999:
            reference = f"{iso_code}{new_value}"
        
        return reference
        
    except Exception as e:
        # Fallback: genera reference temporaneo se fallisce
        import time
        timestamp = int(time.time())
        return f"{iso_code}{timestamp % 10000:04d}"