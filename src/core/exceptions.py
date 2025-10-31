"""
Sistema di gestione errori centralizzato seguendo i principi SOLID
"""
from abc import ABC
from typing import Optional, Dict, Any
from enum import Enum

class ErrorCode(Enum):
    """Codici errore standardizzati"""
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    EMAIL_DUPLICATE = "EMAIL_DUPLICATE"
    INVALID_EMAIL_FORMAT = "INVALID_EMAIL_FORMAT"
    INVALID_PHONE_FORMAT = "INVALID_PHONE_FORMAT"
    REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
    
    # Business logic errors
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    ORDER_NOT_MODIFIABLE = "ORDER_NOT_MODIFIABLE"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    
    # Not found errors
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    CUSTOMER_NOT_FOUND = "CUSTOMER_NOT_FOUND"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    
    # Infrastructure errors
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    
    # Authentication/Authorization errors
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

class BaseApplicationException(Exception, ABC):
    """Base exception per l'applicazione"""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 400
    ):
        self.message = message
        self.error_code = error_code.value
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte l'eccezione in dizionario per la risposta API"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "status_code": self.status_code
        }

class DomainException(BaseApplicationException):
    """Eccezioni del dominio business"""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.BUSINESS_RULE_VIOLATION,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, details, 400)

class ValidationException(DomainException):
    """Errori di validazione"""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, details)

class BusinessRuleException(DomainException):
    """Violazione regole business"""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.BUSINESS_RULE_VIOLATION,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, details)

class NotFoundException(BaseApplicationException):
    """Entità non trovata"""
    
    def __init__(
        self, 
        entity_type: str,
        entity_id: Any = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if entity_id is not None:
            message = f"{entity_type} with id '{entity_id}' not found"
        else:
            message = f"{entity_type} not found"
        
        error_details = details or {}
        if entity_id is not None:
            error_details["entity_id"] = entity_id
        error_details["entity_type"] = entity_type
        
        super().__init__(
            message, 
            ErrorCode.ENTITY_NOT_FOUND, 
            error_details, 
            404
        )

class InfrastructureException(BaseApplicationException):
    """Errori di infrastruttura"""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.DATABASE_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, details, 500)

class AuthenticationException(BaseApplicationException):
    """Errori di autenticazione"""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.UNAUTHORIZED,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, details, 401)

class AuthorizationException(BaseApplicationException):
    """Errori di autorizzazione"""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.FORBIDDEN,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, details, 403)

class AlreadyExistsError(BaseApplicationException):
    """Errore quando un'entità esiste già"""
    
    def __init__(
        self, 
        message: str,
        entity_type: str = None,
        entity_id: Any = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if entity_type:
            error_details["entity_type"] = entity_type
        if entity_id is not None:
            error_details["entity_id"] = entity_id
        
        super().__init__(
            message,
            ErrorCode.ALREADY_EXISTS,
            error_details,
            409
        )

# Factory per creare eccezioni specifiche
class ExceptionFactory:
    """Factory per creare eccezioni specifiche"""
    
    @staticmethod
    def customer_not_found(customer_id: int) -> NotFoundException:
        return NotFoundException("Customer", customer_id)
    
    @staticmethod
    def order_not_found(order_id: int) -> NotFoundException:
        return NotFoundException("Order", order_id)
    
    @staticmethod
    def product_not_found(product_id: int) -> NotFoundException:
        return NotFoundException("Product", product_id)
    
    @staticmethod
    def email_duplicate(email: str) -> ValidationException:
        return ValidationException(
            f"Email '{email}' already exists",
            ErrorCode.EMAIL_DUPLICATE,
            {"email": email}
        )
    
    @staticmethod
    def invalid_email_format(email: str) -> ValidationException:
        return ValidationException(
            f"Invalid email format: '{email}'",
            ErrorCode.INVALID_EMAIL_FORMAT,
            {"email": email}
        )
    
    @staticmethod
    def required_field_missing(field_name: str) -> ValidationException:
        return ValidationException(
            f"Required field '{field_name}' is missing",
            ErrorCode.REQUIRED_FIELD_MISSING,
            {"field_name": field_name}
        )
    
    @staticmethod
    def order_not_modifiable(order_id: int, reason: str) -> BusinessRuleException:
        return BusinessRuleException(
            f"Order {order_id} cannot be modified: {reason}",
            ErrorCode.ORDER_NOT_MODIFIABLE,
            {"order_id": order_id, "reason": reason}
        )
