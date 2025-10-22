"""
Carrier Assignment Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.carrier_assignment_service_interface import ICarrierAssignmentService
from src.repository.interfaces.carrier_assignment_repository_interface import ICarrierAssignmentRepository
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.schemas.carrier_assignment_schema import CarrierAssignmentSchema, CarrierAssignmentUpdateSchema
from src.models.carrier_assignment import CarrierAssignment
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class CarrierAssignmentService(ICarrierAssignmentService):
    """Carrier Assignment Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, 
                 carrier_assignment_repository: ICarrierAssignmentRepository,
                 api_carrier_repository: IApiCarrierRepository):
        self._carrier_assignment_repository = carrier_assignment_repository
        self._api_carrier_repository = api_carrier_repository
    
    async def create_carrier_assignment(self, assignment_data: CarrierAssignmentSchema) -> CarrierAssignment:
        """Crea una nuova assegnazione carrier con validazioni business"""
        
        # Business Rule 1: Verifica che il carrier API esista
        carrier_api = self._api_carrier_repository.get_by_id(assignment_data.id_carrier_api)
        if not carrier_api:
            raise BusinessRuleException(
                f"Carrier API with ID {assignment_data.id_carrier_api} does not exist",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"id_carrier_api": assignment_data.id_carrier_api}
            )
        
        # Business Rule 2: Validazione peso
        if assignment_data.min_weight is not None and assignment_data.max_weight is not None:
            if assignment_data.max_weight < assignment_data.min_weight:
                raise BusinessRuleException(
                    "Il peso massimo deve essere maggiore o uguale al peso minimo",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"min_weight": assignment_data.min_weight, "max_weight": assignment_data.max_weight}
                )
        
        # Crea l'assegnazione
        try:
            assignment = CarrierAssignment(**assignment_data.model_dump())
            assignment = self._carrier_assignment_repository.create(assignment)
            return assignment
        except Exception as e:
            raise ValidationException(f"Error creating carrier assignment: {str(e)}")
    
    async def update_carrier_assignment(self, assignment_id: int, assignment_data: CarrierAssignmentUpdateSchema) -> CarrierAssignment:
        """Aggiorna un'assegnazione carrier esistente"""
        
        # Verifica esistenza
        assignment = self._carrier_assignment_repository.get_by_id_or_raise(assignment_id)
        
        # Business Rule: Se cambia il carrier API, deve esistere
        if assignment_data.id_carrier_api is not None and assignment_data.id_carrier_api != assignment.id_carrier_api:
            carrier_api = self._api_carrier_repository.get_by_id(assignment_data.id_carrier_api)
            if not carrier_api:
                raise BusinessRuleException(
                    f"Carrier API with ID {assignment_data.id_carrier_api} does not exist",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"id_carrier_api": assignment_data.id_carrier_api}
                )
        
        # Business Rule: Validazione peso se forniti
        min_weight = assignment_data.min_weight if assignment_data.min_weight is not None else assignment.min_weight
        max_weight = assignment_data.max_weight if assignment_data.max_weight is not None else assignment.max_weight
        
        if min_weight is not None and max_weight is not None:
            if max_weight < min_weight:
                raise BusinessRuleException(
                    "Il peso massimo deve essere maggiore o uguale al peso minimo",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"min_weight": min_weight, "max_weight": max_weight}
                )
        
        # Aggiorna l'assegnazione
        try:
            # Aggiorna i campi
            for field_name, value in assignment_data.model_dump(exclude_unset=True).items():
                if hasattr(assignment, field_name) and value is not None:
                    setattr(assignment, field_name, value)
            
            updated_assignment = self._carrier_assignment_repository.update(assignment)
            return updated_assignment
        except Exception as e:
            raise ValidationException(f"Error updating carrier assignment: {str(e)}")
    
    async def get_carrier_assignment(self, assignment_id: int) -> CarrierAssignment:
        """Ottiene un'assegnazione carrier per ID"""
        assignment = self._carrier_assignment_repository.get_by_id_or_raise(assignment_id)
        return assignment
    
    async def get_carrier_assignments(self, page: int = 1, limit: int = 10, **filters) -> List[CarrierAssignment]:
        """Ottiene la lista delle assegnazioni carrier con filtri"""
        try:
            # Validazione parametri
            if page < 1:
                page = 1
            if limit < 1:
                limit = 10
            
            # Aggiungi page e limit ai filtri
            filters['page'] = page
            filters['limit'] = limit
            
            # Usa il repository con i filtri
            assignments = self._carrier_assignment_repository.get_all(**filters)
            
            return assignments
        except Exception as e:
            raise ValidationException(f"Error retrieving carrier assignments: {str(e)}")
    
    async def delete_carrier_assignment(self, assignment_id: int) -> bool:
        """Elimina un'assegnazione carrier"""
        # Verifica esistenza
        self._carrier_assignment_repository.get_by_id_or_raise(assignment_id)
        
        try:
            return self._carrier_assignment_repository.delete(assignment_id)
        except Exception as e:
            raise ValidationException(f"Error deleting carrier assignment: {str(e)}")
    
    async def get_carrier_assignments_count(self, **filters) -> int:
        """Ottiene il numero totale di assegnazioni carrier con filtri"""
        try:
            return self._carrier_assignment_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting carrier assignments: {str(e)}")
    
    async def get_assignments_by_carrier_api(self, carrier_api_id: int) -> List[CarrierAssignment]:
        """Ottiene tutte le assegnazioni per un carrier API specifico"""
        try:
            # Verifica che il carrier API esista
            carrier_api = self._api_carrier_repository.get_by_id(carrier_api_id)
            if not carrier_api:
                raise NotFoundException(f"Carrier API with ID {carrier_api_id} not found")
            
            assignments = self._carrier_assignment_repository.get_by_carrier_api_id(carrier_api_id)
            return assignments
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(f"Error retrieving assignments by carrier API: {str(e)}")
    
    async def find_matching_assignment(self, postal_code: Optional[str] = None, 
                                     country_id: Optional[int] = None,
                                     origin_carrier_id: Optional[int] = None,
                                     weight: Optional[float] = None) -> Optional[CarrierAssignment]:
        """Trova l'assegnazione carrier che corrisponde ai criteri specificati"""
        try:
            # Ottieni tutte le assegnazioni
            all_assignments = self._carrier_assignment_repository.get_all()
            
            if not all_assignments:
                return None
            
            # Filtra le assegnazioni in base ai criteri
            matching_assignments = []
            
            for assignment in all_assignments:
                match = True
                
                # Filtro per codice postale
                if postal_code and assignment.postal_codes:
                    postal_codes_list = [code.strip() for code in assignment.postal_codes.split(',') if code.strip()]
                    if postal_code not in postal_codes_list:
                        match = False
                
                # Filtro per paese
                if country_id and assignment.countries:
                    countries_list = [int(country.strip()) for country in assignment.countries.split(',') if country.strip().isdigit()]
                    if country_id not in countries_list:
                        match = False
                
                # Filtro per carrier di origine
                if origin_carrier_id and assignment.origin_carriers:
                    carriers_list = [int(carrier.strip()) for carrier in assignment.origin_carriers.split(',') if carrier.strip().isdigit()]
                    if origin_carrier_id not in carriers_list:
                        match = False
                
                # Filtro per peso
                if weight is not None:
                    if assignment.min_weight is not None and weight < assignment.min_weight:
                        match = False
                    if assignment.max_weight is not None and weight > assignment.max_weight:
                        match = False
                
                if match:
                    matching_assignments.append(assignment)
            
            # Restituisci la prima assegnazione che corrisponde
            # In un'implementazione più sofisticata, potresti implementare una logica di priorità
            return matching_assignments[0] if matching_assignments else None
            
        except Exception as e:
            raise ValidationException(f"Error finding matching assignment: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Carrier Assignment"""
        if hasattr(data, 'id_carrier_api'):
            carrier_api = self._api_carrier_repository.get_by_id(data.id_carrier_api)
            if not carrier_api:
                raise BusinessRuleException(
                    f"Carrier API with ID {data.id_carrier_api} does not exist",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"id_carrier_api": data.id_carrier_api}
                )
