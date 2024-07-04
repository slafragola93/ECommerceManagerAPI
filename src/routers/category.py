from fastapi import APIRouter, Path, HTTPException, Depends, Query
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import CategorySchema, CategoryResponseSchema, AllCategoryResponseSchema
from src.services.wrap import check_authentication
from ..repository.category_repository import CategoryRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/categories',
    tags=['Category'],
)

def get_repository(db: db_dependency) -> CategoryRepository:
    return CategoryRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCategoryResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_categories(user: user_dependency,
                             cr: CategoryRepository = Depends(get_repository),
                             page: int = Query(1, gt=0),
                             limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
    Ottiene l'elenco di tutte le categorie disponibili.

    Verifica prima l'autenticazione dell'utente. Se l'utente non è autenticato,
    solleva un'eccezione HTTP con stato 401. Altrimenti, restituisce l'elenco completo
    delle categorie presenti nel database.

    Parameters:
    - user: Dipendenza dell'utente, per la verifica dell'autenticazione.
    - db: Dipendenza del database, per eseguire la query sulle categorie.

    Returns:
    - list: Un elenco di tutte le categorie presenti nel database.
    """
    categories = cr.get_all(page=page, limit=limit)

    if categories is None:
        raise HTTPException(status_code=404, detail="Nessuna categoria trovata")

    total_count = cr.get_count()

    return {"categories": categories, "total": total_count, "page": page, "limit": limit}


@router.get("/{category_id}", status_code=status.HTTP_200_OK, response_model=CategoryResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_category_by_id(user: user_dependency,
                             cr: CategoryRepository = Depends(get_repository),
                             category_id: int = Path(gt=0)):
    """
    Ottiene i dettagli di una singola categoria basata sull'ID fornito.

    Verifica prima l'autenticazione dell'utente. Se l'utente non è autenticato,
    solleva un'eccezione HTTP con stato 401. Se la categoria richiesta non esiste,
    solleva un'eccezione HTTP con stato 404. Altrimenti, restituisce i dettagli della
    categoria richiesta.

    Parameters:
    - user: Dipendenza dell'utente, per la verifica dell'autenticazione.
    - db: Dipendenza del database, per eseguire la query sulle categorie.
    - category_id: L'ID della categoria da cercare.

    Returns:
    - Category: I dettagli della categoria richiesta.
    """

    category = cr.get_by_id(_id=category_id)

    if category is None:
        raise HTTPException(status_code=404, detail="Categoria non trovata")

    return category


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Categoria creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_category(user: user_dependency,
                          cs: CategorySchema,
                          cr: CategoryRepository = Depends(get_repository)):
    """
    Crea una nuova categoria nel database.

    Verifica prima l'autenticazione dell'utente. Se l'utente non è autenticato,
    solleva un'eccezione HTTP con stato 401. Dopo la verifica, procede con la creazione
    della nuova categoria basandosi sui dati forniti.

    Parameters:
    - user: Dipendenza dell'utente, per la verifica dell'autenticazione.
    - db: Dipendenza del database, per l'inserimento dei dati della nuova categoria.
    - cs: I dati della nuova categoria da creare.
    """

    cr.create(data=cs)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Categoria eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_category(user: user_dependency,
                          cr: CategoryRepository = Depends(get_repository),
                          category_id: int = Path(gt=0)):
    """
    Elimina una categoria dal database basandosi sull'ID fornito.

    Verifica prima l'autenticazione dell'utente. Se l'utente non è autenticato,
    solleva un'eccezione HTTP con stato 401. Se la categoria non esiste, solleva
    un'eccezione HTTP con stato 404. Dopo la verifica, procede con l'eliminazione
    della categoria.

    Parameters:
    - user: Dipendenza dell'utente, per la verifica dell'autenticazione.
    - db: Dipendenza del database, per l'eliminazione dei dati della categoria.
    - category_id: L'ID della categoria da eliminare.
    """

    category = cr.get_by_id(_id=category_id)

    if category is None:
        raise HTTPException(status_code=404, detail="Categoria non trovata.")

    cr.delete(category=category)


@router.put("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_category(user: user_dependency,
                          cs: CategorySchema,
                          cr: CategoryRepository = Depends(get_repository),
                          category_id: int = Path(gt=0)):
    """
    Aggiorna i dettagli di una categoria esistente nel database.

    Verifica prima l'autenticazione dell'utente. Se l'utente non è autenticato,
    solleva un'eccezione HTTP con stato 401. Se la categoria non esiste, solleva
    un'eccezione HTTP con stato 404. Dopo la verifica, procede con l'aggiornamento
    dei dati della categoria basandosi sui dati forniti.

    Parameters:
    - user: Dipendenza dell'utente, per la verifica dell'autenticazione.
    - db: Dipendenza del database, per l'aggiornamento dei dati della categoria.
    - cs: I dati aggiornati della categoria.
    - category_id: L'ID della categoria da aggiornare.
    """

    category = cr.get_by_id(_id=category_id)

    if category is None:
        raise HTTPException(status_code=404, detail="Categoria non trovato.")

    cr.update(edited_category=category, data=cs)
