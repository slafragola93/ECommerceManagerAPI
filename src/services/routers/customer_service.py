"""
Customer Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Tuple
from src.services.interfaces.customer_service_interface import ICustomerService
from src.repository.interfaces.customer_repository_interface import ICustomerRepository
from src.schemas.customer_schema import CustomerSchema, CustomerResponseSchema
from src.models.customer import Customer
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)
from src.events.decorators import emit_event_on_success
from src.events.core.event import EventType
from src.events.extractors import (
    extract_customer_created_data,
    extract_customer_updated_data,
    extract_customer_deleted_data
)
import re

class CustomerService(ICustomerService):
    """Customer Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, customer_repository: ICustomerRepository):
        self._customer_repository = customer_repository
    
    @emit_event_on_success(
        event_type=EventType.CUSTOMER_CREATED,
        data_extractor=extract_customer_created_data,
        source="customer_service.create_customer"
    )
    async def create_customer(self, customer_data: CustomerSchema, user: dict = None) -> Tuple[Customer, bool]:
        """
        Crea un nuovo cliente con validazioni business.
        Se l'email esiste già, restituisce il customer esistente.
        
        Args:
            customer_data: Dati del customer da creare
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            Tuple[Customer, bool]: (customer, is_created) dove is_created è True se creato, False se esistente
        """
        
        # Business Rule 1: Validazione email
        await self._validate_email(customer_data.email)
        
        # Business Rule 2: Controlla se email esiste già
        existing_customer = self._customer_repository.get_by_email(customer_data.email)
        if existing_customer:
            # Restituisce il customer esistente invece di sollevare un'eccezione
            return (existing_customer, False)
        
        # Business Rule 3: Validazione nome e cognome
        await self._validate_name_fields(customer_data.firstname, customer_data.lastname)
        
        # Business Rule 4: Validazione origin_id se fornito
        if customer_data.id_origin and customer_data.id_origin != 0:
            existing_origin = self._customer_repository.get_by_origin_id(str(customer_data.id_origin))
            if existing_origin:
                raise BusinessRuleException(
                    f"Cliente con origin_id '{customer_data.id_origin}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"origin_id": customer_data.id_origin}
                )
        
        # Crea il cliente
        try:
            # Converti CustomerSchema in Customer model
            from src.models.customer import Customer
            from datetime import date
            customer = Customer(**customer_data.model_dump())
            customer.date_add = date.today()  # Aggiungi data di creazione
            customer = self._customer_repository.create(customer)
            return (customer, True)
        except Exception as e:
            raise ValidationException(f"Errore nella creazione del cliente: {str(e)}")
    
    @emit_event_on_success(
        event_type=EventType.CUSTOMER_UPDATED,
        data_extractor=extract_customer_updated_data,
        source="customer_service.update_customer"
    )
    async def update_customer(self, customer_id: int, customer_data: CustomerSchema, user: dict = None) -> Customer:
        """
        Aggiorna un cliente esistente.
        
        Args:
            customer_id: ID del customer da aggiornare
            customer_data: Nuovi dati del customer
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            Customer aggiornato
        """
        
        # Verifica esistenza
        customer = self._customer_repository.get_by_id_or_raise(customer_id)
        
        # Business Rule: Se email cambia, deve essere unica
        if customer_data.email != customer.email:
            await self._validate_email(customer_data.email)
            existing = self._customer_repository.get_by_email(customer_data.email)
            if existing and existing.id_customer != customer_id:
                raise ExceptionFactory.email_duplicate(customer_data.email)
        
        # Business Rule: Validazione nome e cognome
        await self._validate_name_fields(customer_data.firstname, customer_data.lastname)
        
        # Aggiorna il cliente
        try:
            # Aggiorna i campi
            for field_name, value in customer_data.model_dump(exclude_unset=True).items():
                if hasattr(customer, field_name) and value is not None:
                    setattr(customer, field_name, value)
            
            updated_customer = self._customer_repository.update(customer)
            return updated_customer
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento del cliente: {str(e)}")
    
    async def get_customer(self, customer_id: int) -> Customer:
        """Ottiene un cliente per ID"""
        customer = self._customer_repository.get_by_id_or_raise(customer_id)
        return customer
    
    async def get_customers(self, page: int = 1, limit: int = 10, **filters) -> List[Customer]:
        """Ottiene la lista dei clienti con filtri"""
        try:
            # Validazione parametri
            if page < 1:
                page = 1
            if limit < 1:
                limit = 10
            
            # Aggiungi page e limit ai filtri
            filters['page'] = page
            filters['limit'] = limit
            
            # Usa il repository con i filtri - restituisce direttamente i modelli Customer
            customers = self._customer_repository.get_all(**filters)
            
            return customers
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei clienti: {str(e)}")
    
    @emit_event_on_success(
        event_type=EventType.CUSTOMER_DELETED,
        data_extractor=extract_customer_deleted_data,
        source="customer_service.delete_customer"
    )
    async def delete_customer(self, customer_id: int, user: dict = None) -> bool:
        """
        Elimina un cliente.
        
        Args:
            customer_id: ID del customer da eliminare
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            True se eliminato con successo
        """
        # Verifica esistenza
        self._customer_repository.get_by_id_or_raise(customer_id)
        
        # Business Rule: Verifica se il cliente ha ordini associati
        # (Questo dovrebbe essere implementato con un check negli ordini)
        
        try:
            return self._customer_repository.delete(customer_id)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione del cliente: {str(e)}")
    
    async def search_customers(self, search_term: str) -> List[Customer]:
        """Cerca clienti per termine di ricerca"""
        if not search_term or len(search_term.strip()) < 2:
            raise ValidationException("Il termine di ricerca deve essere di almeno 2 caratteri")
        
        try:
            customers = self._customer_repository.search_by_name(search_term.strip())
            return customers
        except Exception as e:
            raise ValidationException(f"Errore nella ricerca dei clienti: {str(e)}")
    
    async def _validate_email(self, email: str) -> None:
        """Valida il formato dell'email"""
        if not email:
            raise ExceptionFactory.required_field_missing("email")
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ExceptionFactory.invalid_email_format(email)
    
    async def get_customers_count(self, **filters) -> int:
        """Ottiene il numero totale di clienti con filtri"""
        try:
            # Usa il repository con i filtri
            return self._customer_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Errore nel conteggio dei clienti: {str(e)}")
    
    async def _validate_name_fields(self, firstname: str, lastname: str) -> None:
        """Valida i campi nome e cognome"""
        if not firstname or not firstname.strip():
            raise ExceptionFactory.required_field_missing("firstname")
        
        if not lastname or not lastname.strip():
            raise ExceptionFactory.required_field_missing("lastname")
        
        if len(firstname.strip()) < 2:
            raise ValidationException("Il nome deve essere di almeno 2 caratteri")
        
        if len(lastname.strip()) < 2:
            raise ValidationException("Il cognome deve essere di almeno 2 caratteri")
