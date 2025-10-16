"""
Synchronization endpoints for e-commerce platforms
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from starlette import status
from sqlalchemy.orm import Session
from typing import Dict, Any

from src.database import get_db
from src.services.auth import db_dependency, get_current_user
from src.services.wrap import check_authentication
from src.services.auth import authorize
from src.services.ecommerce import PrestaShopService
from src.repository.platform_repository import PlatformRepository

router = APIRouter(
    prefix='/api/v1/sync',
    tags=['Synchronization'],
)


def get_platform_repository(db: db_dependency) -> PlatformRepository:
    return PlatformRepository(db)


def get_default_platform(pr: PlatformRepository = Depends(get_platform_repository)):
    """
    Dependency per recuperare la piattaforma di default (is_default = 1)
    
    Raises:
        HTTPException 400: Se non viene trovata nessuna piattaforma di default
    
    Returns:
        Platform: La piattaforma di default
    """
    platform = pr.get_default()
    
    if not platform:
        raise HTTPException(
            status_code=400, 
            detail="No default platform found (is_default = 1). Please set a default platform."
        )
    
    return platform


@router.post("/prestashop", status_code=status.HTTP_202_ACCEPTED)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def sync_prestashop(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    platform = Depends(get_default_platform),
    limit: int = None,
    user: dict = Depends(get_current_user)
):
    """
    Start PrestaShop incremental synchronization process
    
    This endpoint starts an asynchronous synchronization process that will:
    1. Retrieve the default platform (is_default = 1)
    2. Sync all data in the correct order (base tables first, then dependent tables)
    3. Process data in batches to avoid timeouts
    4. Log all operations for tracking
    
    Returns:
        202 Accepted: Synchronization started successfully
        400 Bad Request: Missing configuration or invalid platform
        500 Internal Server Error: Failed to start synchronization
    """
    try:
        # Start background synchronization
        background_tasks.add_task(
            _run_prestashop_sync,
            db=db,
            platform_id=platform.id_platform,
            new_elements=True,
            limit=limit
        )
        
        return {
            "message": "PrestaShop incremental synchronization started",
            "status": "accepted",
            "sync_type": "incremental",
            "platform_id": platform.id_platform,
            "platform_name": platform.name,
            "sync_id": f"prestashop_incremental_{user['id']}_{int(__import__('time').time())}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start PrestaShop synchronization: {str(e)}"
        )

@router.post("/prestashop/full", status_code=status.HTTP_202_ACCEPTED)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def sync_prestashop_full(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    platform = Depends(get_default_platform),
    user: dict = Depends(get_current_user)
):
    """
    Start PrestaShop full synchronization process
    
    This endpoint starts an asynchronous synchronization process that will:
    1. Retrieve the default platform (is_default = 1)
    2. Sync all data in the correct order (base tables first, then dependent tables)
    3. Process data in batches to avoid timeouts
    4. Log all operations for tracking
    
    Returns:
        202 Accepted: Synchronization started successfully
        400 Bad Request: Missing configuration or invalid platform
        500 Internal Server Error: Failed to start synchronization
    """
    try:
        # Start background synchronization
        background_tasks.add_task(
            _run_prestashop_sync,
            db=db,
            platform_id=platform.id_platform,
            new_elements=False
        )
        
        return {
            "message": "PrestaShop full synchronization started",
            "status": "accepted",
            "sync_type": "full",
            "platform_id": platform.id_platform,
            "platform_name": platform.name,
            "sync_id": f"prestashop_full_{user['id']}_{int(__import__('time').time())}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start PrestaShop synchronization: {str(e)}"
        )


@router.get("/prestashop/status", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_prestashop_sync_status(
    user: dict = Depends(get_current_user),
    sync_id: str = None
):
    """
    Get PrestaShop synchronization status
    
    Args:
        sync_id: Optional sync ID to get specific status
        
    Returns:
        Current synchronization status and progress
    """
    # TODO: Implement status tracking
    # For now, return a placeholder response
    return {
        "status": "not_implemented",
        "message": "Status tracking will be implemented in the next phase",
        "sync_id": sync_id
    }


@router.get("/prestashop/last-ids", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_prestashop_last_imported_ids(
    db: Session = Depends(get_db),
    platform = Depends(get_default_platform),
    user: dict = Depends(get_current_user)
):
    """
    Get the last imported ID origin for each table
    
    This endpoint shows the last imported ID for each table, which is useful for:
    - Understanding what data has been imported
    - Planning incremental synchronizations
    - Debugging sync issues
    
    Returns:
        Dict with table names and their last imported ID origins
    """
    try:
        # Create a temporary service instance to get last IDs
        async with PrestaShopService(db, platform_id=platform.id_platform) as ps_service:
            last_ids = await ps_service._get_last_imported_ids()
            
            return {
                "last_imported_ids": last_ids,
                "platform_id": platform.id_platform,
                "platform_name": platform.name,
                "message": "Last imported IDs retrieved successfully",
                "note": "These IDs represent the highest ID origin imported for each table"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get last imported IDs: {str(e)}"
        )


async def _run_prestashop_sync(db: Session, platform_id: int = 1, new_elements: bool = True, incremental: bool = None, limit: int = None):
    """
    Background task to run PrestaShop synchronization
    
    Args:
        db: Database session
        platform_id: Platform ID in the platforms table (default: 1 for PrestaShop)
        new_elements: Whether to sync only new elements (incremental sync)
        incremental: Whether to run incremental sync (only new data) - deprecated, use new_elements
        limit: Maximum number of records to process per batch
    """
    try:
        # Handle both new_elements and incremental parameters
        if incremental is not None:
            new_elements = incremental
        
        sync_type = "incremental" if new_elements else "full"
        print(f"Starting PrestaShop {sync_type} synchronization...")
        print(f"Platform ID: {platform_id}")
        
        # Create PrestaShop service instance
        # Note: limit parameter is not currently supported by PrestaShopService
        # but we log it for future implementation
        if limit:
            print(f"Limit parameter set to {limit} (not yet implemented in PrestaShopService)")
        
        async with PrestaShopService(db, platform_id, new_elements=new_elements) as ps_service:
            print(f"Base URL: {ps_service.base_url}")
            print(f"API Key: {ps_service.api_key[:10]}...")
            # Run synchronization based on type
            results = await ps_service.sync_all_data()
            
            print(f"{sync_type.capitalize()} synchronization completed:")
            print(f"  Total processed: {results['total_processed']}")
            print(f"  Total errors: {results['total_errors']}")
            print(f"  Status: {results['status']}")
            
            if new_elements and 'last_ids' in results:
                print(f"  Last imported IDs: {results['last_ids']}")
            
            # Log detailed results
            for phase in results['phases']:
                print(f"  Phase: {phase['phase']}")
                print(f"    Processed: {phase['total_processed']}")
                print(f"    Errors: {phase['total_errors']}")
                
                for func_result in phase['functions']:
                    status_icon = "✅" if func_result['status'] == 'SUCCESS' else "❌"
                    print(f"    {status_icon} {func_result['function']}: {func_result['processed']} records")
                    if func_result['status'] == 'ERROR':
                        print(f"      Error: {func_result['error']}")
        
    except Exception as e:
        print(f"PrestaShop {sync_type} synchronization failed: {str(e)}")
        # TODO: Log error to database or external logging system
        raise


@router.post("/test-connection", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def test_prestashop_connection(
    db: Session = Depends(get_db),
    platform = Depends(get_default_platform),
    user: dict = Depends(get_current_user)
):
    """
    Test PrestaShop API connection
    
    This endpoint tests the connection to PrestaShop API using the ecommerce configurations.
    Useful for verifying configuration before starting a full synchronization.
    
    Returns:
        200 OK: Connection successful
        400 Bad Request: Missing configuration
        401 Unauthorized: Invalid credentials
        500 Internal Server Error: Connection failed
    """
    try:
        # Test connection
        async with PrestaShopService(db, platform_id=platform.id_platform) as ps_service:
            # Try to get a simple endpoint (languages)
            try:
                response = await ps_service._make_request('/api/languages')
                
                return {
                    "status": "success",
                    "message": "PrestaShop connection successful",
                    "platform_id": platform.id_platform,
                    "platform_name": platform.name,
                    "base_url": ps_service.base_url,
                    "api_key_preview": f"{ps_service.api_key[:10]}..." if len(ps_service.api_key) > 10 else "***",
                    "test_endpoint": "/api/languages",
                    "response_keys": list(response.keys()) if response else [],
                    "response_sample": str(response)[:500] if response else "No response"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"PrestaShop connection failed: {str(e)}",
                    "platform_id": platform.id_platform,
                    "platform_name": platform.name,
                    "test_endpoint": "/api/languages",
                    "error_details": str(e)
                }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PrestaShop connection test failed: {str(e)}"
        )