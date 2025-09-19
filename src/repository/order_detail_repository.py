from fastapi import HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .product_repository import ProductRepository
from ..models import OrderDetail
from src.schemas.order_detail_schema import *
from src.services import QueryUtils


class OrderDetailRepository:

    def __init__(self,
                 session: Session,
                 ):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session
        self.product_repository = ProductRepository(session)

    def get_all(self,
                page: int = 1, limit: int = 10,
                **kwargs
                ) -> AllOrderDetailsResponseSchema:

        order_details_ids = kwargs.get('order_details_ids')
        order_ids = kwargs.get('order_ids')
        invoice_ids = kwargs.get('invoice_ids')
        document_ids = kwargs.get('document_ids')
        origin_ids = kwargs.get('origin_ids')
        product_ids = kwargs.get('product_ids')
        search_value = kwargs.get('search_value')
        rda = kwargs.get('rda')

        query = self.session.query(OrderDetail).order_by(desc(OrderDetail.id_order_detail))

        try:
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_order_detail',
                                            order_details_ids) if order_details_ids else query
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_order', order_ids) if order_ids else query
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_invoice', invoice_ids) if invoice_ids else query
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_order_document',
                                            document_ids) if document_ids else query
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_origin', origin_ids) if origin_ids else query
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_product', product_ids) if product_ids else query
            query = QueryUtils.search_in_every_field(query, OrderDetail, search_value, "product_name",
                                                     "product_reference", "rda") if search_value else query
            query = QueryUtils.filter_by_string(query, OrderDetail, 'rda', rda) if rda else query

        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")

        return query.offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_by_id_order(self, id_order: int) -> list[OrderDetail]:
        return self.session.query(OrderDetail).filter(OrderDetail.id_order == id_order).all()

    def get_count(self,
                  **kwargs,
                  ) -> AllOrderDetailsResponseSchema:

        order_details_ids = kwargs.get('order_details_ids')
        order_ids = kwargs.get('order_ids')
        invoice_ids = kwargs.get('invoice_ids')
        document_ids = kwargs.get('document_ids')
        origin_ids = kwargs.get('origin_ids')
        product_ids = kwargs.get('product_ids')
        search_value = kwargs.get('search_value')
        rda = kwargs.get('rda')

        query = self.session.query(OrderDetail)

        try:
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_order_detail',
                                            order_details_ids) if order_details_ids else query
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_order', order_ids) if order_ids else query
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_invoice', invoice_ids) if invoice_ids else query
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_order_document',
                                            document_ids) if document_ids else query
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_origin', origin_ids) if origin_ids else query
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_product', product_ids) if product_ids else query
            query = QueryUtils.search_in_every_field(query, OrderDetail, search_value, "product_name",
                                                     "product_reference", "rda") if search_value else query
            query = QueryUtils.filter_by_string(query, OrderDetail, 'rda', rda) if rda else query

        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")

        total_count = query.scalar()
        return total_count

    def get_by_id(self, _id: int) -> OrderDetailResponseSchema:
        return self.session.query(OrderDetail).filter(OrderDetail.id_order_detail == _id).first()

    def create(self, data: OrderDetailSchema):
        order_detail = OrderDetail(**data.model_dump())
        # Get live price and weight based on the order's platform
        self.session.add(order_detail)
        self.session.commit()

    def create_and_get_id(self, data: OrderDetailSchema):
        """Funzione normalmente utilizzata nelle repository degli altri modelli per creare e recuperare ID"""
        order_detail = OrderDetail(**data.model_dump())
        self.session.add(order_detail)
        self.session.commit()
        self.session.refresh(order_detail)
        return order_detail.id_order_detail

    def update(self, edited_order_detail: OrderDetail, data: OrderDetailSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_order_detail, key) and value is not None:
                setattr(edited_order_detail, key, value)

        self.session.add(edited_order_detail)
        self.session.commit()

    def delete(self, order_detail: OrderDetail) -> bool:
        self.session.delete(order_detail)
        self.session.commit()

        return True

    def formatted_output(self, order_detail: OrderDetail):
        """
        Formatta l'output di un order detail
        """
        return {
            "id_order_detail": order_detail.id_order_detail,
            "id_order": order_detail.id_order,
            "id_invoice": order_detail.id_invoice,
            "id_order_document": order_detail.id_order_document,
            "id_origin": order_detail.id_origin,
            "id_product": order_detail.id_product,
            "product_name": order_detail.product_name,
            "product_reference": order_detail.product_reference,
            "product_qty": order_detail.product_qty,
            "product_price": order_detail.product_price,
            "product_weight": order_detail.product_weight,
            "rda": order_detail.rda,
            "reduction_percent": order_detail.reduction_percent,
            "reduction_amount": order_detail.reduction_amount
        }