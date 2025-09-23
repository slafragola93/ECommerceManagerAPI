from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from starlette import status
from .dependencies import db_dependency, user_dependency, MAX_LIMIT, LIMIT_DEFAULT
from ..repository.carrier_assignment_repository import CarrierAssignmentRepository
from src.schemas.carrier_assignment_schema import *
from src.services.wrap import check_authentication
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/carrier_assignments',
    tags=['CarrierAssignment'],
)


def get_repository(db: db_dependency) -> CarrierAssignmentRepository:
    return CarrierAssignmentRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCarrierAssignmentsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_all_carrier_assignments(user: user_dependency,
                                    car_repo: CarrierAssignmentRepository = Depends(get_repository),
                                    carrier_assignments_ids: Optional[str] = None,
                                    carrier_apis_ids: Optional[str] = None,
                                    page: int = Query(1, gt=0),
                                    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
    Recupera una lista di assegnazioni di corrieri filtrata in base a vari criteri.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `carrier_assignments_ids`: ID delle assegnazioni, separati da virgole.
    - `carrier_apis_ids`: ID dei carrier API, separati da virgole.
    - `page`: Pagina corrente per la paginazione.
    - `limit`: Numero di record per pagina.
    """
    assignments = car_repo.get_all(carrier_assignments_ids=carrier_assignments_ids,
                                 carrier_apis_ids=carrier_apis_ids,
                                 page=page,
                                 limit=limit)

    if not assignments:
        raise HTTPException(status_code=404, detail="Nessuna assegnazione di corriere trovata")

    total_count = car_repo.get_count(carrier_assignments_ids=carrier_assignments_ids,
                                   carrier_apis_ids=carrier_apis_ids)

    results = []
    for assignment in assignments:
        results.append(car_repo.formatted_output(assignment))

    return {"carrier_assignments": results, "total": total_count, "page": page, "limit": limit}


@router.get("/{assignment_id}", status_code=status.HTTP_200_OK, response_model=CarrierAssignmentIdSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_carrier_assignment_by_id(user: user_dependency,
                                     car_repo: CarrierAssignmentRepository = Depends(get_repository),
                                     assignment_id: int = Path(gt=0)):
    """
    Recupera un'assegnazione di corriere per ID.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `assignment_id`: ID dell'assegnazione da recuperare.
    """
    assignment = car_repo.get_by_id(_id=assignment_id)

    if assignment is None:
        raise HTTPException(status_code=404, detail="Assegnazione di corriere non trovata")

    return car_repo.formatted_output(assignment)


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Assegnazione di corriere creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_carrier_assignment(user: user_dependency,
                                  assignment: CarrierAssignmentSchema,
                                  car_repo: CarrierAssignmentRepository = Depends(get_repository)):
    """
    Crea una nuova assegnazione di corriere con i dati forniti.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `assignment`: Schema dell'assegnazione da creare.
    """
    assignment_id = car_repo.create(data=assignment)
    return {"id_carrier_assignment": assignment_id, "message": "Assegnazione di corriere creata con successo"}


@router.put("/{assignment_id}", status_code=status.HTTP_200_OK, response_description="Assegnazione di corriere aggiornata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_carrier_assignment(user: user_dependency,
                                  assignment_schema: CarrierAssignmentUpdateSchema,
                                  car_repo: CarrierAssignmentRepository = Depends(get_repository),
                                  assignment_id: int = Path(gt=0)):
    """
    Aggiorna un'assegnazione di corriere esistente con aggiornamenti parziali.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `assignment_schema`: Schema dell'assegnazione con i campi da aggiornare (tutti opzionali).
    - `assignment_id`: ID dell'assegnazione da aggiornare.
    """
    assignment = car_repo.get_by_id(_id=assignment_id)

    if assignment is None:
        raise HTTPException(status_code=404, detail="Assegnazione di corriere non trovata")

    car_repo.update(edited_assignment=assignment, data=assignment_schema)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Assegnazione di corriere eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_carrier_assignment(user: user_dependency,
                                  car_repo: CarrierAssignmentRepository = Depends(get_repository),
                                  assignment_id: int = Path(gt=0)):
    """
    Elimina un'assegnazione di corriere dal sistema per l'ID specificato.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `assignment_id`: ID dell'assegnazione da eliminare.
    """
    assignment = car_repo.get_by_id(_id=assignment_id)

    if assignment is None:
        raise HTTPException(status_code=404, detail="Assegnazione di corriere non trovata")

    car_repo.delete(assignment=assignment)


# Endpoint aggiuntivi per la gestione delle assegnazioni

@router.post("/find-match", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def find_matching_assignment(user: user_dependency,
                                 car_repo: CarrierAssignmentRepository = Depends(get_repository),
                                 postal_code: Optional[str] = Query(None),
                                 country_id: Optional[int] = Query(None),
                                 origin_carrier_id: Optional[int] = Query(None),
                                 weight: Optional[float] = Query(None)):
    """
    Trova l'assegnazione di corriere che corrisponde ai criteri specificati.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `postal_code`: Codice postale per la ricerca.
    - `country_id`: ID del paese per la ricerca.
    - `origin_carrier_id`: ID del corriere di origine per la ricerca.
    - `weight`: Peso del pacco per la ricerca.
    """
    assignment = car_repo.find_matching_assignment(
        postal_code=postal_code,
        country_id=country_id,
        origin_carrier_id=origin_carrier_id,
        weight=weight
    )

    if assignment is None:
        return {"message": "Nessuna assegnazione trovata per i criteri specificati", "assignment": None}

    return {
        "message": "Assegnazione trovata",
        "assignment": car_repo.formatted_output(assignment)
    }
