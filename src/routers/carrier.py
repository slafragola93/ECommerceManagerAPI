"""
Carrier Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.repository.tax_repository import TaxRepository
from src.services.core.tool import calculate_price_without_tax
from src.services.interfaces.carrier_service_interface import ICarrierService
from src.repository.interfaces.carrier_repository_interface import ICarrierRepository
from src.schemas.carrier_schema import CarrierSchema, CarrierResponseSchema, AllCarriersResponseSchema, CarrierPriceResponseSchema
from src.core.container import container
from src.core.exceptions import (
    BaseApplicationException,
    ValidationException,
    NotFoundException,
    BusinessRuleException
)
from src.services.routers.auth_service import authorize, get_current_user, db_dependency
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT

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
    db: db_dependency,
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
    
    **Calcolo IVA**:
    - Recupera la percentuale IVA dalla tabella Taxes per il country specificato
    - Se non presente in Taxes per il country, recupera il valore "default_tav" da app_configuration
    - Calcola il prezzo senza IVA (price_net) partendo dal prezzo con IVA (price_with_tax)
    
    Restituisce sia il prezzo con IVA che il prezzo senza IVA del corriere.
    """
    # Tratta stringhe vuote come None
    postcode_value = postcode if postcode and postcode.strip() else None
    
    price_with_tax = await carrier_service.get_carrier_price(
        id_carrier_api=id_carrier_api,
        id_country=id_country,
        weight=weight,
        postcode=postcode_value
    )
    
    # Recupera la percentuale IVA per il country

    
    tax_repo = TaxRepository(db)
    
    # Recupera tax info per il country
    # Se in Taxes è presente l'id_country, recupera percentage
    # Se in Taxes non è presente l'id_country, recupera in app_configuration il valore di "default_tav"
    tax_info = tax_repo.get_tax_info_by_country(id_country)
    
    if tax_info and tax_info.get("percentage") is not None:
        tax_percentage = tax_info["percentage"]
        id_tax = tax_info["id_tax"]
    else:
        # Se non trovata, recupera da app_configuration.default_tav
        tax_percentage = tax_repo.get_default_tax_percentage_from_app_config(22.0)
    # Calcola price_net togliendo l'IVA
    price_net = calculate_price_without_tax(price_with_tax, tax_percentage)
    
    return {
        "price_with_tax": price_with_tax,
        "price_net": price_net,
        "id_tax": id_tax
    }

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

