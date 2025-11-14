"""
Country Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.country import Country
from src.repository.interfaces.country_repository_interface import ICountryRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils
from src.schemas.country_schema import CountrySchema

class CountryRepository(BaseRepository[Country, int], ICountryRepository):
    """Country Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Country)
    
    def get_all(self, **filters) -> List[Country]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Country.id_country))
            
            # Paginazione
            page = filters.get('page', 1)
            limit = filters.get('limit', 100)
            offset = self.get_offset(limit, page)
            
            return query.offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__} list: {str(e)}")
    
    def get_count(self, **filters) -> int:
        """Conta le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class)
            return query.count()
        except Exception as e:
            raise InfrastructureException(f"Database error counting {self._model_class.__name__}: {str(e)}")
    
    def get_by_name(self, name: str) -> Optional[Country]:
        """Ottiene un country per nome (case insensitive)"""
        try:
            return self._session.query(Country).filter(
                func.lower(Country.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving country by name: {str(e)}")
    
    def get_by_origin_id(self, origin_id: str) -> Optional[Country]:
        """Ottiene un paese per origin ID"""
        try:
            return self._session.query(Country).filter(
                Country.id_origin == origin_id
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving country by origin ID: {str(e)}")
    
    def get_iso_code(self, id_country: int) -> str:
        """Get only iso_code field"""
        try:
            result = self._session.query(Country.iso_code).filter(
                Country.id_country == id_country
            ).first()
            if not result:
                raise InfrastructureException(f"Country {id_country} not found")
            return result[0]
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving country ISO code: {str(e)}")
    
    def get_all_id_mappings(self) -> Dict[int, int]:
        """
        Ottiene tutti i mapping id_origin -> id_country per uso efficiente.
        
        Query ottimizzata che recupera solo i campi necessari SENZA limitazioni.
        Utilizzata per sincronizzazione e operazioni bulk dove servono tutti i paesi.
        
        Returns:
            Dict[int, int]: Dizionario {id_origin: id_country}
        """
        try:
            # Query ottimizzata: solo 2 campi, NESSUN limite
            results = self._session.query(
                Country.id_origin,
                Country.id_country
            ).filter(
                Country.id_origin.isnot(None),
                Country.id_origin != 0
            ).all()
            
            return {int(row.id_origin): int(row.id_country) for row in results}
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving country ID mappings: {str(e)}")
    
    def bulk_create_csv_import(self, data_list: List[CountrySchema], batch_size: int = 1000) -> int:
        """
        Bulk insert countries da CSV import.
        
        Args:
            data_list: Lista CountrySchema da inserire
            batch_size: Dimensione batch (default: 1000)
            
        Returns:
            Numero countries inseriti
        """
        if not data_list:
            return 0
        
        try:
            # Get existing id_origin to avoid duplicates
            origin_ids = [data.id_origin for data in data_list if data.id_origin]
            existing_countries = self._session.query(Country.id_origin).filter(
                Country.id_origin.in_(origin_ids)
            ).all()
            existing_origins = {c.id_origin for c in existing_countries}
            
            # Filter new countries
            new_countries_data = [data for data in data_list if data.id_origin not in existing_origins]
            
            if not new_countries_data:
                return 0
            
            # Batch insert
            total_inserted = 0
            for i in range(0, len(new_countries_data), batch_size):
                batch = new_countries_data[i:i + batch_size]
                countries = [Country(**c.model_dump()) for c in batch]
                self._session.bulk_save_objects(countries)
                total_inserted += len(countries)
            
            self._session.commit()
            return total_inserted
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error bulk creating countries: {str(e)}")