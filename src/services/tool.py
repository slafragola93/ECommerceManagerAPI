from datetime import datetime
from typing import Any

from fastapi import HTTPException


def edit_entity(entity, entity_schema):
    """ Recupero dei dati e modifica dell'entità """
    # Recupera i campi modificati
    entity_updated = entity_schema.dict(exclude_unset=True)  # Esclude i campi non impostati

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