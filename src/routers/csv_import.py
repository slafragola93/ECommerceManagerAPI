"""
CSV Import Router

Endpoints per import dati da file CSV con validazione e batch processing.
"""
from fastapi import APIRouter, Depends, UploadFile, File, Query, Path, status
from fastapi.responses import StreamingResponse
from typing import Optional
from io import StringIO

from src.database import get_db
from src.core.dependencies import db_dependency
from src.services.csv_import.csv_import_service import CSVImportService
from src.services.csv_import.entity_mapper import EntityMapper
from src.services.csv_import.dependency_resolver import DependencyResolver
from src.services.routers.auth_service import get_current_user, authorize
from src.services.core.wrap import check_authentication


router = APIRouter(
    prefix="/api/v1/sync/import",
    tags=["CSV Import"]
)


@router.post(
    "/csv",
    status_code=status.HTTP_200_OK,
    response_description="CSV import completed"
)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def import_csv(
    db: db_dependency,
    user: dict = Depends(get_current_user),
    file: UploadFile = File(..., description="CSV file to import"),
    entity_type: str = Query(..., description="Entity type: products, customers, addresses, brands, categories, carriers, countries, languages, payments, orders, order_details"),
    id_platform: int = Query(1, ge=0, description="Platform ID: 0=Manual, 1=PrestaShop, etc."),
    batch_size: int = Query(1000, ge=100, le=10000, description="Batch size for insert (100-10000)"),
    validate_only: bool = Query(False, description="If true, only validate without importing")
):
    """
    Import data from CSV file.
    
    **Workflow**:
    1. Parse CSV with headers
    2. Auto-detect and validate dependencies
    3. Map CSV rows to Pydantic schemas (inject id_platform)
    4. Complete validation (Pydantic + FK + unique constraints + business rules)
    5. If errors: return validation errors (no import)
    6. If valid and validate_only=false: batch insert
    7. Return import result with statistics
    
    **Entity types**: products, customers, addresses, brands, categories, carriers, 
                      countries, languages, payments, orders, order_details
    
    **id_platform**:
    - 0 = Manual/Generic
    - 1 = PrestaShop (default)
    - Future: 2 = WooCommerce, 3 = Shopify
    
    **CSV Format**:
    - First row must be headers (field names)
    - Delimiter: auto-detected (comma, semicolon, tab)
    - Encoding: UTF-8 or Latin-1
    
    **Example**: products.csv with id_platform=1
    ```csv
    id_origin,name,sku,reference,id_category,id_brand,price_without_tax,weight,quantity
    12345,Product Name,SKU123,REF001,5,3,99.99,1.5,100
    ```
    
    **Validation**:
    - All-or-nothing: if any row fails validation, no rows are imported
    - Returns detailed errors with row numbers and field names
    
    **Dependencies**:
    - System auto-detects required dependencies
    - Example: to import products, categories and brands must exist
    - Import order: Layer 1 (languages, countries...) → Layer 5 (order_details)
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        from src.core.exceptions import ValidationException, ErrorCode
        raise ValidationException(
            "Il file deve essere in formato CSV",
            ErrorCode.VALIDATION_ERROR,
            {"filename": file.filename}
        )
    
    # Read file content
    content = await file.read()
    
    # Initialize service
    import_service = CSVImportService(db)
    
    # Execute import
    result = await import_service.import_entity(
        file_content=content,
        entity_type=entity_type,
        id_platform=id_platform,
        batch_size=batch_size,
        validate_only=validate_only
    )
    
    return result.to_dict()


@router.get(
    "/templates/{entity_type}",
    status_code=status.HTTP_200_OK,
    response_description="CSV template downloaded"
)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_csv_template(
    entity_type: str = Path(..., description="Entity type for template"),
    id_platform: Optional[int] = Query(None, description="Platform ID (optional, for documentation)"),
    user: dict = Depends(get_current_user)
):
    """
    Download CSV template with correct headers for entity type.
    
    Returns a CSV file with headers only, ready to be filled with data.
    
    **Supported entity types**:
    - products
    - customers
    - addresses
    - brands
    - categories
    - carriers
    - countries
    - languages
    - payments
    - orders
    - order_details
    
    **Note**: id_platform is NOT included in CSV template (passed as query parameter during import)
    """
    # Validate entity type
    if entity_type not in EntityMapper.SCHEMA_MAPPING:
        from src.core.exceptions import NotFoundException
        raise NotFoundException("Template", entity_type, {"entity_type": entity_type})
    
    # Generate CSV template
    template_content = EntityMapper.generate_csv_template(entity_type)
    
    # Return as downloadable CSV
    return StreamingResponse(
        iter([template_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={entity_type}_template.csv"
        }
    )


@router.get(
    "/supported-entities",
    status_code=status.HTTP_200_OK
)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_supported_entities(
    user: dict = Depends(get_current_user)
):
    """
    Get list of supported entity types for CSV import.
    
    Returns entity types with their dependencies and layer information.
    """
    entities_info = []
    
    for entity_type in EntityMapper.SCHEMA_MAPPING.keys():
        dependencies = DependencyResolver.get_dependencies(entity_type)
        required_fields = EntityMapper.get_required_fields(entity_type)
        is_platform_aware = entity_type in EntityMapper.PLATFORM_AWARE_ENTITIES
        
        entities_info.append({
            "entity_type": entity_type,
            "dependencies": dependencies,
            "required_fields": required_fields,
            "is_platform_aware": is_platform_aware,
            "template_url": f"/api/v1/sync/import/templates/{entity_type}"
        })
    
    return {
        "supported_entities": entities_info,
        "dependency_graph": DependencyResolver.DEPENDENCY_GRAPH
    }

