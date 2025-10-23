from fastapi import APIRouter, Depends, Path, HTTPException, status
from src.schemas.brt_configuration_schema import BrtConfigurationSchema, BrtConfigurationResponseSchema, BrtConfigurationUpdateSchema
from src.schemas.fedex_configuration_schema import FedexConfigurationSchema, FedexConfigurationResponseSchema, FedexConfigurationUpdateSchema
from src.schemas.dhl_configuration_schema import DhlConfigurationSchema, DhlConfigurationResponseSchema, DhlConfigurationUpdateSchema
from src.services.interfaces.brt_configuration_service_interface import IBrtConfigurationService
from src.services.interfaces.fedex_configuration_service_interface import IFedexConfigurationService
from src.services.interfaces.dhl_configuration_service_interface import IDhlConfigurationService
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.models.carrier_api import CarrierTypeEnum
from src.core.exceptions import BusinessRuleException, InfrastructureException

router = APIRouter(
    prefix="/api/v1/carriers_configuration",
    tags=["Carriers Configuration"]
)

# Dependency injection functions (to be implemented in dependencies.py)
def get_brt_service() -> IBrtConfigurationService:
    # This will be implemented in dependencies.py
    pass

def get_fedex_service() -> IFedexConfigurationService:
    # This will be implemented in dependencies.py
    pass

def get_dhl_service() -> IDhlConfigurationService:
    # This will be implemented in dependencies.py
    pass

def get_carrier_repo() -> IApiCarrierRepository:
    # This will be implemented in dependencies.py
    pass

# === BRT ENDPOINTS ===

