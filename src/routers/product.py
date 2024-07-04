from typing import Optional
from fastapi import APIRouter, Path, HTTPException, Query, Depends
from sqlalchemy.exc import IntegrityError
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from src.models.product import Product
from .. import ProductSchema, ProductResponseSchema, AllProductsResponseSchema
from src.services.tool import edit_entity
from src.services.wrap import check_authentication
from ..repository.product_repository import ProductRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/products',
    tags=['Product'],
)


def get_repository(db: db_dependency) -> ProductRepository:
    return ProductRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllProductsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_products(user: user_dependency,
                           pr: ProductRepository = Depends(get_repository),
                           category_ids: Optional[str] = None,
                           brand_ids: Optional[str] = None,
                           product_name: Optional[str] = None,
                           product_ids: Optional[str] = None,
                           sku: Optional[str] = None,
                           page: int = Query(1, gt=0),
                           limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
     Ottiene un elenco paginato di prodotti, con opzioni di filtraggio avanzate.

     Questo endpoint permette agli utenti di recuperare un elenco di prodotti, filtrati in base a vari criteri come categoria, marca, ID del prodotto, nome (supportando la ricerca parziale) e SKU. È possibile anche paginare i risultati per gestire efficacemente l'esplorazione di grandi set di dati.

     Parametri:
         user: Dipendenza dell'utente autenticato, necessaria per accedere a questo endpoint.
         categories (str, opzionale): Elenco degli ID di categorie, separati da virgole, per filtrare i prodotti appartenenti a specifiche categorie.
         brands (str, opzionale): Elenco degli ID di marchi, separati da virgole, per filtrare i prodotti associati a specifici marchi.
         name (str, opzionale): Testo per la ricerca parziale nei nomi dei prodotti, supporta la ricerca case-insensitive.
         products (str, opzionale): Elenco degli ID di prodotti, separati da virgole, per filtrare specifici prodotti.
         sku (str, opzionale): Codice SKU per identificare univocamente un prodotto e filtrare la ricerca basandosi su di esso.
         page (int): Numero della pagina di risultati da restituire, utile per la navigazione paginata dei dati. Default a 1.
         limit (int): Numero massimo di risultati da includere in una singola pagina. Default a 10.

     Restituisce:
         Un dizionario che contiene un elenco paginato di prodotti, ciascuno con dettagli inclusi il nome del brand e della categoria, insieme al numero totale di prodotti disponibili che soddisfano i criteri di ricerca, il numero della pagina attuale, e il limite di prodotti per pagina.
         In caso di mancanza di risultati, viene restituito un errore 404.
         Se i parametri di ricerca non sono validi (ad esempio, formati di ID non corretti), viene restituito un errore 400.

     Eccezioni:
         HTTPException: Restituisce uno status code 401 se l'utente non è autenticato.
         HTTPException: Restituisce uno status code 400 se i parametri di ricerca sono non validi.
         HTTPException: Restituisce uno status code 404 se nessun prodotto corrisponde ai criteri di ricerca forniti.
     """
    products = pr.get_all(
        categories_ids=category_ids,
        brands_ids=brand_ids,
        product_name=product_name,
        products_ids=product_ids,
        sku=sku,
        page=page,
        limit=limit
    )

    if not products:
        raise HTTPException(status_code=404, detail="Nessun prodotto trovato")

    total_count = pr.get_count(
        categories_ids=category_ids,
        brands_ids=brand_ids,
        product_name=product_name,
        products_ids=product_ids,
        sku=sku
    )

    results = []
    for product, brand_name, brand_id_origin, category_name, category_id_origin in products:
        results.append(pr.formatted_output(product=product,
                                           brand_name=brand_name,
                                           brand_id_origin=brand_id_origin,
                                           category_name=category_name,
                                           category_id_origin=category_id_origin
                                           ))

    return {"products": results, "total": total_count, "page": page, "limit": limit}


@router.get("/{product_id}", status_code=status.HTTP_200_OK, response_model=ProductResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_product_by_id(user: user_dependency,
                            pr: ProductRepository = Depends(get_repository),
                            product_id: int = Path(gt=0)):
    """
    Recupera e restituisce i dettagli di un singolo prodotto identificato dall'ID fornito.

    Questo endpoint richiede l'autenticazione e restituisce i dettagli completi di un prodotto,
    inclusi il nome del brand e della categoria associata al prodotto.

    Parametri:
    - user: Dipendenza dell'utente autenticato, necessaria per accedere a questo endpoint.
    - db: Sessione di connessione al database per eseguire la query.
    - product_id: L'identificativo numerico unico del prodotto da ricercare.

    Restituisce:
    - Un oggetto JSON che contiene i dettagli del prodotto richiesto se trovato.
    - Un errore 404 se il prodotto specificato non esiste.
    """

    product = pr.get_by_id_complete(_id=product_id)

    if product is None:
        raise HTTPException(status_code=404, detail="Prodotto non trovato.")

    product, brand_name, brand_id_origin, category_name, category_id_origin = product

    return formatted_output(product=product,
                            brand_name=brand_name,
                            brand_id_origin=brand_id_origin,
                            category_name=category_name,
                            category_id_origin=category_id_origin)


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Prodotto creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_product(user: user_dependency,
                         ps: ProductSchema,
                         pr: ProductRepository = Depends(get_repository)):
    """
    Crea un nuovo prodotto con i dati forniti.

    Parametri:
    - user: Dipendenza dell'utente autenticato, usata per verificare l'autorizzazione.
    - db: Sessione del database per inserire il nuovo prodotto.
    - ps: Schema del prodotto contenente i dati per la creazione.
    """
    pr.create(data=ps)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Prodotto eliminato")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_product(user: user_dependency,
                         pr: ProductRepository = Depends(get_repository),
                         product_id: int = Path(gt=0)):
    """
    Elimina un prodotto basato sull'ID specificato.

    Parametri:
    - user: Dipendenza dell'utente autenticato, usata per verificare l'autorizzazione.
    - db: Sessione del database per eliminare il prodotto.
    - product_id: Identificativo del prodotto da eliminare.
    """

    product = pr.get_by_id(_id=product_id)

    if product is None:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")

    pr.delete(product=product)


@router.put("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Prodotto modificato")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_product(user: user_dependency,
                         ps: ProductSchema,
                         pr: ProductRepository = Depends(get_repository),
                         product_id: int = Path(gt=0)):
    """
    Aggiorna i dati di un prodotto esistente basato sull'ID specificato.

    Questo endpoint consente di modificare le proprietà di un prodotto, inclusi marca, categoria, e altri dettagli.
    Richiede l'autenticazione dell'utente e verifica che il prodotto esista prima di procedere con l'aggiornamento.

    Parametri:
    - user: Dipendenza dell'utente autenticato, necessaria per accedere a questo endpoint.
    - db: Sessione del database per aggiornare i dati del prodotto.
    - ps: Schema del prodotto contenente i dati aggiornati.
    - product_id: Identificativo del prodotto da aggiornare.

    Restituisce:
    - Status code 204 in caso di successo.
    - Errore 404 se il prodotto specificato non esiste.
    - Errore 400 in caso di violazione di vincoli di integrità dei dati.
    """

    product = pr.get_by_id(_id=product_id)

    if product is None:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")

    pr.update(edited_product=product, data=ps)


def formatted_output(product: Product,
                     category_id_origin: int,
                     category_name: str,
                     brand_name: str,
                     brand_id_origin: int
                     ):
    return {
        "id_product": product.id_product,
        "id_origin": product.id_origin,
        "name": product.name,
        "sku": product.sku,
        "type": product.type,
        "category": {
            "id_category": product.id_category,  # Assumi che tu abbia l'ID disponibile qui
            "id_origin": category_id_origin,
            "name": category_name
        },
        "brand": {
            "id_brand": product.id_brand,  # Assumi che tu abbia l'ID disponibile qui
            "id_origin": brand_id_origin,
            "name": brand_name
        },
    }
