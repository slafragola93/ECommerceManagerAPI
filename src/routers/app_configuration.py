from fastapi import APIRouter, Path, HTTPException, Query, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from src.services.wrap import check_authentication
from ..repository.app_configuration_repository import AppConfigurationRepository
from ..schemas.app_configuration_schema import (
    AllAppConfigurationsResponseSchema, 
    AppConfigurationResponseSchema,
    AppConfigurationSchema,
    AppConfigurationUpdateSchema,
    AllAppConfigurationsByCategoryResponseSchema,
    AppConfigurationByCategoryResponseSchema,
    CompanyInfoSchema,
    ElectronicInvoicingSchema,
    ExemptRatesSchema,
    FatturapaSchema,
    EmailSettingsSchema,
    ApiKeysSchema
)
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/app-configs',
    tags=['App Configuration'],
)


def get_repository(db: db_dependency) -> AppConfigurationRepository:
    return AppConfigurationRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllAppConfigurationsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_app_configurations(user: user_dependency,
                                   acr: AppConfigurationRepository = Depends(get_repository),
                                   page: int = Query(1, gt=0),
                                   limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """Recupera tutte le configurazioni dell'app con paginazione"""
    configurations = acr.get_all(page=page, limit=limit)

    if not configurations:
        raise HTTPException(status_code=404, detail="Configurazioni non trovate")

    total_count = acr.get_count()

    return {
        "configurations": configurations, 
        "total": total_count, 
        "page": page, 
        "limit": limit
    }


@router.get("/by-category", status_code=status.HTTP_200_OK, response_model=AllAppConfigurationsByCategoryResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_app_configurations_by_category(user: user_dependency,
                                           acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le configurazioni raggruppate per categoria"""
    configurations_by_category = acr.get_configurations_by_category()
    
    categories = []
    total_configurations = 0
    
    for category, configs in configurations_by_category.items():
        categories.append(AppConfigurationByCategoryResponseSchema(
            category=category,
            configurations=configs,
            total=len(configs)
        ))
        total_configurations += len(configs)
    
    return {
        "categories": categories,
        "total_categories": len(categories),
        "total_configurations": total_configurations
    }


@router.get("/category/{category}", status_code=status.HTTP_200_OK, response_model=list[AppConfigurationResponseSchema])
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_app_configurations_by_category_name(user: user_dependency,
                                                acr: AppConfigurationRepository = Depends(get_repository),
                                                category: str = Path(..., description="Nome della categoria")):
    """Recupera tutte le configurazioni di una categoria specifica"""
    configurations = acr.get_by_category(category)

    if not configurations:
        raise HTTPException(status_code=404, detail=f"Configurazioni per la categoria '{category}' non trovate")

    return configurations


# Endpoint specifici per le categorie di configurazione
@router.get("/company-info", status_code=status.HTTP_200_OK, response_model=CompanyInfoSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_company_info(user: user_dependency,
                         acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le configurazioni di anagrafica azienda"""
    configurations = acr.get_by_category("company_info")
    
    # Converti le configurazioni in un dizionario
    company_info = {}
    for config in configurations:
        company_info[config.name] = config.value
    
    # Crea lo schema con tutti i campi, usando None per quelli mancanti
    return CompanyInfoSchema(
        company_logo=company_info.get("company_logo"),
        company_name=company_info.get("company_name"),
        vat_number=company_info.get("vat_number"),
        fiscal_code=company_info.get("fiscal_code"),
        share_capital=company_info.get("share_capital"),
        rea_number=company_info.get("rea_number"),
        address=company_info.get("address"),
        postal_code=company_info.get("postal_code"),
        city=company_info.get("city"),
        province=company_info.get("province"),
        country=company_info.get("country"),
        phone=company_info.get("phone"),
        fax=company_info.get("fax"),
        email=company_info.get("email"),
        website=company_info.get("website"),
        bank_name=company_info.get("bank_name"),
        iban=company_info.get("iban"),
        bic_swift=company_info.get("bic_swift"),
        account_holder=company_info.get("account_holder"),
        account_number=company_info.get("account_number"),
        abi=company_info.get("abi"),
        cab=company_info.get("cab")
    )


@router.get("/electronic-invoicing", status_code=status.HTTP_200_OK, response_model=ElectronicInvoicingSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_electronic_invoicing(user: user_dependency,
                                 acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le configurazioni di fatturazione elettronica"""
    configurations = acr.get_by_category("electronic_invoicing")
    
    # Converti le configurazioni in un dizionario
    electronic_invoicing = {}
    for config in configurations:
        electronic_invoicing[config.name] = config.value
    
    return ElectronicInvoicingSchema(
        tax_regime=electronic_invoicing.get("tax_regime"),
        transmitter_fiscal_code=electronic_invoicing.get("transmitter_fiscal_code"),
        send_progressive=electronic_invoicing.get("send_progressive"),
        register_number=electronic_invoicing.get("register_number"),
        rea_registration=electronic_invoicing.get("rea_registration"),
        cash_type=electronic_invoicing.get("cash_type"),
        withholding_type=electronic_invoicing.get("withholding_type"),
        payment_reason=electronic_invoicing.get("payment_reason"),
        vat_exigibility=electronic_invoicing.get("vat_exigibility"),
        intermediary_name=electronic_invoicing.get("intermediary_name"),
        intermediary_vat=electronic_invoicing.get("intermediary_vat"),
        intermediary_fiscal_code=electronic_invoicing.get("intermediary_fiscal_code")
    )


@router.get("/exempt-rates", status_code=status.HTTP_200_OK, response_model=ExemptRatesSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_exempt_rates(user: user_dependency,
                         acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le configurazioni di aliquote esenti"""
    configurations = acr.get_by_category("exempt_rates")
    
    # Converti le configurazioni in un dizionario
    exempt_rates = {}
    for config in configurations:
        exempt_rates[config.name] = config.value
    
    return ExemptRatesSchema(
        exempt_rate_standard=exempt_rates.get("exempt_rate_standard"),
        exempt_rate_no=exempt_rates.get("exempt_rate_no"),
        exempt_rate_no_x=exempt_rates.get("exempt_rate_no_x"),
        exempt_rate_vat_refund=exempt_rates.get("exempt_rate_vat_refund"),
        exempt_rate_spring=exempt_rates.get("exempt_rate_spring"),
        exempt_rate_san_marino=exempt_rates.get("exempt_rate_san_marino"),
        exempt_rate_commissions=exempt_rates.get("exempt_rate_commissions")
    )


@router.get("/fatturapa", status_code=status.HTTP_200_OK, response_model=FatturapaSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_fatturapa(user: user_dependency,
                       acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le configurazioni Fatturapa"""
    configurations = acr.get_by_category("fatturapa")
    
    # Converti le configurazioni in un dizionario
    fatturapa = {}
    for config in configurations:
        fatturapa[config.name] = config.value
    
    return FatturapaSchema(
        api_key=fatturapa.get("api_key")
    )


@router.get("/email-settings", status_code=status.HTTP_200_OK, response_model=EmailSettingsSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_email_settings(user: user_dependency,
                           acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le configurazioni email"""
    configurations = acr.get_by_category("email_settings")
    
    # Converti le configurazioni in un dizionario
    email_settings = {}
    for config in configurations:
        email_settings[config.name] = config.value
    
    return EmailSettingsSchema(
        sender_name=email_settings.get("sender_name"),
        sender_email=email_settings.get("sender_email"),
        password=email_settings.get("password"),
        ccn=email_settings.get("ccn"),
        smtp_server=email_settings.get("smtp_server"),
        smtp_port=email_settings.get("smtp_port"),
        security=email_settings.get("security")
    )


@router.get("/api-keys", status_code=status.HTTP_200_OK, response_model=ApiKeysSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_api_keys(user: user_dependency,
                      acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le chiavi API dell'app"""
    configurations = acr.get_by_category("api_keys")
    
    # Converti le configurazioni in un dizionario
    api_keys = {}
    for config in configurations:
        api_keys[config.name] = config.value
    
    return ApiKeysSchema(
        app_api_key=api_keys.get("app_api_key")
    )


@router.get("/{configuration_id}", status_code=status.HTTP_200_OK, response_model=AppConfigurationResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_app_configuration_by_id(user: user_dependency,
                                    acr: AppConfigurationRepository = Depends(get_repository),
                                    configuration_id: int = Path(gt=0)):
    """Recupera una configurazione specifica per ID"""
    configuration = acr.get_by_id(_id=configuration_id)

    if configuration is None:
        raise HTTPException(status_code=404, detail="Configurazione non trovata")

    return configuration


@router.get("/value/{category}/{name}", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_app_configuration_value(user: user_dependency,
                                    acr: AppConfigurationRepository = Depends(get_repository),
                                    category: str = Path(..., description="Categoria della configurazione"),
                                    name: str = Path(..., description="Nome della configurazione")):
    """Recupera il valore di una configurazione specifica"""
    configuration = acr.get_by_name_and_category(name, category)

    if configuration is None:
        raise HTTPException(status_code=404, detail="Configurazione non trovata")

    return {"value": configuration.value}


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Configurazione creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_app_configuration(user: user_dependency,
                                 acs: AppConfigurationSchema,
                                 acr: AppConfigurationRepository = Depends(get_repository)):
    """Crea una nuova configurazione"""
    # Verifica se esiste già una configurazione con lo stesso nome e categoria
    existing = acr.get_by_name_and_category(acs.name, acs.category)
    if existing:
        raise HTTPException(status_code=400, detail="Configurazione già esistente per questa categoria")
    
    acr.create(data=acs)


@router.post("/bulk", status_code=status.HTTP_201_CREATED, response_description="Configurazioni create correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_bulk_app_configurations(user: user_dependency,
                                       configurations: list[AppConfigurationSchema],
                                       acr: AppConfigurationRepository = Depends(get_repository)):
    """Crea multiple configurazioni in batch"""
    if not configurations:
        raise HTTPException(status_code=422, detail="Lista configurazioni non può essere vuota")
    
    acr.create_bulk(configurations)


@router.put("/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_app_configuration(user: user_dependency,
                                 acs: AppConfigurationUpdateSchema,
                                 acr: AppConfigurationRepository = Depends(get_repository),
                                 configuration_id: int = Path(gt=0)):
    """Aggiorna una configurazione esistente"""
    configuration = acr.get_by_id(_id=configuration_id)

    if configuration is None:
        raise HTTPException(status_code=404, detail="Configurazione non trovata")

    acr.update(edited_configuration=configuration, data=acs)


@router.put("/value/{category}/{name}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_app_configuration_value(user: user_dependency,
                                       acr: AppConfigurationRepository = Depends(get_repository),
                                       category: str = Path(..., description="Categoria della configurazione"),
                                       name: str = Path(..., description="Nome della configurazione"),
                                       value: str = Query(..., description="Nuovo valore")):
    """Aggiorna il valore di una configurazione specifica"""
    configuration = acr.get_by_name_and_category(name, category)

    if configuration is None:
        raise HTTPException(status_code=404, detail="Configurazione non trovata")

    acr.update_by_name_and_category(name, category, value)


@router.delete("/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Configurazione eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_app_configuration(user: user_dependency,
                                 acr: AppConfigurationRepository = Depends(get_repository),
                                 configuration_id: int = Path(gt=0)):
    """Elimina una configurazione"""
    configuration = acr.get_by_id(_id=configuration_id)

    if configuration is None:
        raise HTTPException(status_code=404, detail="Configurazione non trovata")

    acr.delete(configuration)


@router.delete("/{category}/{name}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Configurazione eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_app_configuration_by_name(user: user_dependency,
                                         acr: AppConfigurationRepository = Depends(get_repository),
                                         category: str = Path(..., description="Categoria della configurazione"),
                                         name: str = Path(..., description="Nome della configurazione")):
    """Elimina una configurazione per nome e categoria"""
    success = acr.delete_by_name_and_category(name, category)
    
    if not success:
        raise HTTPException(status_code=404, detail="Configurazione non trovata")


# Endpoint specifici per le categorie di configurazione
@router.get("/company-info", status_code=status.HTTP_200_OK, response_model=CompanyInfoSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_company_info(user: user_dependency,
                         acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le configurazioni di anagrafica azienda"""
    configurations = acr.get_by_category("company_info")
    
    # Converti le configurazioni in un dizionario
    company_info = {}
    for config in configurations:
        company_info[config.name] = config.value
    
    # Crea lo schema con tutti i campi, usando None per quelli mancanti
    return CompanyInfoSchema(
        company_logo=company_info.get("company_logo"),
        company_name=company_info.get("company_name"),
        vat_number=company_info.get("vat_number"),
        fiscal_code=company_info.get("fiscal_code"),
        share_capital=company_info.get("share_capital"),
        rea_number=company_info.get("rea_number"),
        address=company_info.get("address"),
        postal_code=company_info.get("postal_code"),
        city=company_info.get("city"),
        province=company_info.get("province"),
        country=company_info.get("country"),
        phone=company_info.get("phone"),
        fax=company_info.get("fax"),
        email=company_info.get("email"),
        website=company_info.get("website"),
        bank_name=company_info.get("bank_name"),
        iban=company_info.get("iban"),
        bic_swift=company_info.get("bic_swift"),
        account_holder=company_info.get("account_holder"),
        account_number=company_info.get("account_number"),
        abi=company_info.get("abi"),
        cab=company_info.get("cab")
    )


@router.get("/electronic-invoicing", status_code=status.HTTP_200_OK, response_model=ElectronicInvoicingSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_electronic_invoicing(user: user_dependency,
                                 acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le configurazioni di fatturazione elettronica"""
    configurations = acr.get_by_category("electronic_invoicing")
    
    # Converti le configurazioni in un dizionario
    electronic_invoicing = {}
    for config in configurations:
        electronic_invoicing[config.name] = config.value
    
    return ElectronicInvoicingSchema(
        tax_regime=electronic_invoicing.get("tax_regime"),
        transmitter_fiscal_code=electronic_invoicing.get("transmitter_fiscal_code"),
        send_progressive=electronic_invoicing.get("send_progressive"),
        register_number=electronic_invoicing.get("register_number"),
        rea_registration=electronic_invoicing.get("rea_registration"),
        cash_type=electronic_invoicing.get("cash_type"),
        withholding_type=electronic_invoicing.get("withholding_type"),
        payment_reason=electronic_invoicing.get("payment_reason"),
        vat_exigibility=electronic_invoicing.get("vat_exigibility"),
        intermediary_name=electronic_invoicing.get("intermediary_name"),
        intermediary_vat=electronic_invoicing.get("intermediary_vat"),
        intermediary_fiscal_code=electronic_invoicing.get("intermediary_fiscal_code")
    )


@router.get("/exempt-rates", status_code=status.HTTP_200_OK, response_model=ExemptRatesSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_exempt_rates(user: user_dependency,
                         acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le configurazioni di aliquote esenti"""
    configurations = acr.get_by_category("exempt_rates")
    
    # Converti le configurazioni in un dizionario
    exempt_rates = {}
    for config in configurations:
        exempt_rates[config.name] = config.value
    
    return ExemptRatesSchema(
        exempt_rate_standard=exempt_rates.get("exempt_rate_standard"),
        exempt_rate_no=exempt_rates.get("exempt_rate_no"),
        exempt_rate_no_x=exempt_rates.get("exempt_rate_no_x"),
        exempt_rate_vat_refund=exempt_rates.get("exempt_rate_vat_refund"),
        exempt_rate_spring=exempt_rates.get("exempt_rate_spring"),
        exempt_rate_san_marino=exempt_rates.get("exempt_rate_san_marino"),
        exempt_rate_commissions=exempt_rates.get("exempt_rate_commissions")
    )


@router.get("/fatturapa", status_code=status.HTTP_200_OK, response_model=FatturapaSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_fatturapa(user: user_dependency,
                       acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le configurazioni Fatturapa"""
    configurations = acr.get_by_category("fatturapa")
    
    # Converti le configurazioni in un dizionario
    fatturapa = {}
    for config in configurations:
        fatturapa[config.name] = config.value
    
    return FatturapaSchema(
        api_key=fatturapa.get("api_key")
    )


@router.get("/email-settings", status_code=status.HTTP_200_OK, response_model=EmailSettingsSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_email_settings(user: user_dependency,
                           acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le configurazioni email"""
    configurations = acr.get_by_category("email_settings")
    
    # Converti le configurazioni in un dizionario
    email_settings = {}
    for config in configurations:
        email_settings[config.name] = config.value
    
    return EmailSettingsSchema(
        sender_name=email_settings.get("sender_name"),
        sender_email=email_settings.get("sender_email"),
        password=email_settings.get("password"),
        ccn=email_settings.get("ccn"),
        smtp_server=email_settings.get("smtp_server"),
        smtp_port=email_settings.get("smtp_port"),
        security=email_settings.get("security")
    )


@router.get("/api-keys", status_code=status.HTTP_200_OK, response_model=ApiKeysSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_api_keys(user: user_dependency,
                      acr: AppConfigurationRepository = Depends(get_repository)):
    """Recupera tutte le chiavi API dell'app"""
    configurations = acr.get_by_category("api_keys")
    
    # Converti le configurazioni in un dizionario
    api_keys = {}
    for config in configurations:
        api_keys[config.name] = config.value
    
    return ApiKeysSchema(
        app_api_key=api_keys.get("app_api_key")
    )
