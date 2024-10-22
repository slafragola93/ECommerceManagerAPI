from typing import Optional

from fastapi import APIRouter, Path, HTTPException, Query, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from src.services.wrap import check_authentication, timing_decorator
from .. import InvoiceSchema, AllInvoiceResponseSchema, InvoiceResponseSchema
from ..repository.invoice_repository import InvoiceRepository
from ..services import tool
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/invoices',
    tags=['Invoice'],
)


def get_repository(db: db_dependency) -> InvoiceRepository:
    return InvoiceRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllInvoiceResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
@timing_decorator
async def get_all_invoices(
        user: user_dependency,
        ir: InvoiceRepository = Depends(get_repository),
        document_number: Optional[int] = None,
        payed: Optional[bool] = None,
        order_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = Query(1, gt=0),
        limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    if date_from or date_to:
        tool.validate_format_date(date_from)
        tool.validate_format_date(date_to)

    invoices = ir.get_all(page=page,
                          limit=limit,
                          order_id=order_id,
                          payed=payed,
                          date_from=date_from,
                          date_to=date_to,
                          document_number=document_number)

    if not invoices:
        raise HTTPException(status_code=404, detail="Nessuna fattura trovata")

    total_count = ir.get_count(order_id=order_id,
                               payed=payed,
                               date_from=date_from,
                               date_to=date_to,
                               document_number=document_number)
    results = []
    for invoice, payment in invoices:
        results.append(ir.formatted_output(invoice=invoice, payment=payment))
    return {"invoices": results, "total": total_count, "page": page, "limit": limit}


@router.get("/{invoice_id}", status_code=status.HTTP_200_OK, response_model=InvoiceResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_invoice_by_id(user: user_dependency,
                            ir: InvoiceRepository = Depends(get_repository),
                            invoice_id: int = Path(gt=0)):
    """
    Restituisce un singolo cliente basato sull'ID specificato.

    - **invoice_id**: Identificativo del cliente da ricercare.
    """

    result = ir.get_by_id_with_payment(_id=invoice_id)
    
    if result is None:
        raise HTTPException(status_code=404, detail="Fattura non trovata.")

    invoice, payment = result
    return ir.formatted_output(invoice, payment)


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Fattura creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_invoice(user: user_dependency,
                         invoice: InvoiceSchema,
                         ir: InvoiceRepository = Depends(get_repository)):

    last_document_number = ir.get_last_document_number()

    invoice.document_number = tool.document_number_generator(last_document_number)

    ir.create(data=invoice)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Fattura eliminata.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_invoice(user: user_dependency,
                         cr: InvoiceRepository = Depends(get_repository),
                         invoice_id: int = Path(gt=0)):
    """
    Elimina un cliente basato sull'ID specificato.

    - **invoice_id**: Identificativo del cliente da eliminare.
    """

    invoice = cr.get_by_id(_id=invoice_id)

    if invoice is None:
        raise HTTPException(status_code=404, detail="Fattura non trovata.")

    cr.delete(invoice=invoice)


@router.put("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Fattura modificata")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_invoice(user: user_dependency,
                         cs: InvoiceSchema,
                         ir: InvoiceRepository = Depends(get_repository),
                         invoice_id: int = Path(gt=0)):
    """
    Aggiorna i dati di un cliente esistente basato sull'ID specificato.

    - **invoice_id**: Identificativo del cliente da aggiornare.
    """
    invoice = ir.get_by_id(_id=invoice_id)

    if invoice is None:
        raise HTTPException(status_code=404, detail="Fattura non trovata.")

    ir.update(edited_invoice=invoice, data=cs)