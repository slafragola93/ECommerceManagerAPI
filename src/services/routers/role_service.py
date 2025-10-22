"""
Role Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.role_service_interface import IRoleService
from src.repository.interfaces.role_repository_interface import IRoleRepository
from src.schemas.role_schema import RoleSchema, RoleResponseSchema
from src.models.role import Role
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class RoleService(IRoleService):
    """Role Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, role_repository: IRoleRepository):
        self._role_repository = role_repository
    
    async def create_role(self, role_data: RoleSchema) -> Role:
        """Crea un nuovo ruolo con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(role_data, 'name') and role_data.name:
            existing_role = self._role_repository.get_by_name(role_data.name)
            if existing_role:
                raise BusinessRuleException(
                    f"Role with name '{role_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": role_data.name}
                )
        
        # Crea il ruolo
        try:
            role = Role(**role_data.model_dump())
            role = self._role_repository.create(role)
            return role
        except Exception as e:
            raise ValidationException(f"Error creating role: {str(e)}")
    
    async def update_role(self, role_id: int, role_data: RoleSchema) -> Role:
        """Aggiorna un ruolo esistente"""
        
        # Verifica esistenza
        role = self._role_repository.get_by_id_or_raise(role_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(role_data, 'name') and role_data.name != role.name:
            existing = self._role_repository.get_by_name(role_data.name)
            if existing and existing.id_role != role_id:
                raise BusinessRuleException(
                    f"Role with name '{role_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": role_data.name}
                )
        
        # Aggiorna il ruolo
        try:
            # Aggiorna i campi
            for field_name, value in role_data.model_dump(exclude_unset=True).items():
                if hasattr(role, field_name) and value is not None:
                    setattr(role, field_name, value)
            
            updated_role = self._role_repository.update(role)
            return updated_role
        except Exception as e:
            raise ValidationException(f"Error updating role: {str(e)}")
    
    async def get_role(self, role_id: int) -> Role:
        """Ottiene un ruolo per ID"""
        role = self._role_repository.get_by_id_or_raise(role_id)
        return role
    
    async def get_roles(self, page: int = 1, limit: int = 10, **filters) -> List[Role]:
        """Ottiene la lista dei ruoli con filtri"""
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
            roles = self._role_repository.get_all(**filters)
            
            return roles
        except Exception as e:
            raise ValidationException(f"Error retrieving roles: {str(e)}")
    
    async def delete_role(self, role_id: int) -> bool:
        """Elimina un ruolo"""
        # Verifica esistenza
        self._role_repository.get_by_id_or_raise(role_id)
        
        try:
            return self._role_repository.delete(role_id)
        except Exception as e:
            raise ValidationException(f"Error deleting role: {str(e)}")
    
    async def get_roles_count(self, **filters) -> int:
        """Ottiene il numero totale di ruoli con filtri"""
        try:
            # Usa il repository con i filtri
            return self._role_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting roles: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Role"""
        # Validazioni specifiche per Role se necessarie
        pass
