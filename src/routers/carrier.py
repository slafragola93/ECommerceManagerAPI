"""
Carrier Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.carrier_service_interface import ICarrierService
from src.repository.interfaces.carrier_repository_interface import ICarrierRepository
from src.schemas.carrier_schema import CarrierSchema, CarrierResponseSchema, AllCarriersResponseSchema
from src.schemas.carrier_assignment_schema import CarrierPriceResponseSchema
from src.core.container import container
from src.core.exceptions import (
    BaseApplicationException,
    ValidationException,
    NotFoundException,
    BusinessRuleException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user

router = APIRouter(
    prefix="/api/v1/carriers",
    tags=["Carrier"],
)

def get_carrier_service(db: db_dependency) -> ICarrierService:
    """Dependency injection per Carrier Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    carrier_repo = configured_container.resolve_with_session(ICarrierRepository, db)
    carrier_service = configured_container.resolve(ICarrierService)
    
    if hasattr(carrier_service, '_carrier_repository'):
        carrier_service._carrier_repository = carrier_repo
    
    return carrier_service


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCarriersResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_carriers(
    user: dict = Depends(get_current_user),
    carrier_service: ICarrierService = Depends(get_carrier_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i carrier con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    carriers = await carrier_service.get_carriers(page=page, limit=limit)
    if not carriers:
        raise NotFoundException("Carriers", None)

    total_count = await carrier_service.get_carriers_count()

    return {"carriers": carriers, "total": total_count, "page": page, "limit": limit}

@router.get("/price", status_code=status.HTTP_200_OK, response_model=CarrierPriceResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'PREVENTIVI'], permissions_required=['R'])
async def get_carrier_price(
    id_carrier_api: int = Query(..., gt=0, description="ID del carrier API"),
    id_country: int = Query(..., gt=0, description="ID del paese"),
    weight: float = Query(..., ge=0, description="Peso del pacco in kg"),
    postcode: Optional[str] = Query(None, description="Codice postale (opzionale)"),
    user: dict = Depends(get_current_user),
    carrier_service: ICarrierService = Depends(get_carrier_service)
):
    """
    Recupera il prezzo del corriere basato sui criteri specificati.
    
    Logica di ricerca:
    - Se postcode è fornito, cerca prima con postcode specifico
    - Se non trova con postcode, cerca senza postcode (solo country e weight)
    
    - **id_carrier_api**: ID del carrier API (obbligatorio)
    - **id_country**: ID del paese (obbligatorio)
    - **weight**: Peso del pacco in kg (obbligatorio)
    - **postcode**: Codice postale (opzionale)
    
    Restituisce il prezzo con IVA del corriere che corrisponde ai criteri specificati.
    """
    # Tratta stringhe vuote come None
    postcode_value = postcode if postcode and postcode.strip() else None
    
    price = await carrier_service.get_carrier_price(
        id_carrier_api=id_carrier_api,
        id_country=id_country,
        weight=weight,
        postcode=postcode_value
    )
    return {"price_with_tax": price}

@router.get("/{carrier_id}", status_code=status.HTTP_200_OK, response_model=CarrierResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_carrier_by_id(
    carrier_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    carrier_service: ICarrierService = Depends(get_carrier_service)
):
    """
    Restituisce un singolo carrier basato sull'ID specificato.

    - **carrier_id**: Identificativo del carrier da ricercare.
    """
    carrier = await carrier_service.get_carrier(carrier_id)
    return carrier

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Carrier creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_carrier(
    carrier_data: CarrierSchema,
    user: dict = Depends(get_current_user),
    carrier_service: ICarrierService = Depends(get_carrier_service)
):
    """
    Crea un nuovo carrier con i dati forniti.
    """
    return await carrier_service.create_carrier(carrier_data)
    
@router.put("/{carrier_id}", status_code=status.HTTP_200_OK, response_description="Carrier aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_carrier(
    carrier_data: CarrierSchema,
    carrier_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    carrier_service: ICarrierService = Depends(get_carrier_service)
):
    """
    Aggiorna i dati di un carrier esistente basato sull'ID specificato.

    - **carrier_id**: Identificativo del carrier da aggiornare.
    """
    return await carrier_service.update_carrier(carrier_id, carrier_data)

@router.delete("/{carrier_id}", status_code=status.HTTP_200_OK, response_description="Carrier eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_carrier(
    carrier_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    carrier_service: ICarrierService = Depends(get_carrier_service)
):
    """
    Elimina un carrier basato sull'ID specificato.

    - **carrier_id**: Identificativo del carrier da eliminare.
    """
    await carrier_service.delete_carrier(carrier_id)

