from datetime import date
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models import Customer
from src.schemas.customer_schema import *
from src.services import QueryUtils


class CustomerRepository:
    """
    Repository clienti
    """

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self,
                page: int = 1, limit: int = 10,
                **kwargs
                ) -> AllCustomerResponseSchema:
        """
        Recupera tutti i clienti

        Returns:
            AllCustomerResponseSchema: Tutti i clienti
        """
        lang_ids = kwargs.get('lang_ids')
        param = kwargs.get('param')

        query = self.session.query(Customer)

        try:
            query = QueryUtils.filter_by_id(query, Customer, 'id_lang', lang_ids) if lang_ids else query
            query = QueryUtils.search_in_every_field(query,
                                                     Customer,
                                                     param,
                                                     "firstname", "lastname", "email") if param else query

        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")

        customers_result = query.offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

        return customers_result

    def get_count(self,
                  **kwargs,
                  ) -> AllCustomerResponseSchema:
        """
        Recupera tutti i clienti

        Returns:
            AllCustomerResponseSchema: Tutti i clienti
        """
        lang_ids = kwargs.get('lang_ids')
        param = kwargs.get('param')
        query = self.session.query(func.count(Customer.id_customer))

        try:
            query = QueryUtils.filter_by_id(query, Customer, 'id_lang', lang_ids) if lang_ids else query
            query = QueryUtils.search_in_every_field(query,
                                                     Customer,
                                                     param,
                                                     "firstname", "lastname", "email") if param else query

        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")

        customers_result = query.scalar()

        return customers_result

    def get_by_id(self, _id: int) -> CustomerResponseSchema:
        return self.session.query(Customer).filter(Customer.id_customer == _id).first()

    def get_by_email(self, email: str) -> CustomerResponseSchema:
        return self.session.query(Customer).filter(func.lower(Customer.email) == email.lower()).first()

    def create(self, data: CustomerSchema):
        customer = Customer(**data.model_dump())
        if self.get_by_email(customer.email) is None:
            customer.date_add = date.today()

            self.session.add(customer)
            self.session.commit()
            self.session.refresh(customer)
        else:
            raise HTTPException(status_code=409, detail="Email già presente in database")

    def create_and_get_id(self, data: CustomerSchema):
        """Funzione normalmente utilizzata nelle repository degli altri modelli per creare e recuperare ID"""
        customer_new = Customer(**data.model_dump())
        customer = self.get_by_email(customer_new.email)
        if customer is None:
            customer_new.date_add = date.today()

            self.session.add(customer_new)
            self.session.commit()
            self.session.refresh(customer_new)
            return customer_new.id_customer
        else:
            return customer.id_customer

    def update(self, edited_customer: Customer, data: CustomerSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_customer, key) and value is not None:
                setattr(edited_customer, key, value)

        self.session.add(edited_customer)
        self.session.commit()

    def delete(self, customer: Customer) -> bool:
        self.session.delete(customer)
        self.session.commit()

        return True
