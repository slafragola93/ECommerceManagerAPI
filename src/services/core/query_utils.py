from fastapi import HTTPException, Query
from sqlalchemy import or_, func
from sqlalchemy.sql import expression


class QueryUtils:
    @staticmethod
    def parse_int_list(s):
        """Gestisce la conversione di stringhe in liste di interi e lancia un'eccezione se il formato non è corretto."""
        try:
            return [int(item) for item in s.split(',')]
        except ValueError:
            raise ValueError("Input non valido, separare gli elementi con una virgola.")

    @staticmethod
    def filter_by_id(query, model, field_name, values):
        if values:
            try:
                ids = QueryUtils.parse_int_list(values)
                query = query.filter(getattr(model, field_name).in_(ids))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid parameter for {field_name}")
        return query

    @staticmethod
    def filter_by_string(query, model, field_name, value):
        if value:
            query = query.filter(getattr(model, field_name).ilike(f"%{value}%"))
        return query

    @staticmethod
    def search_in_every_field(query: Query, model, value: str, *args) -> Query:
        if value:
            conditions = []
            for field_name in args:
                if hasattr(model, field_name):
                    conditions.append(getattr(model, field_name).ilike(f"%{value}%"))
            if conditions:
                query = query.filter(or_(*conditions))
        return query

    @staticmethod
    def search_customer_in_every_field_and_firstname_and_lastname(query: Query, model, value: str) -> Query:
        if value:
            query = query.filter(
                (func.lower(func.trim(model.firstname)) + ' ' + func.lower(func.trim(model.lastname))).like(
                    f'%{value}%') |
                func.lower(model.email).like(f'%{value}%') | (
                    func.lower(model.id_customer).in_([value.lower()])
                )
            )
        return query

    @staticmethod
    def filter_by_date(query, model, field_name: str, date_from: str, date_to: str):
        if date_from:
            query = query.filter(getattr(model, field_name) >= date_from)
        if date_to:
            query = query.filter(getattr(model, field_name) <= date_to)
        return query

    @staticmethod
    def edit_entity(entity, entity_schema):
        """ Recupero dei dati e modifica dell'entità """
        # Recupera i campi modificati
        entity_updated = entity_schema.model_dump(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(entity, key) and value is not None:
                setattr(entity, key, value)

    @staticmethod
    def get_offset(limit, page):
        """Calcola l'offset per la query"""
        offset = (page - 1) * limit
        return offset

    @staticmethod
    def get_count_results(query, model):
        """Calcola il numero di risultati della query"""
        return query.count()

    @staticmethod
    def create_and_set_id(repository, schema_datas: dict, field_name):
        """Imposta l'id dell'entità"""
        return repository.create_and_get_id(getattr(schema_datas, field_name))
