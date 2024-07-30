from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, extract, desc
from sqlalchemy.orm import Session

from .. import AllInvoiceResponseSchema, InvoiceResponseSchema, InvoiceSchema, Payment
from ..models.invoice import Invoice
from ..services import QueryUtils


class InvoiceRepository:
    """
    Repository clienti
    """

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self,
                page: int = 1, limit: int = 10,
                **kwargs
                ) -> AllInvoiceResponseSchema:
        """
        Recupera tutti i clienti

        Returns:
            AllInvoiceResponseSchema: Tutti i clienti
        """
        document_number = kwargs.get('document_number')
        payed = kwargs.get('payed')
        date_from = kwargs.get('date_from') if kwargs.get('date_from') else None
        date_to = kwargs.get('date_to') if kwargs.get('date_to') else None
        order_id = kwargs.get('order_id')

        query = self.session.query(
            Invoice,
            Payment) \
            .order_by(desc(Invoice.id_invoice)) \
            .outerjoin(Payment, Invoice.id_payment == Payment.id_payment)

        if not kwargs:
            return query.offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

        query = QueryUtils.filter_by_string(query, Invoice, 'document_number',
                                            document_number) if document_number else query
        query = QueryUtils.filter_by_date(query, Invoice, 'date_add', date_from, date_to)
        query = query.filter(Invoice.id_order == order_id) if order_id else query
        query = query.filter(Invoice.payed == payed) if payed else query

        return query.offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_last_id(self) -> int:

        return self.session.query(Invoice).select(Invoice.id_invoice).order_by(Invoice.id_invoice.desc()).first()

    def get_count(self,
                  **kwargs) -> AllInvoiceResponseSchema:

        document_number = kwargs.get('document_number')
        payed = kwargs.get('payed')
        date_from = kwargs.get('date_from') if kwargs.get('date_from') else None
        date_to = kwargs.get('date_to') if kwargs.get('date_to') else None
        order_id = kwargs.get('order_id')

        query = self.session.query(func.count(Invoice.id_invoice))

        if not kwargs:
            return query.scalar()

        query = QueryUtils.filter_by_string(query, Invoice, 'document_number',
                                            document_number) if document_number else query
        query = QueryUtils.filter_by_date(query, Invoice, 'date_add', date_from, date_to)
        query = query.filter(Invoice.id_order == order_id) if order_id else query
        query = query.filter(Invoice.payed == payed) if payed else query

        return query.scalar()

    def get_by_id(self, _id: int) -> InvoiceResponseSchema:
        return self.session.query(Invoice).filter(Invoice.id_invoice == _id).first()

    def get_last_document_number(self) -> int:
        current_year = int(datetime.now().year)
        return self.session.query(func.max(Invoice.document_number)).filter(
            extract('year', Invoice.date_add) == current_year
        ).scalar()

    def create(self, data: InvoiceSchema):
        invoice = Invoice(**data.model_dump())
        self.session.add(invoice)
        self.session.commit()
        self.session.refresh(invoice)

    # def create_and_get_id(self, data: InvoiceSchema):
    #     """Funzione normalmente utilizzata nelle repository degli altri modelli per creare e recuperare ID"""
    #     invoice_new = Invoice(**data.model_dump())
    #     invoice = self.get_by_email(invoice_new.email)
    #     if invoice is None:
    #         invoice_new.date_add = date.today()
    #
    #         self.session.add(invoice_new)
    #         self.session.commit()
    #         self.session.refresh(invoice_new)
    #         return invoice_new.id_invoice
    #     else:
    #         return invoice.id_invoice
    #
    def update(self, edited_invoice: Invoice, data: InvoiceSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_invoice, key) and value is not None:
                setattr(edited_invoice, key, value)

        self.session.add(edited_invoice)
        self.session.commit()

    def delete(self, invoice: Invoice) -> bool:
        self.session.delete(invoice)
        self.session.commit()

        return True

    @staticmethod
    def formatted_output(invoice: Invoice,
                         payment: Payment = None) -> dict:
        return {
            "id_invoice": invoice.id_invoice,
            "id_order": invoice.id_order,
            "id_customer": invoice.id_customer,
            "id_address_delivery": invoice.id_address_delivery,
            "id_address_invoice": invoice.id_address_invoice,
            "id_payment": payment.id_payment if payment else None,
            "payment_name": payment.name if payment else None,
            "invoice_status": invoice.invoice_status,
            "note": invoice.note,
            "document_number": invoice.document_number,
            "payed": invoice.payed,
            "date_add": invoice.date_add,
        }
