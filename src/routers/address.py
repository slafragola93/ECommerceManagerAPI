from typing import Optional
from ..repository.address_repository import AddressRepository
from fastapi import APIRouter, HTTPException, Path, Depends, Query
from starlette import status
from .dependencies import db_dependency, user_dependency, MAX_LIMIT, LIMIT_DEFAULT
from .. import AddressSchema, AddressResponseSchema, AllAddressResponseSchema
from src.services.wrap import check_authentication
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/addresses',
    tags=['Address'],
)


def get_repository(db: db_dependency) -> AddressRepository:
    return AddressRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllAddressResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_address(user: user_dependency,
                          ar: AddressRepository = Depends(get_repository),
                          addresses_ids: Optional[str] = None,
                          origin_ids: Optional[str] = None,
                          customers_ids: Optional[str] = None,
                          countries: Optional[str] = None,
                          state: Optional[str] = None,
                          vat: Optional[str] = None,
                          dni: Optional[str] = None,
                          pec: Optional[str] = None,
                          sdi: Optional[str] = None,
                          page: int = Query(1, gt=0),
                          limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
     Recupera una lista di indirizzi filtrata in base a vari criteri.

     Parametri:
     - `user`: Dipendenza dell'utente autenticato.
     - `db`: Dipendenza del database.
     - `addresses_ids`: ID degli indirizzi, separati da virgole.
     - `origin_ids`: ID di origine, separati da virgole.
     - `customers`: ID dei clienti, separati da virgole.
     - `countries`: ID dei paesi, separati da virgole.
     - `state`: Stato di appartenenza.
     - `vat`: Numero di partita IVA.
     - `dni`: Documento nazionale di identità.
     - `pec`: Email PEC.
     - `sdi`: Sistema di interscambio.
     - `page`: Pagina corrente per la paginazione.
     - `limit`: Numero di record per pagina.
     """
    addresses = ar.get_all(addresses_ids=addresses_ids,
                           origin_ids=origin_ids,
                           customers_ids=customers_ids,
                           countries_ids=countries,
                           state=state,
                           vat=vat,
                           dni=dni,
                           pec=pec,
                           sdi=sdi,
                           page=page,
                           limit=limit)

    if not addresses:
        raise HTTPException(status_code=404, detail="Nessun indirizzo trovato")

    total_count = ar.get_count(addresses_ids=addresses_ids,
                               origin_ids=origin_ids,
                               customers_ids=customers_ids,
                               countries_ids=countries,
                               state=state,
                               vat=vat,
                               dni=dni,
                               pec=pec,
                               sdi=sdi)

    results = []
    for address, country, customer in addresses:
        results.append(ar.formatted_output(address=address,
                                           country=country,
                                           customer=customer))

    return {"addresses": results, "total": total_count, "page": page, "limit": limit}


@router.get("/{address_id}", status_code=status.HTTP_200_OK, response_model=AddressResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_address_by_id(user: user_dependency,
                            ar: AddressRepository = Depends(get_repository),
                            address_id: int = Path(gt=0)):
    """
     Recupera un singolo indirizzo per ID.

     Parametri:
     - `user`: Dipendenza dell'utente autenticato.
     - `db`: Dipendenza del database.
     - `address_id`: ID dell'indirizzo da recuperare.
     """

    result = ar.get_complete_address_by_id(_id=address_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Indirizzo non trovato")

    address, country, customer = result

    return ar.formatted_output(address, country, customer)


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Indirizzo creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_address(user: user_dependency,
                         address: AddressSchema,
                         ar: AddressRepository = Depends(get_repository) ):
    """
    Crea un nuovo indirizzo nel sistema.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `db`: Dipendenza del database.
    - `address`: Schema dell'indirizzo da creare.
    """

    return ar.create(data=address)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Indirizzo eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_address(user: user_dependency,
                         ar: AddressRepository = Depends(get_repository),
                         address_id: int = Path(gt=0)):
    """
    Elimina un indirizzo dal sistema per l'ID specificato.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `db`: Dipendenza del database.
    - `address_id`: ID dell'indirizzo da eliminare.
    """

    address = ar.get_by_id(_id=address_id)

    if address is None:
        raise HTTPException(status_code=404, detail="Indirizzo non trovato")

    ar.delete(address=address)


@router.put("/{address_id}", status_code=status.HTTP_200_OK, response_description="Indirizzo aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_address(user: user_dependency,
                         address_schema: AddressSchema,
                         ar: AddressRepository = Depends(get_repository),
                         address_id: int = Path(gt=0)):
    """
     Aggiorna un indirizzo esistente.

     Parametri:
     - `user`: Dipendenza dell'utente autenticato.
     - `db`: Dipendenza del database.
     - `address_schema`: Schema dell'indirizzo aggiornato.
     - `address_id`: ID dell'indirizzo da aggiornare.
     """

    address = ar.get_by_id(_id=address_id)

    if address is None:
        raise HTTPException(status_code=404, detail="Indirizzo non trovato")

    ar.update(edited_address=address,
              data=address_schema)
