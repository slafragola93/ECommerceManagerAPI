"""
Synchronization endpoints for e-commerce platforms
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from starlette import status
from sqlalchemy.orm import Session
from typing import Dict, Any

from .dependencies import db_dependency, user_dependency
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


@router.post("/prestashop", status_code=status.HTTP_202_ACCEPTED)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def sync_prestashop(
    background_tasks: BackgroundTasks,
    user: user_dependency,
    db: db_dependency,
    pr: PlatformRepository = Depends(get_platform_repository),
    limit: int = None
):
    """
    Start PrestaShop full synchronization process
    
    This endpoint starts an asynchronous synchronization process that will:
    1. Retrieve PrestaShop API credentials from platforms table (ID 1)
    2. Sync all data in the correct order (base tables first, then dependent tables)
    3. Process data in batches to avoid timeouts
    4. Log all operations for tracking
    
    Returns:
        202 Accepted: Synchronization started successfully
        400 Bad Request: Missing configuration or invalid credentials
        500 Internal Server Error: Failed to start synchronization
    """
    try:
        # Get PrestaShop configuration from platforms table (ID 1)
        platform = pr.get_by_id(1)
        
        if not platform:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop platform not found in platforms table (ID 1)"
            )
        
        api_key = platform.api_key
        base_url = platform.url
        
        if not api_key:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop API key not found in platforms table"
            )
        
        if not base_url:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop base URL not found in platforms table"
            )
        
        # Start background synchronization
        background_tasks.add_task(
            _run_prestashop_sync,
            db=db,
            platform_id=1,
            new_elements=True,
            limit=limit
        )
        
        return {
            "message": "PrestaShop incremental synchronization started",
            "status": "accepted",
            "sync_type": "incremental",
            "sync_id": f"prestashop_full_{user['id']}_{int(__import__('time').time())}"
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
    user: user_dependency,
    db: db_dependency,
    pr: PlatformRepository = Depends(get_platform_repository)
):
    """
    Start PrestaShop full synchronization process
    
    This endpoint starts an asynchronous synchronization process that will:
    1. Retrieve PrestaShop API credentials from platforms table (ID 1)
    2. Sync all data in the correct order (base tables first, then dependent tables)
    3. Process data in batches to avoid timeouts
    4. Log all operations for tracking
    
    Returns:
        202 Accepted: Synchronization started successfully
        400 Bad Request: Missing configuration or invalid credentials
        500 Internal Server Error: Failed to start synchronization
    """
    try:
        # Get PrestaShop configuration from platforms table (ID 1)
        platform = pr.get_by_id(1)
        
        if not platform:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop platform not found in platforms table (ID 1)"
            )
        
        api_key = platform.api_key
        base_url = platform.url
        
        if not api_key:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop API key not found in platforms table"
            )
        
        if not base_url:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop base URL not found in platforms table"
            )
        
        # Start background synchronization
        background_tasks.add_task(
            _run_prestashop_sync,
            db=db,
            platform_id=1,
            new_elements=False
        )
        
        return {
            "message": "PrestaShop full synchronization started",
            "status": "accepted",
            "sync_type": "full",
            "sync_id": f"prestashop_full_{user['id']}_{int(__import__('time').time())}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start PrestaShop synchronization: {str(e)}"
        )


@router.post("/prestashop/incremental", status_code=status.HTTP_202_ACCEPTED)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def sync_prestashop_incremental(
    background_tasks: BackgroundTasks,
    user: user_dependency,
    db: db_dependency,
    pr: PlatformRepository = Depends(get_platform_repository),
    new_elements: bool = True
):
    """
    Start PrestaShop incremental synchronization process
    
    This endpoint starts an asynchronous incremental synchronization that will:
    1. Retrieve PrestaShop API credentials from platforms table (ID 1)
    2. Get the last imported ID origin for each table
    3. Sync only new data (ID origin > last imported ID)
    4. Process data in batches to avoid timeouts
    5. Log all operations for tracking
    
    This is much faster than full sync as it only processes new records.
    
    Returns:
        202 Accepted: Incremental synchronization started successfully
        400 Bad Request: Missing configuration or invalid credentials
        500 Internal Server Error: Failed to start synchronization
    """
    try:
        # Get PrestaShop configuration from platforms table (ID 1)
        platform = pr.get_by_id(1)
        
        if not platform:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop platform not found in platforms table (ID 1)"
            )
        
        api_key = platform.api_key
        base_url = platform.url
        
        if not api_key:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop API key not found in platforms table"
            )
        
        if not base_url:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop base URL not found in platforms table"
            )
        
        # Start background incremental synchronization
        background_tasks.add_task(
            _run_prestashop_sync,
            db=db,
            platform_id=1,
            new_elements=new_elements,
            incremental=True
        )
        
        return {
            "message": "PrestaShop incremental synchronization started",
            "status": "accepted",
            "sync_type": "incremental",
            "sync_id": f"prestashop_incremental_{user['id']}_{int(__import__('time').time())}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start PrestaShop incremental synchronization: {str(e)}"
        )


@router.get("/prestashop/status", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_prestashop_sync_status(
    user: user_dependency,
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
    user: user_dependency,
    db: db_dependency
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
        async with PrestaShopService(db, platform_id=1) as ps_service:
            last_ids = await ps_service._get_last_imported_ids()
            
            return {
                "last_imported_ids": last_ids,
                "message": "Last imported IDs retrieved successfully",
                "note": "These IDs represent the highest ID origin imported for each table"
            }
            
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
    user: user_dependency,
    db: db_dependency,
    pr: PlatformRepository = Depends(get_platform_repository)
):
    """
    Test PrestaShop API connection
    
    This endpoint tests the connection to PrestaShop API using the configured credentials.
    Useful for verifying configuration before starting a full synchronization.
    
    Returns:
        200 OK: Connection successful
        400 Bad Request: Missing configuration
        401 Unauthorized: Invalid credentials
        500 Internal Server Error: Connection failed
    """
    try:
        # Get PrestaShop configuration from platforms table (ID 1)
        platform = pr.get_by_id(1)
        
        if not platform:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop platform not found in platforms table (ID 1)"
            )
        
        api_key = platform.api_key
        base_url = platform.url
        
        if not api_key:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop API key not found in platforms table"
            )
        
        if not base_url:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop base URL not found in platforms table"
            )
        
        # Test connection
        async with PrestaShopService(db, platform_id=1) as ps_service:
            # Try to get a simple endpoint (languages)
            try:
                response = await ps_service._make_request('/api/languages')
                
                return {
                    "status": "success",
                    "message": "PrestaShop connection successful",
                    "base_url": base_url,
                    "api_key_preview": f"{api_key[:10]}...",
                    "test_endpoint": "/api/languages",
                    "response_keys": list(response.keys()) if response else [],
                    "response_sample": str(response)[:500] if response else "No response"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"PrestaShop connection failed: {str(e)}",
                    "base_url": base_url,
                    "api_key_preview": f"{api_key[:10]}...",
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


@router.post("/prestashop/test-endpoint", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def test_prestashop_endpoint(
    user: user_dependency,
    db: db_dependency,
    endpoint: str = "/api/languages",
    pr: PlatformRepository = Depends(get_platform_repository)
):
    """
    Test a specific PrestaShop API endpoint
    
    This endpoint allows testing specific PrestaShop API endpoints to debug issues.
    
    Args:
        endpoint: The API endpoint to test (e.g., "/api/languages", "/api/products")
        
    Returns:
        Detailed response from the endpoint
    """
    try:
        # Get PrestaShop configuration from platforms table (ID 1)
        platform = pr.get_by_id(1)
        
        if not platform:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop platform not found in platforms table (ID 1)"
            )
        
        api_key = platform.api_key
        base_url = platform.url
        
        if not api_key:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop API key not found in platforms table"
            )
        
        if not base_url:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop base URL not found in platforms table"
            )
        
        # Test specific endpoint
        async with PrestaShopService(db, platform_id=1) as ps_service:
            try:
                response = await ps_service._make_request(endpoint)
                
                return {
                    "status": "success",
                    "message": f"Endpoint {endpoint} test successful",
                    "endpoint": endpoint,
                    "base_url": base_url,
                    "api_key_preview": f"{api_key[:10]}...",
                    "response_keys": list(response.keys()) if isinstance(response, dict) else "Not a dict",
                    "response_type": type(response).__name__,
                    "response_sample": str(response)[:1000] if response else "No response"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Endpoint {endpoint} test failed: {str(e)}",
                    "endpoint": endpoint,
                    "base_url": base_url,
                    "api_key_preview": f"{api_key[:10]}...",
                    "error_details": str(e)
                }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Endpoint test failed: {str(e)}"
        )


@router.post("/prestashop/debug-response", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def debug_prestashop_response(
    user: user_dependency,
    db: db_dependency,
    endpoint: str = "/api/languages",
    pr: PlatformRepository = Depends(get_platform_repository)
):
    """
    Debug PrestaShop API response structure
    
    This endpoint shows the raw response structure to help debug parsing issues.
    """
    try:
        # Get PrestaShop configuration from platforms table (ID 1)
        platform = pr.get_by_id(1)
        
        if not platform:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop platform not found in platforms table (ID 1)"
            )
        
        # Test specific endpoint
        async with PrestaShopService(db, platform_id=1) as ps_service:
            try:
                response = await ps_service._make_request(endpoint)
                
                return {
                    "status": "success",
                    "endpoint": endpoint,
                    "response_type": type(response).__name__,
                    "response_structure": str(response)[:2000] if response else "No response",
                    "response_keys": list(response.keys()) if isinstance(response, dict) else "Not a dict",
                    "response_length": len(response) if hasattr(response, '__len__') else "No length"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "endpoint": endpoint,
                    "error_details": str(e)
                }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Debug failed: {str(e)}"
        )


@router.post("/prestashop/test-order-details", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def test_order_details_endpoint(
    user: user_dependency,
    db: db_dependency,
    pr: PlatformRepository = Depends(get_platform_repository)
):
    """
    Test order_details endpoint specifically
    
    This endpoint tests the order_details endpoint to see the exact structure.
    """
    try:
        # Get PrestaShop configuration from platforms table (ID 1)
        platform = pr.get_by_id(1)
        
        if not platform:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop platform not found in platforms table (ID 1)"
            )
        
        # Test order_details endpoint
        async with PrestaShopService(db, platform_id=1) as ps_service:
            try:
                # Test with a small limit to see structure
                response = await ps_service._make_request('/api/order_details', {'limit': '5'})
                
                return {
                    "status": "success",
                    "endpoint": "/api/order_details",
                    "response_type": type(response).__name__,
                    "response_structure": str(response)[:2000] if response else "No response",
                    "response_keys": list(response.keys()) if isinstance(response, dict) else "Not a dict",
                    "response_length": len(response) if hasattr(response, '__len__') else "No length"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "endpoint": "/api/order_details",
                    "error_details": str(e)
                }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Test failed: {str(e)}"
        )


@router.post("/prestashop/test-endpoints", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def test_all_endpoints(
    user: user_dependency,
    db: db_dependency,
    pr: PlatformRepository = Depends(get_platform_repository)
):
    """
    Test all PrestaShop endpoints to see which ones work
    
    This endpoint tests all the endpoints we use to identify working ones.
    """
    try:
        # Get PrestaShop configuration from platforms table (ID 1)
        platform = pr.get_by_id(1)
        
        if not platform:
            raise HTTPException(
                status_code=400, 
                detail="PrestaShop platform not found in platforms table (ID 1)"
            )
        
        # Test all endpoints
        endpoints_to_test = [
            '/api/languages',
            '/api/countries', 
            '/api/manufacturers',
            '/api/categories',
            '/api/carriers',
            '/api/products',
            '/api/customers',
            '/api/orders',
            '/api/addresses',
            '/api/order_details',
            '/api/order_detail'
        ]
        
        results = {}
        
        async with PrestaShopService(db, platform_id=1) as ps_service:
            for endpoint in endpoints_to_test:
                try:
                    print(f"Testing endpoint: {endpoint}")
                    response = await ps_service._make_request(endpoint, {'limit': '5'})
                    
                    results[endpoint] = {
                        'status': 'success',
                        'response_type': type(response).__name__,
                        'response_keys': list(response.keys()) if isinstance(response, dict) else "Not a dict",
                        'response_length': len(response) if hasattr(response, '__len__') else "No length"
                    }
                    
                except Exception as e:
                    results[endpoint] = {
                        'status': 'error',
                        'error': str(e)
                    }
                
                # Small delay between requests
                import asyncio
                await asyncio.sleep(0.5)
        
        return {
            "status": "completed",
            "endpoints_tested": len(endpoints_to_test),
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Test failed: {str(e)}"
        )
