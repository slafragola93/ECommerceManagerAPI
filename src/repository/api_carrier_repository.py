"""
API Carrier Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, select
from sqlalchemy.engine import Row
from src.models.carrier_api import CarrierApi
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException

class ApiCarrierRepository(BaseRepository[CarrierApi, int], IApiCarrierRepository):
    """API Carrier Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, CarrierApi)
    
    def get_all(self, **filters) -> List[CarrierApi]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(CarrierApi.id_carrier_api))
            
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
    
    def get_by_name(self, name: str) -> Optional[CarrierApi]:
        """Ottiene un API carrier per nome (case insensitive)"""
        try:
            return self._session.query(CarrierApi).filter(
                func.lower(CarrierApi.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving API carrier by name: {str(e)}")
    
    def get_by_account_number(self, account_number: int) -> Optional[CarrierApi]:
        """Ottiene un API carrier per numero account"""
        try:
            return self._session.query(CarrierApi).filter(
                CarrierApi.account_number == account_number
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving API carrier by account number: {str(e)}")
    
    def get_auth_credentials(self, id_carrier_api: int) -> Row:
        """Get username, password, use_sandbox for auth"""
        try:
            stmt = select(
                CarrierApi.id_carrier_api,
                CarrierApi.use_sandbox
            ).where(CarrierApi.id_carrier_api == id_carrier_api)
            
            result = self._session.execute(stmt).first()
            if not result:
                raise InfrastructureException(f"CarrierApi {id_carrier_api} not found")
            return result
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving carrier auth credentials: {str(e)}")
    
    def get_active_carriers_for_init(self) -> List[dict]:
        """
        Query idratata: recupera solo id_carrier_api e name per carrier attivi.
        Utilizzato per endpoint init.
        
        Returns:
            Lista di dict con id_carrier_api e name
        """
        try:
            from sqlalchemy import text
            result = self._session.execute(
                text("""
                    SELECT id_carrier_api, name 
                    FROM carriers_api 
                    WHERE is_active = 1
                    ORDER BY id_carrier_api
                """)
            ).fetchall()
            carriers = [
                {
                    "id_carrier_api": int(row.id_carrier_api),
                    "name": str(row.name)
                }
                for row in result
            ]
            print(f"[DEBUG] Carriers recuperati dalla query: {len(carriers)}")
            return carriers
        except Exception as e:
            print(f"[ERROR] Errore query carriers: {e}")
            import traceback
            traceback.print_exc()
            raise InfrastructureException(f"Database error retrieving active carriers for init: {str(e)}")