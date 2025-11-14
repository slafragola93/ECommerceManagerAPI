"""
Customer Repository rifattorizzato seguendo i principi SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc, or_
from src.models.customer import Customer
from src.repository.interfaces.customer_repository_interface import ICustomerRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils
from src.schemas.customer_schema import CustomerSchema

class CustomerRepository(ICustomerRepository, BaseRepository[Customer, int]):
    """Customer Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Customer)
    
    def get_all(self, **filters) -> List[Customer]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Customer.id_customer))
            
            # Gestisci filtri specifici per Customer
            with_address = filters.get('with_address', False)
            if not with_address:
                query = query.options(noload(Customer.addresses))
            
            # Filtro per lingue
            lang_ids = filters.get('lang_ids')
            if lang_ids:
                query = QueryUtils.filter_by_id(query, Customer, 'id_lang', lang_ids)
            
            # Filtro per ricerca testuale
            param = filters.get('param')
            if param:
                query = QueryUtils.search_customer_in_every_field_and_firstname_and_lastname(query, Customer, param)
            
            # Paginazione
            page = filters.get('page', 1)
            limit = filters.get('limit', 100)
            offset = self.get_offset(limit, page)
            
            return query.offset(offset).limit(limit).all()
        except ValueError:
            raise InfrastructureException("Parametri di ricerca non validi")
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__} list: {str(e)}")
    
    def get_count(self, **filters) -> int:
        """Conta le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class)
            
            # Filtro per lingue
            lang_ids = filters.get('lang_ids')
            if lang_ids:
                query = QueryUtils.filter_by_id(query, Customer, 'id_lang', lang_ids)
            
            # Filtro per ricerca testuale
            param = filters.get('param')
            if param:
                query = QueryUtils.search_customer_in_every_field_and_firstname_and_lastname(query, Customer, param)
            
            return query.count()
        except ValueError:
            raise InfrastructureException("Parametri di ricerca non validi")
        except Exception as e:
            raise InfrastructureException(f"Database error counting {self._model_class.__name__}: {str(e)}")
    
    def get_by_email(self, email: str) -> Optional[Customer]:
        """Ottiene un cliente per email (case insensitive)"""
        try:
            return self._session.query(Customer).filter(
                func.lower(Customer.email) == email.lower()
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving customer by email: {str(e)}")
    
    def get_by_origin_id(self, origin_id: str) -> Optional[Customer]:
        """Ottiene un cliente per origin ID"""
        try:
            return self._session.query(Customer).filter(
                Customer.id_origin == origin_id
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving customer by origin_id: {str(e)}")
    
    def search_by_name(self, name: str) -> List[Customer]:
        """Cerca clienti per nome (firstname o lastname)"""
        try:
            search_term = f"%{name}%"
            return self._session.query(Customer).filter(
                or_(
                    Customer.firstname.ilike(search_term),
                    Customer.lastname.ilike(search_term)
                )
            ).all()
        except Exception as e:
            raise InfrastructureException(f"Database error searching customers by name: {str(e)}")
    
    def get_customers_with_addresses(self, page: int = 1, limit: int = 10) -> List[Customer]:
        """Ottiene clienti con i loro indirizzi"""
        try:
            offset = self.get_offset(limit, page)
            return self._session.query(Customer).offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving customers with addresses: {str(e)}")
    
    def get_customers_without_addresses(self, page: int = 1, limit: int = 10) -> List[Customer]:
        """Ottiene clienti senza caricare gli indirizzi (performance optimization)"""
        try:
            offset = self.get_offset(limit, page)
            return self._session.query(Customer).options(
                noload(Customer.addresses)
            ).offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving customers without addresses: {str(e)}")
    
    def get_customers_by_lang(self, lang_id: int, page: int = 1, limit: int = 10) -> List[Customer]:
        """Ottiene clienti per lingua"""
        try:
            offset = self.get_offset(limit, page)
            return self._session.query(Customer).filter(
                Customer.id_lang == lang_id
            ).offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving customers by language: {str(e)}")
    
    def get_active_customers_count(self) -> int:
        """Conta i clienti attivi (con almeno un ordine)"""
        try:
            # Subquery per clienti con ordini
            subquery = self._session.query(Customer.id_customer).distinct().subquery()
            return self._session.query(Customer).filter(
                Customer.id_customer.in_(subquery)
            ).count()
        except Exception as e:
            raise InfrastructureException(f"Database error counting active customers: {str(e)}")
    
    def bulk_create_csv_import(self, data_list: List[CustomerSchema], batch_size: int = 1000) -> int:
        """
        Bulk insert customers da CSV import.
        
        Args:
            data_list: Lista CustomerSchema da inserire
            batch_size: Dimensione batch (default: 1000)
            
        Returns:
            Numero customers inseriti
        """
        if not data_list:
            return 0
        
        try:
            # Get existing id_origin to avoid duplicates
            origin_ids = [data.id_origin for data in data_list if data.id_origin]
            existing_customers = self._session.query(Customer.id_origin).filter(
                Customer.id_origin.in_(origin_ids)
            ).all()
            existing_origins = {c.id_origin for c in existing_customers}
            
            # Filter new customers
            new_customers_data = [data for data in data_list if data.id_origin not in existing_origins]
            
            if not new_customers_data:
                return 0
            
            # Batch insert
            total_inserted = 0
            for i in range(0, len(new_customers_data), batch_size):
                batch = new_customers_data[i:i + batch_size]
                customers = [Customer(**c.model_dump()) for c in batch]
                self._session.bulk_save_objects(customers)
                total_inserted += len(customers)
            
            self._session.commit()
            return total_inserted
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error bulk creating customers: {str(e)}")
