"""
Carrier Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload, joinedload
from sqlalchemy import func, desc, and_, or_
from src.models.carrier import Carrier
from src.models.carrier_price import CarrierPrice
from src.repository.interfaces.carrier_repository_interface import ICarrierRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils
from src.schemas.carrier_schema import CarrierSchema

class CarrierRepository(BaseRepository[Carrier, int], ICarrierRepository):
    """Carrier Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Carrier)
    
    def get_all(self, **filters) -> List[Carrier]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Carrier.id_carrier))
            
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
    
    def get_by_name(self, name: str) -> Optional[Carrier]:
        """Ottiene un carrier per nome (case insensitive)"""
        try:
            return self._session.query(Carrier).filter(
                func.lower(Carrier.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving carrier by name: {str(e)}")
    
    def bulk_create_csv_import(self, data_list: List[CarrierSchema], batch_size: int = 1000) -> int:
        """
        Bulk insert carriers da CSV import.
        
        Args:
            data_list: Lista CarrierSchema da inserire
            batch_size: Dimensione batch (default: 1000)
            
        Returns:
            Numero carriers inseriti
        """
        if not data_list:
            return 0
        
        try:
            # Get existing id_origin to avoid duplicates
            origin_ids = [data.id_origin for data in data_list if data.id_origin]
            existing_carriers = self._session.query(Carrier.id_origin).filter(
                Carrier.id_origin.in_(origin_ids)
            ).all()
            existing_origins = {c.id_origin for c in existing_carriers}
            
            # Filter new carriers
            new_carriers_data = [data for data in data_list if data.id_origin not in existing_origins]
            
            if not new_carriers_data:
                return 0
            
            # Batch insert
            total_inserted = 0
            for i in range(0, len(new_carriers_data), batch_size):
                batch = new_carriers_data[i:i + batch_size]
                carriers = [Carrier(**c.model_dump()) for c in batch]
                self._session.bulk_save_objects(carriers)
                total_inserted += len(carriers)
            
            self._session.commit()
            return total_inserted
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error bulk creating carriers: {str(e)}")
    
    def get_price_by_criteria(self, id_carrier_api: int, id_country: int, weight: float, postcode: Optional[str] = None) -> Optional[float]:
        """
        Ottiene il prezzo del carrier price che corrisponde ai criteri specificati.
        
        Logica di ricerca:
        1. Recupera tutti i risultati per id_carrier_api, countries (LIKE), weight (range)
        2. Filtra in memoria per countries esatto e postcode
        3. Se postcode è fornito e trovato, restituisce quel prezzo
        4. Altrimenti restituisce il primo prezzo con postal_codes = NULL
        
        Args:
            id_carrier_api: ID del carrier API (obbligatorio)
            id_country: ID del paese (obbligatorio)
            weight: Peso del pacco (obbligatorio)
            postcode: Codice postale (opzionale)
            
        Returns:
            Optional[float]: Prezzo con IVA del carrier price, None se non trovato o se price_with_tax è None
        """
        try:
            # Step 1: Filtra per id_carrier_api esatto
            query = self._session.query(CarrierPrice).options(
                joinedload(CarrierPrice.carrier_api)
            ).filter(
                CarrierPrice.id_carrier_api == id_carrier_api
            )
            
            # Step 2: Filtra per id_country nella lista countries
            query = query.filter(
                and_(
                    CarrierPrice.countries.isnot(None),
                    CarrierPrice.countries.like(f'%{id_country}%')
                )
            )
            
            # Step 3: Verifica che weight sia nel range min_weight <= weight <= max_weight
            query = query.filter(
                and_(
                    or_(CarrierPrice.min_weight.is_(None), CarrierPrice.min_weight <= weight),
                    or_(CarrierPrice.max_weight.is_(None), CarrierPrice.max_weight >= weight)
                )
            )
            
            # Recupera tutti i risultati
            all_prices = query.all()
            
            # Filtra in memoria usando dict
            prices_with_postcode_match = []  # Record con postcode che matcha
            prices_without_postcode = []      # Record con postal_codes = NULL
            prices_with_postcode_other = []   # Record con postal_codes ma postcode non fornito o non matcha
            
            for price in all_prices:
                # Verifica che id_country sia effettivamente nella lista (non solo substring)
                if price.countries:
                    countries_list = [int(c.strip()) for c in price.countries.split(',') if c.strip().isdigit()]
                    if id_country not in countries_list:
                        continue
                
                # Se ha postal_codes, verifica se contiene il postcode
                if price.postal_codes:
                    postal_codes_list = [code.strip() for code in price.postal_codes.split(',') if code.strip()]
                    if postcode and postcode in postal_codes_list:
                        # Match esatto con postcode fornito
                        prices_with_postcode_match.append(price)
                    elif not postcode:
                        # postcode non fornito, ma record ha postal_codes (da usare come fallback)
                        prices_with_postcode_other.append(price)
                else:
                    # postal_codes è NULL
                    prices_without_postcode.append(price)
            
            # Priorità 1: Se postcode è fornito e c'è un match esatto con postcode, restituisci quello
            if postcode and prices_with_postcode_match:
                price_obj = prices_with_postcode_match[0]
                if price_obj.price_with_tax is not None:
                    return round(float(price_obj.price_with_tax), 2)
            
            # Priorità 2: Se postcode NON è fornito, preferisci record con postal_codes = NULL
            if not postcode and prices_without_postcode:
                price_obj = prices_without_postcode[0]
                if price_obj.price_with_tax is not None:
                    return round(float(price_obj.price_with_tax), 2)
            
            # Priorità 3: Se postcode NON è fornito e non ci sono record con postal_codes = NULL,
            # usa il primo record disponibile (anche se ha postal_codes)
            if not postcode and prices_with_postcode_other:
                price_obj = prices_with_postcode_other[0]
                if price_obj.price_with_tax is not None:
                    return round(float(price_obj.price_with_tax), 2)
            
            # Priorità 4: Se postcode è fornito ma non c'è match, cerca senza postcode (fallback)
            if postcode:
                # Prova prima con postal_codes = NULL
                if prices_without_postcode:
                    price_obj = prices_without_postcode[0]
                    if price_obj.price_with_tax is not None:
                        return round(float(price_obj.price_with_tax), 2)
                # Altrimenti usa qualsiasi record disponibile
                if prices_with_postcode_other:
                    price_obj = prices_with_postcode_other[0]
                    if price_obj.price_with_tax is not None:
                        return round(float(price_obj.price_with_tax), 2)
            
            return None
            
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving carrier price by criteria: {str(e)}")
