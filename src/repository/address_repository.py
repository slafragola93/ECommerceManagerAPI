"""
Address Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc, select
from sqlalchemy.engine import Row
from src.models.address import Address
from src.models.customer import Customer
from src.repository.interfaces.address_repository_interface import IAddressRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils

class AddressRepository(BaseRepository[Address, int], IAddressRepository):
    """Address Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Address)
    
    def get_by_id(self, id: int) -> Optional[Address]:
        """Ottiene un address per ID con relazioni caricate"""
        try:
            from sqlalchemy.orm import joinedload
            
            id_field = self._get_id_field()
            return self._session.query(self._model_class).filter(
                getattr(self._model_class, id_field) == id
            ).options(
                joinedload(Address.customer),
                joinedload(Address.country)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__}: {str(e)}")
    
    def get_all(self, **filters) -> List[Address]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            from sqlalchemy.orm import joinedload
            
            query = self._session.query(self._model_class).order_by(desc(Address.id_address))
            
            # Filtro per id_customer se specificato
            id_customer = filters.get('id_customer')
            if id_customer is not None:
                query = query.filter(Address.id_customer == id_customer)
            
            # Carica sempre le relazioni customer e country per lo schema di risposta
            query = query.options(
                joinedload(Address.customer),
                joinedload(Address.country)
            )
            
            # Paginazione (solo se page e limit sono specificati)
            page = filters.get('page')
            limit = filters.get('limit')
            
            if page is not None and limit is not None:
                offset = self.get_offset(limit, page)
                query = query.offset(offset).limit(limit)
            
            return query.all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__} list: {str(e)}")
    
    def get_count(self, **filters) -> int:
        """Conta le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class)
            
            # Filtro per id_customer se specificato
            id_customer = filters.get('id_customer')
            if id_customer is not None:
                query = query.filter(Address.id_customer == id_customer)
            
            return query.count()
        except Exception as e:
            raise InfrastructureException(f"Database error counting {self._model_class.__name__}: {str(e)}")
    
    def get_by_name(self, name: str) -> Optional[Address]:
        """Ottiene un address per nome (case insensitive)"""
        try:
            return self._session.query(Address).filter(
                func.lower(Address.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving address by name: {str(e)}")
    
    def get_delivery_data(self, id_address: int) -> Row:
        """Get address fields for delivery details"""
        try:
            stmt = select(
                Address.id_address,
                Address.address1,
                Address.postcode,
                Address.city,
                Address.firstname,
                Address.lastname,
                Address.company,
                Address.phone,
                Customer.email,  # Email from Customer table
                Address.id_country
            ).join(Customer, Address.id_customer == Customer.id_customer).where(Address.id_address == id_address)
            
            result = self._session.execute(stmt).first()
            if not result:
                raise InfrastructureException(f"Address {id_address} not found")
            return result
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving address delivery data: {str(e)}")
