from datetime import date
from fastapi import HTTPException
from sqlalchemy import func, desc
from sqlalchemy.orm import Session, noload

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
                with_address: bool = False,
                page: int = 1,
                limit: int = 100,
                **kwargs
                ) -> AllCustomerResponseSchema:
        """
        Recupera tutti i clienti

        Returns:
            AllCustomerResponseSchema: Tutti i clienti
        """
        lang_ids = kwargs.get('lang_ids')
        param = kwargs.get('param')

        query = self.session.query(Customer).order_by(desc(Customer.id_customer))
        if not with_address:
            query = query.options(noload(Customer.addresses))
        try:

            query = QueryUtils.filter_by_id(query, Customer, 'id_lang', lang_ids) if lang_ids else query
            query = QueryUtils.search_customer_in_every_field_and_firstname_and_lastname(query, Customer,
                                                                                         param) if param else query

            return query.offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")


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
            query = QueryUtils.search_customer_in_every_field_and_firstname_and_lastname(query, Customer,
                                                                                         param) if param else query

        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")

        return query.scalar()

    def get_by_id(self, _id: int) -> CustomerResponseSchema:
        return self.session.query(Customer).filter(Customer.id_customer == _id).first()
    
    def get_by_origin_id(self, origin_id: str) -> Customer:
        """Get customer by origin ID"""
        return self.session.query(Customer).filter(Customer.id_origin == origin_id).first()

    def get_by_email(self, email: str) -> CustomerResponseSchema:
        return self.session.query(Customer).filter(func.lower(Customer.email) == email.lower()).first()

    def create(self, data: CustomerSchema):
        customer = Customer(**data.model_dump())
        if self.get_by_origin_id(str(customer.id_origin)) is None or customer.id_origin == 0:
            customer.date_add = date.today()

            self.session.add(customer)
            self.session.commit()
            self.session.refresh(customer)
            return customer.id_customer
        else:
            raise HTTPException(status_code=409, detail="Customer con questo id_origin già presente in database")

    def create_and_get_id(self, data: CustomerSchema):
        """Funzione normalmente utilizzata nelle repository degli altri modelli per creare e recuperare ID"""
        customer_new = Customer(**data.model_dump())
        customer = self.get_by_origin_id(str(customer_new.id_origin))
        if customer is None:
            customer_new.date_add = date.today()

            self.session.add(customer_new)
            self.session.commit()
            self.session.refresh(customer_new)
            return customer_new.id_customer
        else:
            return customer.id_customer

    def bulk_create(self, data_list: list[CustomerSchema], batch_size: int = 1000):
        """Bulk insert customers for better performance"""
        from datetime import date
        
        # Get existing origin IDs to avoid duplicates
        origin_ids = [str(data.id_origin) for data in data_list]
        existing_customers = self.session.query(Customer).filter(Customer.id_origin.in_(origin_ids)).all()
        existing_origin_ids = {str(customer.id_origin) for customer in existing_customers}
        
        # Filter out existing customers
        new_customers_data = [data for data in data_list if str(data.id_origin) not in existing_origin_ids]
        
        if not new_customers_data:
            return 0
        
        # Process in batches
        total_inserted = 0
        for i in range(0, len(new_customers_data), batch_size):
            batch = new_customers_data[i:i + batch_size]
            customers = []
            
            for data in batch:
                customer = Customer(**data.model_dump())
                customer.date_add = date.today()
                customers.append(customer)
            
            self.session.bulk_save_objects(customers)
            total_inserted += len(customers)
            
            # Commit every batch
            self.session.commit()
            
        return total_inserted

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
