"""
OrderPackage Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.order_package_service_interface import IOrderPackageService
from src.repository.interfaces.order_package_repository_interface import IOrderPackageRepository
from src.schemas.order_package_schema import OrderPackageSchema
from src.models.order_package import OrderPackage
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class OrderPackageService(IOrderPackageService):
    """OrderPackage Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, order_package_repository: IOrderPackageRepository):
        self._order_package_repository = order_package_repository
    
    async def create_order_package(self, order_package_data: OrderPackageSchema) -> OrderPackage:
        """Crea un nuovo order_package con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(order_package_data, 'name') and order_package_data.name:
            existing_order_package = self._order_package_repository.get_by_name(order_package_data.name)
            if existing_order_package:
                raise BusinessRuleException(
                    f"OrderPackage with name '{order_package_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": order_package_data.name}
                )
        
        # Crea il order_package
        try:
            order_package = OrderPackage(**order_package_data.model_dump())
            order_package = self._order_package_repository.create(order_package)
            return order_package
        except Exception as e:
            raise ValidationException(f"Error creating order_package: {str(e)}")
    
    async def update_order_package(self, order_package_id: int, order_package_data: OrderPackageSchema) -> OrderPackage:
        """Aggiorna un order_package esistente"""
        
        # Verifica esistenza
        order_package = self._order_package_repository.get_by_id_or_raise(order_package_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(order_package_data, 'name') and order_package_data.name != order_package.name:
            existing = self._order_package_repository.get_by_name(order_package_data.name)
            if existing and existing.id_order_package != order_package_id:
                raise BusinessRuleException(
                    f"OrderPackage with name '{order_package_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": order_package_data.name}
                )
        
        # Aggiorna il order_package
        try:
            # Aggiorna i campi
            for field_name, value in order_package_data.model_dump(exclude_unset=True).items():
                if hasattr(order_package, field_name) and value is not None:
                    setattr(order_package, field_name, value)
            
            updated_order_package = self._order_package_repository.update(order_package)
            return updated_order_package
        except Exception as e:
            raise ValidationException(f"Error updating order_package: {str(e)}")
    
    async def get_order_package(self, order_package_id: int) -> OrderPackage:
        """Ottiene un order_package per ID"""
        order_package = self._order_package_repository.get_by_id_or_raise(order_package_id)
        return order_package
    
    async def get_order_packages(self, page: int = 1, limit: int = 10, **filters) -> List[OrderPackage]:
        """Ottiene la lista dei order_package con filtri"""
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
            order_packages = self._order_package_repository.get_all(**filters)
            
            return order_packages
        except Exception as e:
            raise ValidationException(f"Error retrieving order_packages: {str(e)}")
    
    async def delete_order_package(self, order_package_id: int) -> bool:
        """Elimina un order_package"""
        # Verifica esistenza
        self._order_package_repository.get_by_id_or_raise(order_package_id)
        
        try:
            return self._order_package_repository.delete(order_package_id)
        except Exception as e:
            raise ValidationException(f"Error deleting order_package: {str(e)}")
    
    async def get_order_packages_count(self, **filters) -> int:
        """Ottiene il numero totale di order_package con filtri"""
        try:
            # Usa il repository con i filtri
            return self._order_package_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting order_packages: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per OrderPackage"""
        # Validazioni specifiche per OrderPackage se necessarie
        pass
