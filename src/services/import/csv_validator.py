"""
CSV Validator for Import System.

Validates data pre-import: foreign keys, unique constraints, business rules.
Follows Single Responsibility Principle.
"""
from __future__ import annotations

from typing import List, Dict, Any, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import ValidationError as PydanticValidationError

from .models import ValidationResult, ValidationError as ImportValidationError
from .entity_mapper import EntityMapper
import time


class CSVValidator:
    """
    Validatore pre-import per dati CSV.
    
    Valida:
    - Pydantic schemas
    - Foreign keys existence
    - Unique constraints
    - Business rules
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def validate_batch(
        self,
        rows: List[Dict[str, Any]],
        entity_type: str,
        id_platform: int = 1
    ) -> ValidationResult:
        """
        Valida batch completo di righe CSV.
        
        Validazione completa pre-import per approccio tutto-o-niente.
        
        Args:
            rows: Lista righe CSV (con _row_number)
            entity_type: Tipo entità
            id_platform: ID platform
            
        Returns:
            ValidationResult con esito validazione
        """
        start_time = time.time()
        errors: List[ImportValidationError] = []
        valid_rows = 0
        
        # 1. Validate Pydantic schemas
        schema_errors = self._validate_pydantic_schemas(rows, entity_type, id_platform)
        errors.extend(schema_errors)
        
        # 2. Check for duplicate id_origin in CSV
        duplicate_errors = self._check_duplicate_origins(rows, entity_type, id_platform)
        errors.extend(duplicate_errors)
        
        # 3. Validate foreign keys
        fk_errors = await self._validate_foreign_keys(rows, entity_type, id_platform)
        errors.extend(fk_errors)
        
        # 4. Check existing records (duplicates in DB)
        existing_errors = self._check_existing_records(rows, entity_type, id_platform)
        errors.extend(existing_errors)
        
        # 5. Business rules validation (entity-specific)
        business_errors = self._validate_business_rules(rows, entity_type)
        errors.extend(business_errors)
        
        valid_rows = len(rows) - len(set(err.row_number for err in errors))
        
        validation_time = time.time() - start_time
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            total_rows=len(rows),
            valid_rows=valid_rows,
            errors=errors,
            validation_time=validation_time
        )
    
    def _validate_pydantic_schemas(
        self,
        rows: List[Dict[str, Any]],
        entity_type: str,
        id_platform: int
    ) -> List[ImportValidationError]:
        """Valida righe con Pydantic schema"""
        errors = []
        
        for row in rows:
            row_num = row.get('_row_number', 0)
            try:
                # Prova a creare schema
                EntityMapper.map_to_schema(row, entity_type, id_platform)
            except PydanticValidationError as e:
                # Estrai errori Pydantic
                for pyd_err in e.errors():
                    field_name = '.'.join(str(loc) for loc in pyd_err['loc'])
                    errors.append(ImportValidationError(
                        row_number=row_num,
                        field_name=field_name,
                        error_type='pydantic_validation',
                        message=pyd_err['msg'],
                        value=pyd_err.get('input')
                    ))
            except Exception as e:
                errors.append(ImportValidationError(
                    row_number=row_num,
                    field_name='unknown',
                    error_type='schema_error',
                    message=str(e)
                ))
        
        return errors
    
    def _check_duplicate_origins(
        self,
        rows: List[Dict[str, Any]],
        entity_type: str,
        id_platform: int
    ) -> List[ImportValidationError]:
        """Check duplicati id_origin nel CSV stesso"""
        errors = []
        seen = {}
        
        for row in rows:
            row_num = row.get('_row_number', 0)
            id_origin = row.get('id_origin')
            
            if not id_origin:
                continue
            
            # Per entity platform-aware, la chiave è (id_origin, id_platform)
            if entity_type in EntityMapper.PLATFORM_AWARE_ENTITIES:
                key = (id_origin, id_platform)
            else:
                key = id_origin
            
            if key in seen:
                errors.append(ImportValidationError(
                    row_number=row_num,
                    field_name='id_origin',
                    error_type='duplicate_in_csv',
                    message=f"Duplicate id_origin {id_origin} in CSV (first seen at row {seen[key]})",
                    value=id_origin
                ))
            else:
                seen[key] = row_num
        
        return errors
    
    async def _validate_foreign_keys(
        self,
        rows: List[Dict[str, Any]],
        entity_type: str,
        id_platform: int
    ) -> List[ImportValidationError]:
        """Valida che foreign keys esistano nel DB"""
        errors = []
        
        # Define FK fields per entity
        fk_checks = self._get_fk_checks(entity_type)
        
        if not fk_checks:
            return errors
        
        # Pre-fetch existing IDs for validation
        for fk_field, (table, id_field, platform_aware) in fk_checks.items():
            # Collect unique values da CSV
            values_to_check = set()
            for row in rows:
                value = row.get(fk_field)
                if value and value != '' and value != '0' and value != 0:
                    try:
                        values_to_check.add(int(value))
                    except (ValueError, TypeError):
                        pass
            
            if not values_to_check:
                continue
            
            # Check existence in DB
            try:
                placeholders = ','.join([f':val_{i}' for i in range(len(values_to_check))])
                params = {f'val_{i}': val for i, val in enumerate(values_to_check)}
                
                if platform_aware:
                    query = text(f"SELECT {id_field} FROM {table} WHERE {id_field} IN ({placeholders}) AND id_platform = :id_platform")
                    params['id_platform'] = id_platform
                else:
                    query = text(f"SELECT {id_field} FROM {table} WHERE {id_field} IN ({placeholders})")
                
                result = self.db.execute(query, params)
                existing = {row[0] for row in result}
                
                missing = values_to_check - existing
                
                # Trova righe con FK invalidi
                for row in rows:
                    row_num = row.get('_row_number', 0)
                    value = row.get(fk_field)
                    if value:
                        try:
                            val_int = int(value)
                            if val_int in missing:
                                errors.append(ImportValidationError(
                                    row_number=row_num,
                                    field_name=fk_field,
                                    error_type='fk_violation',
                                    message=f"Foreign key {fk_field}={val_int} not found in {table}",
                                    value=val_int
                                ))
                        except (ValueError, TypeError):
                            pass
                            
            except Exception as e:
                print(f"WARNING: FK validation error for {fk_field}: {str(e)}")
        
        return errors
    
    def _check_existing_records(
        self,
        rows: List[Dict[str, Any]],
        entity_type: str,
        id_platform: int
    ) -> List[ImportValidationError]:
        """Check records già esistenti nel DB (duplicati)"""
        errors = []
        
        table_name = self._get_table_name(entity_type)
        if not table_name:
            return errors
        
        # Collect all id_origin from CSV
        id_origins = []
        for row in rows:
            id_origin = row.get('id_origin')
            if id_origin:
                try:
                    id_origins.append(int(id_origin))
                except (ValueError, TypeError):
                    pass
        
        if not id_origins:
            return errors
        
        try:
            # Check existing by id_origin (+ id_platform se applicabile)
            placeholders = ','.join([f':id_{i}' for i in range(len(id_origins))])
            params = {f'id_{i}': id_val for i, id_val in enumerate(id_origins)}
            
            if entity_type in EntityMapper.PLATFORM_AWARE_ENTITIES:
                query = text(f"SELECT id_origin FROM {table_name} WHERE id_origin IN ({placeholders}) AND id_platform = :id_platform")
                params['id_platform'] = id_platform
            else:
                query = text(f"SELECT id_origin FROM {table_name} WHERE id_origin IN ({placeholders})")
            
            result = self.db.execute(query, params)
            existing_origins = {row[0] for row in result}
            
            # Mark rows with existing id_origin as errors
            for row in rows:
                row_num = row.get('_row_number', 0)
                id_origin = row.get('id_origin')
                if id_origin:
                    try:
                        origin_int = int(id_origin)
                        if origin_int in existing_origins:
                            errors.append(ImportValidationError(
                                row_number=row_num,
                                field_name='id_origin',
                                error_type='duplicate_in_db',
                                message=f"Record with id_origin={origin_int} already exists in database",
                                value=origin_int
                            ))
                    except (ValueError, TypeError):
                        pass
                        
        except Exception as e:
            print(f"WARNING: Error checking existing records: {str(e)}")
        
        return errors
    
    def _validate_business_rules(
        self,
        rows: List[Dict[str, Any]],
        entity_type: str
    ) -> List[ImportValidationError]:
        """Valida business rules specifiche per entity"""
        errors = []
        
        # Email unique per customers
        if entity_type == 'customers':
            seen_emails = {}
            for row in rows:
                row_num = row.get('_row_number', 0)
                email = row.get('email')
                if email:
                    email_lower = email.lower()
                    if email_lower in seen_emails:
                        errors.append(ImportValidationError(
                            row_number=row_num,
                            field_name='email',
                            error_type='unique_violation',
                            message=f"Duplicate email in CSV (first at row {seen_emails[email_lower]})",
                            value=email
                        ))
                    else:
                        seen_emails[email_lower] = row_num
        
        # SKU unique per products (per platform)
        if entity_type == 'products':
            seen_skus = {}
            for row in rows:
                row_num = row.get('_row_number', 0)
                sku = row.get('sku')
                if sku:
                    if sku in seen_skus:
                        errors.append(ImportValidationError(
                            row_number=row_num,
                            field_name='sku',
                            error_type='unique_violation',
                            message=f"Duplicate SKU in CSV (first at row {seen_skus[sku]})",
                            value=sku
                        ))
                    else:
                        seen_skus[sku] = row_num
        
        return errors
    
    def _get_fk_checks(self, entity_type: str) -> Dict[str, Tuple[str, str, bool]]:
        """
        Returns FK checks configuration: {field: (table, id_field, platform_aware)}
        
        Args:
            entity_type: Tipo entità
            
        Returns:
            Dict con configurazione FK checks
        """
        fk_config = {
            'products': {
                'id_category': ('categories', 'id_category', False),
                'id_brand': ('brands', 'id_brand', False)
            },
            'customers': {
                'id_lang': ('languages', 'id_lang', False)
            },
            'addresses': {
                'id_customer': ('customers', 'id_customer', False),
                'id_country': ('countries', 'id_country', False)
            },
            'orders': {
                'id_customer': ('customers', 'id_customer', False),
                'id_address_delivery': ('addresses', 'id_address', True),
                'id_address_invoice': ('addresses', 'id_address', True),
                'id_payment': ('payments', 'id_payment', False),
                'id_carrier': ('carriers', 'id_carrier', False)
            },
            'order_details': {
                'id_order': ('orders', 'id_order', True),
                'id_product': ('products', 'id_product', True),
                'id_tax': ('taxes', 'id_tax', False)
            }
        }
        
        return fk_config.get(entity_type, {})
    
    def _get_table_name(self, entity_type: str) -> Optional[str]:
        """Get table name for entity type"""
        table_mapping = {
            'products': 'products',
            'customers': 'customers',
            'addresses': 'addresses',
            'brands': 'brands',
            'categories': 'categories',
            'carriers': 'carriers',
            'countries': 'countries',
            'languages': 'languages',
            'payments': 'payments',
            'orders': 'orders',
            'order_details': 'order_details'
        }
        return table_mapping.get(entity_type)