@router.post("/brt/{carrier_api_id}", response_model=BrtConfigurationResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_brt_configuration(
    carrier_api_id: int = Path(..., gt=0),
    config_data: BrtConfigurationSchema = ...,
    brt_service: IBrtConfigurationService = Depends(get_brt_service),
    carrier_repo: IApiCarrierRepository = Depends(get_carrier_repo)
):
    """Crea configurazione BRT per un carrier_api"""
    try:
        carrier = await carrier_repo.get_by_id(carrier_api_id)
        if not carrier:
            raise HTTPException(status_code=404, detail="Carrier API not found")
        if carrier.carrier_type != CarrierTypeEnum.BRT:
            raise HTTPException(status_code=400, detail="Carrier is not BRT type")
        
        return await brt_service.create_configuration(carrier_api_id, config_data)
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/brt/{carrier_api_id}", response_model=BrtConfigurationResponseSchema)
async def get_brt_configuration(
    carrier_api_id: int = Path(..., gt=0),
    brt_service: IBrtConfigurationService = Depends(get_brt_service)
):
    """Recupera configurazione BRT per carrier_api_id"""
    try:
        config = await brt_service.get_configuration_by_carrier(carrier_api_id)
        if not config:
            raise HTTPException(status_code=404, detail="BRT configuration not found")
        return config
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/brt/{carrier_api_id}", response_model=BrtConfigurationResponseSchema)
async def update_brt_configuration(
    carrier_api_id: int = Path(..., gt=0),
    config_data: BrtConfigurationUpdateSchema = ...,
    brt_service: IBrtConfigurationService = Depends(get_brt_service)
):
    """Aggiorna configurazione BRT"""
    try:
        return await brt_service.update_configuration(carrier_api_id, config_data)
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/brt/{carrier_api_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brt_configuration(
    carrier_api_id: int = Path(..., gt=0),
    brt_service: IBrtConfigurationService = Depends(get_brt_service)
):
    """Elimina configurazione BRT"""
    try:
        await brt_service.delete_configuration(carrier_api_id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))

# === FEDEX ENDPOINTS ===

@router.post("/fedex/{carrier_api_id}", response_model=FedexConfigurationResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_fedex_configuration(
    carrier_api_id: int = Path(..., gt=0),
    config_data: FedexConfigurationSchema = ...,
    fedex_service: IFedexConfigurationService = Depends(get_fedex_service),
    carrier_repo: IApiCarrierRepository = Depends(get_carrier_repo)
):
    """Crea configurazione Fedex per un carrier_api"""
    try:
        carrier = await carrier_repo.get_by_id(carrier_api_id)
        if not carrier:
            raise HTTPException(status_code=404, detail="Carrier API not found")
        if carrier.carrier_type != CarrierTypeEnum.FEDEX:
            raise HTTPException(status_code=400, detail="Carrier is not Fedex type")
        
        return await fedex_service.create_configuration(carrier_api_id, config_data)
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fedex/{carrier_api_id}", response_model=FedexConfigurationResponseSchema)
async def get_fedex_configuration(
    carrier_api_id: int = Path(..., gt=0),
    fedex_service: IFedexConfigurationService = Depends(get_fedex_service)
):
    """Recupera configurazione Fedex per carrier_api_id"""
    try:
        config = await fedex_service.get_configuration_by_carrier(carrier_api_id)
        if not config:
            raise HTTPException(status_code=404, detail="Fedex configuration not found")
        return config
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/fedex/{carrier_api_id}", response_model=FedexConfigurationResponseSchema)
async def update_fedex_configuration(
    carrier_api_id: int = Path(..., gt=0),
    config_data: FedexConfigurationUpdateSchema = ...,
    fedex_service: IFedexConfigurationService = Depends(get_fedex_service)
):
    """Aggiorna configurazione Fedex"""
    try:
        return await fedex_service.update_configuration(carrier_api_id, config_data)
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/fedex/{carrier_api_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fedex_configuration(
    carrier_api_id: int = Path(..., gt=0),
    fedex_service: IFedexConfigurationService = Depends(get_fedex_service)
):
    """Elimina configurazione Fedex"""
    try:
        await fedex_service.delete_configuration(carrier_api_id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))

# === DHL ENDPOINTS ===

@router.post("/dhl/{carrier_api_id}", response_model=DhlConfigurationResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_dhl_configuration(
    carrier_api_id: int = Path(..., gt=0),
    config_data: DhlConfigurationSchema = ...,
    dhl_service: IDhlConfigurationService = Depends(get_dhl_service),
    carrier_repo: IApiCarrierRepository = Depends(get_carrier_repo)
):
    """
    Crea configurazione DHL MyDHL API per un carrier_api
    
    **CAMPI OBBLIGATORI**
    
    **📋 Identificazione e Conti**
    - `shipper_account_number`: Numero conto DHL mittente (obbligatorio per fatturazione trasporto)
    - `payer_account_number`: Numero conto terzo pagatore (opzionale, se diverso dal mittente)
    - `duties_account_number`: Numero conto per dazi doganali (opzionale, per DDP/DDU)
    
    **Dati Mittente (Shipper)**
    - `company_name`: Ragione sociale mittente
    - `reference_person`: Nome e cognome referente
    - `email`: Email di contatto
    - `phone`: Telefono (formato internazionale consigliato, es. +393331234567)
    - `address`: Indirizzo completo (via, numero civico)
    - `postal_code`: CAP
    - `city`: Città
    - `country_code`: Codice ISO paese (2 lettere, es. "IT", "DE", "FR")
    - `province_code`: Provincia/stato (opzionale, es. "MI" per Milano)
    - `tax_id`: Partita IVA/EORI (opzionale, necessario per spedizioni internazionali)
    
    **Dimensioni Pacco Predefinite**
    - `default_weight`: Peso predefinito in kg (o lbs se unit_of_measure = IMPERIAL)
    - `package_height`: Altezza pacco in cm (o inch)
    - `package_width`: Larghezza pacco in cm (o inch)
    - `package_depth`: Profondità pacco in cm (o inch)
    - `unit_of_measure`: Sistema di misura ("Metric" = kg/cm, "Imperial" = lbs/inch)
    
    **Servizi e Documenti**
    - `default_product_code_domestic`: Codice servizio nazionale (es. "N" = DHL Express Domestic)
    - `default_product_code_international`: Codice servizio internazionale (es. "P" = DHL Worldwide Express)
    - `label_format`: Formato etichetta ("PDF" per stampanti laser, "ZPL" per stampanti termiche)
    - `goods_description`: Descrizione merce predefinita (es. "General Merchandise", "Electronics")
    
    **Dogana (per spedizioni internazionali)**
    - `default_is_customs_declarable`: Se true, genera dichiarazione doganale per spedizioni internazionali
    - `default_incoterm`: Termini di resa (es. "DAP" = consegna senza dazi, "DDP" = consegna con dazi pagati)
    
    **Ritiro (Pickup)**
    - `pickup_is_requested`: Se true, DHL ritira il pacco presso il mittente
    - `pickup_close_time`: Orario chiusura per ritiro (formato "HH:mm", es. "18:00")
    - `pickup_location`: Luogo ritiro specifico (es. "Reception", "Warehouse")
    
    **Contrassegno (COD)**
    - `cod_enabled`: Abilita contrassegno (Cash On Delivery)
    - `cod_currency`: Valuta contrassegno (es. "EUR", "USD")
    
    **Altri Campi**
    - `description`: Descrizione configurazione (uso interno)
    
     **NOTA**: Tutti i campi opzionali possono essere lasciati vuoti/null se non necessari.
    """
    try:
        carrier = await carrier_repo.get_by_id(carrier_api_id)
        if not carrier:
            raise HTTPException(status_code=404, detail="API Corriere non trovato")
        if carrier.carrier_type != CarrierTypeEnum.DHL:
            raise HTTPException(status_code=400, detail="Corriere non è DHL")
        
        return await dhl_service.create_configuration(carrier_api_id, config_data)
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dhl/{carrier_api_id}", response_model=DhlConfigurationResponseSchema)
async def get_dhl_configuration(
    carrier_api_id: int = Path(..., gt=0),
    dhl_service: IDhlConfigurationService = Depends(get_dhl_service)
):
    """
    Recupera la configurazione DHL MyDHL API associata a un carrier_api
    
    Restituisce tutti i parametri di configurazione necessari per creare spedizioni DHL,
    inclusi dati mittente, dimensioni predefinite, servizi, e impostazioni dogana/pickup.
    """
    try:
        config = await dhl_service.get_configuration_by_carrier(carrier_api_id)
        if not config:
            raise HTTPException(status_code=404, detail="DHL configuration not found")
        return config
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/dhl/{carrier_api_id}", response_model=DhlConfigurationResponseSchema)
async def update_dhl_configuration(
    carrier_api_id: int = Path(..., gt=0),
    config_data: DhlConfigurationUpdateSchema = ...,
    dhl_service: IDhlConfigurationService = Depends(get_dhl_service)
):
    """
    Aggiorna la configurazione DHL MyDHL API esistente
    
    Permette di modificare parzialmente i parametri di configurazione.
    Tutti i campi sono opzionali: solo i campi forniti verranno aggiornati.
    
    **Casi d'uso comuni:**
    - Cambio numero conto DHL
    - Modifica dimensioni pacco predefinite
    - Aggiornamento indirizzo mittente
    - Cambio servizi domestic/international
    - Abilitazione/disabilitazione pickup
    """
    try:
        return await dhl_service.update_configuration(carrier_api_id, config_data)
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/dhl/{carrier_api_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dhl_configuration(
    carrier_api_id: int = Path(..., gt=0),
    dhl_service: IDhlConfigurationService = Depends(get_dhl_service)
):
    """
    Elimina la configurazione DHL MyDHL API
    
    ⚠️ **ATTENZIONE**: L'eliminazione è permanente e impedirà la creazione
    di nuove spedizioni DHL con questo carrier_api finché non viene
    ricreata una nuova configurazione.
    
    Le spedizioni già create rimarranno salvate e tracciabili.
    """
    try:
        await dhl_service.delete_configuration(carrier_api_id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InfrastructureException as e:
        raise HTTPException(status_code=500, detail=str(e))
