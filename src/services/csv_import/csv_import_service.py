"""
CSV Import Service - Main orchestration service.

Coordinates the entire CSV import workflow following SOLID principles.
"""
from __future__ import annotations

import time
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from .models import ImportResult, ValidationError
from .csv_parser import CSVParser
from .csv_validator import CSVValidator
from .dependency_resolver import DependencyResolver
from .entity_mapper import EntityMapper

from src.core.exceptions import ValidationException, InfrastructureException, ErrorCode


class CSVImportService:
    """
    Service principale per orchestrazione import CSV.
    
    Coordina: parsing, validazione, dependency checking, batch insert.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.validator = CSVValidator(db)
    
    async def import_entity(
        self,
        file_content: bytes,
        entity_type: str,
        id_platform: int = 1,
        batch_size: int = 1000,
        validate_only: bool = False
    ) -> ImportResult:
        """
        Import completo entity da CSV.
        
        Workflow:
        1. Validate entity type
        2. Parse CSV
        3. Check dependencies
        4. Map to schemas
        5. Validate all (tutto-o-niente)
        6. Import if valid
        7. Return result
        
        Args:
            file_content: File CSV in bytes
            entity_type: Tipo entità (products, customers, ecc.)
            id_platform: ID platform (default: 1)
            batch_size: Dimensione batch insert (default: 1000)
            validate_only: Se True, solo validazione senza import
            
        Returns:
            ImportResult con statistiche e dettagli
        """
        started_at = datetime.now()
        
        # Step 1: Validate entity type
        if entity_type not in EntityMapper.SCHEMA_MAPPING:
            raise ValidationException(
                f"Unknown entity type: {entity_type}",
                ErrorCode.VALIDATION_ERROR,
                {"entity_type": entity_type, "supported": list(EntityMapper.SCHEMA_MAPPING.keys())}
            )
        
        try:
            # Step 2: Parse CSV
            required_fields = EntityMapper.get_required_fields(entity_type)
            headers, rows = CSVParser.parse_csv(file_content, entity_type, required_fields)
            
            print(f"📝 Parsed {len(rows)} rows from CSV for {entity_type}")
            
            # Step 3: Check dependencies
            deps_valid, missing_deps = DependencyResolver.validate_dependencies(
                entity_type, 
                self.db,
                id_platform
            )
            
            if not deps_valid:
                raise ValidationException(
                    f"Missing dependencies for {entity_type}: {', '.join(missing_deps)}",
                    ErrorCode.VALIDATION_ERROR,
                    {"missing_dependencies": missing_deps}
                )
            
            # Step 4: Map to schemas
            print(f"🔄 Mapping {len(rows)} rows to {entity_type} schemas...")
            mapped_data = []
            mapping_errors = []
            
            for row in rows:
                row_num = row.get('_row_number', 0)
                try:
                    # Passa db session per order_details (necessario per lookup id_origin->id_product e Tax->id_tax)
                    db_session = self.db if entity_type == 'order_details' else None
                    schema_instance = EntityMapper.map_to_schema(row, entity_type, id_platform, db_session)
                    mapped_data.append(schema_instance)
                except Exception as e:
                    mapping_errors.append(ValidationError(
                        row_number=row_num,
                        field_name='mapping',
                        error_type='mapping_error',
                        message=str(e)
                    ))
            
            if mapping_errors:
                print(f"❌ Mapping failed: {len(mapping_errors)} errors")
                return ImportResult(
                    entity_type=entity_type,
                    id_platform=id_platform,
                    total_rows=len(rows),
                    validated_rows=0,
                    inserted_rows=0,
                    skipped_rows=len(rows),
                    errors=mapping_errors,
                    started_at=started_at,
                    completed_at=datetime.now()
                )
            
            # Step 5: Validate all
            print(f"✓ Validating {len(mapped_data)} {entity_type}...")
            validation_result = await self.validator.validate_batch(rows, entity_type, id_platform)
            
            if not validation_result.is_valid:
                print(f"❌ Validation failed: {len(validation_result.errors)} errors")
                return ImportResult(
                    entity_type=entity_type,
                    id_platform=id_platform,
                    total_rows=len(rows),
                    validated_rows=validation_result.valid_rows,
                    inserted_rows=0,
                    skipped_rows=len(rows) - validation_result.valid_rows,
                    errors=validation_result.errors,
                    validation_time=validation_result.validation_time,
                    started_at=started_at,
                    completed_at=datetime.now()
                )
            
            # Step 6: If validate_only, return now
            if validate_only:
                print(f"✓ Validation passed: {len(mapped_data)} valid rows (validate_only mode)")
                return ImportResult(
                    entity_type=entity_type,
                    id_platform=id_platform,
                    total_rows=len(rows),
                    validated_rows=len(mapped_data),
                    inserted_rows=0,
                    skipped_rows=0,
                    errors=[],
                    validation_time=validation_result.validation_time,
                    started_at=started_at,
                    completed_at=datetime.now()
                )
            
            # Step 7: Import
            print(f"💾 Importing {len(mapped_data)} {entity_type}...")
            import_start = time.time()
            
            inserted_count = await self._bulk_insert(
                mapped_data,
                entity_type,
                id_platform,
                batch_size
            )
            
            import_time = time.time() - import_start
            
            print(f"✅ Import completed: {inserted_count}/{len(rows)} records inserted")
            
            return ImportResult(
                entity_type=entity_type,
                id_platform=id_platform,
                total_rows=len(rows),
                validated_rows=len(mapped_data),
                inserted_rows=inserted_count,
                skipped_rows=len(rows) - inserted_count,
                errors=[],
                validation_time=validation_result.validation_time,
                import_time=import_time,
                started_at=started_at,
                completed_at=datetime.now()
            )
            
        except ValidationException:
            raise
        except Exception as e:
            raise InfrastructureException(
                f"Error importing {entity_type} from CSV: {str(e)}",
                ErrorCode.DATABASE_ERROR,
                {"entity_type": entity_type, "error": str(e)}
            )
    
    async def _bulk_insert(
        self,
        data_list: List[Any],
        entity_type: str,
        id_platform: int,
        batch_size: int
    ) -> int:
        """
        Execute bulk insert usando repository appropriato.
        
        Args:
            data_list: Lista schema instances
            entity_type: Tipo entità
            id_platform: ID platform
            batch_size: Dimensione batch
            
        Returns:
            Numero records inseriti
        """
        # Get appropriate repository and call bulk_create_csv_import
        repository = self._get_repository(entity_type)
        
        # Entity platform-aware hanno firma diversa
        if entity_type in EntityMapper.PLATFORM_AWARE_ENTITIES:
            if entity_type == 'products':
                # ProductRepository ha bulk_create standard
                return repository.bulk_create(data_list, batch_size)
            else:
                # Address, Order hanno bulk_create_csv_import con id_platform
                return repository.bulk_create_csv_import(data_list, id_platform, batch_size)
        else:
            return repository.bulk_create_csv_import(data_list, batch_size)
    
    def _get_repository(self, entity_type: str):
        """Get repository instance for entity type"""
        repository_mapping = {
            'products': ('src.repository.product_repository', 'ProductRepository'),
            'customers': ('src.repository.customer_repository', 'CustomerRepository'),
            'addresses': ('src.repository.address_repository', 'AddressRepository'),
            'brands': ('src.repository.brand_repository', 'BrandRepository'),
            'categories': ('src.repository.category_repository', 'CategoryRepository'),
            'carriers': ('src.repository.carrier_repository', 'CarrierRepository'),
            'countries': ('src.repository.country_repository', 'CountryRepository'),
            'languages': ('src.repository.lang_repository', 'LangRepository'),
            'payments': ('src.repository.payment_repository', 'PaymentRepository'),
            'orders': ('src.repository.order_repository', 'OrderRepository'),
            'order_details': ('src.repository.order_detail_repository', 'OrderDetailRepository')
        }
        
        module_path, class_name = repository_mapping.get(entity_type, (None, None))
        
        if not module_path:
            raise ValueError(f"No repository found for entity type: {entity_type}")
        
        # Dynamic import
        import importlib
        module = importlib.import_module(module_path)
        repo_class = getattr(module, class_name)
        
        return repo_class(self.db)

