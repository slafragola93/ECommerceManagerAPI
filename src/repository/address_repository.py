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
from src.schemas.address_schema import AddressSchema

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
                Address.state,
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
    
    def bulk_create_csv_import(self, data_list: List[AddressSchema], id_platform: int = 1, batch_size: int = 1000) -> int:
        """
        Bulk insert addresses da CSV import con gestione id_platform.
        
        Args:
            data_list: Lista AddressSchema da inserire
            id_platform: ID platform per uniqueness check
            batch_size: Dimensione batch (default: 1000)
            
        Returns:
            Numero addresses inseriti
        """
        if not data_list:
            return 0
        
        try:
            # Get existing (id_origin, id_platform) pairs to avoid duplicates
            origin_ids = [data.id_origin for data in data_list if data.id_origin]
            
            if origin_ids:
                from sqlalchemy import and_
                existing_addresses = self._session.query(Address.id_origin).filter(
                    and_(
                        Address.id_origin.in_(origin_ids),
                        Address.id_platform == id_platform
                    )
                ).all()
                existing_origins = {a.id_origin for a in existing_addresses}
            else:
                existing_origins = set()
            
            # Filter new addresses
            new_addresses_data = [data for data in data_list if data.id_origin not in existing_origins]
            
            if not new_addresses_data:
                return 0
            
            # Batch insert
            total_inserted = 0
            for i in range(0, len(new_addresses_data), batch_size):
                batch = new_addresses_data[i:i + batch_size]
                addresses = [Address(**a.model_dump()) for a in batch]
                self._session.bulk_save_objects(addresses)
                total_inserted += len(addresses)
            
            self._session.commit()
            return total_inserted
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error bulk creating addresses: {str(e)}")
