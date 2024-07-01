from datetime import datetime

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
    print(last_document_number)
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