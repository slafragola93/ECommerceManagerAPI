from fastapi import APIRouter, Path, HTTPException, Query, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import TaxSchema, AllTaxesResponseSchema, TaxResponseSchema
from src.services.wrap import check_authentication
from ..repository.tax_repository import TaxRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/taxes',
    tags=['Tax'],
)


def get_repository(db: db_dependency) -> TaxRepository:
    return TaxRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllTaxesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'FATTURAZIONE'], permissions_required=['R'])
async def get_all_taxs(
        user: user_dependency,
        tr: TaxRepository = Depends(get_repository),
        page: int = Query(1, gt=0),
        limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    taxes = tr.get_all(page=page, limit=limit)

    if not taxes:
        raise HTTPException(status_code=404, detail="Nessuna tasse trovato")

    total_count = tr.get_count()

    return {"taxes": taxes, "total": total_count, "page": page, "limit": limit}


@router.get("/{tax_id}", status_code=status.HTTP_200_OK, response_model=TaxResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'FATTURAZIONE'], permissions_required=['R'])
async def get_tax_by_id(user: user_dependency,
                        tr: TaxRepository = Depends(get_repository),
                        tax_id: int = Path(gt=0)):

    tax = tr.get_by_id(_id=tax_id)

    if tax is None:
        raise HTTPException(status_code=404, detail="Tassa non trovato.")

    return tax


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Tassa creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'FATTURAZIONE'], permissions_required=['C'])
async def create_tax(user: user_dependency,
                     tax: TaxSchema,
                     tr: TaxRepository = Depends(get_repository)):

    tr.create(data=tax)


@router.delete("/{tax_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Tassa eliminato.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'FATTURAZIONE'], permissions_required=['D'])
async def delete_tax(user: user_dependency,
                     tr: TaxRepository = Depends(get_repository),
                     tax_id: int = Path(gt=0)):

    tax = tr.get_by_id(_id=tax_id)

    if tax is None:
        raise HTTPException(status_code=404, detail="Tassa non trovato.")

    tr.delete(tax=tax)


@router.put("/{tax_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Tassa modificata")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'FATTURAZIONE'], permissions_required=['U'])
async def update_tax(user: user_dependency,
                     ts: TaxSchema,
                     tr: TaxRepository = Depends(get_repository),
                     tax_id: int = Path(gt=0)):

    tax = tr.get_by_id(_id=tax_id)

    if tax is None:
        raise HTTPException(status_code=404, detail="Tassa non trovato.")

    tr.update(edited_tax=tax, data=ts)
