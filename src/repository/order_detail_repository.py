from fastapi import HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .product_repository import ProductRepository
from ..models import OrderDetail
from src.schemas.order_detail_schema import *
from src.services import QueryUtils
from src.services.tool import calculate_order_totals, apply_order_totals_to_order


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
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_fiscal_document', invoice_ids) if invoice_ids else query
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
            query = QueryUtils.filter_by_id(query, OrderDetail, 'id_fiscal_document', invoice_ids) if invoice_ids else query
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
        
        # Aggiorna dinamicamente tutti i totali dell'ordine (prezzo, peso, sconti)
        if data.id_order:
            self._update_order_totals(data.id_order)
        
        # Aggiorna dinamicamente tutti i totali del preventivo (prezzo, peso, sconti)
        if data.id_order_document:
            self._update_preventivo_totals(data.id_order_document)

    def create_and_get_id(self, data: OrderDetailSchema):
        """Funzione normalmente utilizzata nelle repository degli altri modelli per creare e recuperare ID"""
        order_detail = OrderDetail(**data.model_dump())
        self.session.add(order_detail)
        self.session.commit()
        self.session.refresh(order_detail)
        
        # Aggiorna dinamicamente tutti i totali dell'ordine (prezzo, peso, sconti)
        if data.id_order:
            self._update_order_totals(data.id_order)
        
        # Aggiorna dinamicamente tutti i totali del preventivo (prezzo, peso, sconti)
        if data.id_order_document:
            self._update_preventivo_totals(data.id_order_document)
        
        return order_detail.id_order_detail

    def update(self, edited_order_detail: OrderDetail, data: OrderDetailSchema):
        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_order_detail, key) and value is not None:
                setattr(edited_order_detail, key, value)

        self.session.add(edited_order_detail)
        self.session.commit()
        
        # Aggiorna dinamicamente tutti i totali dell'ordine (prezzo, peso, sconti)
        if edited_order_detail.id_order:
            self._update_order_totals(edited_order_detail.id_order)
        
        # Aggiorna dinamicamente tutti i totali del preventivo (prezzo, peso, sconti)
        if edited_order_detail.id_order_document:
            self._update_preventivo_totals(edited_order_detail.id_order_document)

    def delete(self, order_detail: OrderDetail) -> bool:
        order_id = order_detail.id_order
        order_document_id = order_detail.id_order_document
        self.session.delete(order_detail)
        self.session.commit()
        
        # Aggiorna dinamicamente tutti i totali dell'ordine (prezzo, peso, sconti)
        if order_id:
            self._update_order_totals(order_id)
        
        # Aggiorna dinamicamente tutti i totali del preventivo (prezzo, peso, sconti)
        if order_document_id:
            self._update_preventivo_totals(order_document_id)

        return True

    def _get_tax_percentages(self, order_details: list) -> dict:
        """
        Recupera le percentuali delle tasse per gli order details
        
        Args:
            order_details: Lista di OrderDetail objects
            
        Returns:
            dict: Dizionario {id_tax: percentage}
        """
        from src.models.tax import Tax
        
        tax_ids = set()
        for order_detail in order_details:
            if hasattr(order_detail, 'id_tax') and order_detail.id_tax:
                tax_ids.add(order_detail.id_tax)
        
        if not tax_ids:
            return {}
        
        taxes = self.session.query(Tax).filter(Tax.id_tax.in_(tax_ids)).all()
        return {tax.id_tax: tax.percentage for tax in taxes}

    def _update_order_totals(self, order_id: int) -> bool:
        """
        Aggiorna i totali di un ordine ricalcolando tutto
        
        Args:
            order_id: ID dell'ordine da aggiornare
            
        Returns:
            bool: True se l'aggiornamento è riuscito
        """
        from src.models.order import Order
        
        try:
            # Recupera tutti gli order details dell'ordine
            order_details = self.session.query(OrderDetail).filter(OrderDetail.id_order == order_id).all()
            
            if not order_details:
                # Se non ci sono order details, azzera i totali
                order = self.session.query(Order).filter(Order.id_order == order_id).first()
                if order:
                    order.total_price = 0.0
                    order.total_weight = 0.0
                    order.total_discounts = 0.0
                    self.session.add(order)
                    self.session.commit()
                return True
            
            # Recupera le percentuali delle tasse
            tax_percentages = self._get_tax_percentages(order_details)
            
            # Calcola i totali
            totals = calculate_order_totals(order_details, tax_percentages)
            
            # Aggiorna l'ordine
            order = self.session.query(Order).filter(Order.id_order == order_id).first()
            if order:
                # Usa il prezzo base senza tasse per mantenere la compatibilità
                apply_order_totals_to_order(order, totals, use_tax_included=False)
                self.session.add(order)
                self.session.commit()
                return True
            else:
                return False
                
        except Exception as e:
            self.session.rollback()
            print(f"Errore nell'aggiornamento dei totali per l'ordine {order_id}: {e}")
            return False

    def _update_preventivo_totals(self, order_document_id: int) -> bool:
        """
        Aggiorna i totali di un preventivo basandosi sui suoi articoli
        
        Args:
            order_document_id: ID del documento ordine (preventivo)
            
        Returns:
            bool: True se aggiornamento riuscito, False altrimenti
        """
        from src.models.order_document import OrderDocument
        from src.services.tool import calculate_order_totals, apply_order_totals_to_order
        
        try:
            # Recupera tutti gli articoli del preventivo
            order_details = self.session.query(OrderDetail).filter(
                OrderDetail.id_order_document == order_document_id
            ).all()
            
            if not order_details:
                # Se non ci sono articoli, azzera i totali
                order_document = self.session.query(OrderDocument).filter(
                    OrderDocument.id_order_document == order_document_id
                ).first()
                if order_document:
                    order_document.total_price = 0.0
                    order_document.total_weight = 0.0
                    self.session.add(order_document)
                    self.session.commit()
                return True
            
            # Recupera le percentuali delle tasse
            tax_percentages = self._get_tax_percentages(order_details)
            
            # Calcola i totali usando le funzioni pure
            totals = calculate_order_totals(order_details, tax_percentages)
            
            # Aggiorna il documento ordine
            order_document = self.session.query(OrderDocument).filter(
                OrderDocument.id_order_document == order_document_id
            ).first()
            
            if order_document:
                # Per i preventivi usiamo il prezzo con tasse
                order_document.total_price = totals['total_price_with_tax']
                order_document.total_weight = totals['total_weight']
                self.session.add(order_document)
                self.session.commit()
                return True
            else:
                return False
                
        except Exception as e:
            self.session.rollback()
            print(f"Errore nell'aggiornamento dei totali per il preventivo {order_document_id}: {e}")
            return False

    def formatted_output(self, order_detail: OrderDetail):
        """
        Formatta l'output di un order detail
        """
        return {
            "id_order_detail": order_detail.id_order_detail,
            "id_order": order_detail.id_order,
            "id_fiscal_document": order_detail.id_fiscal_document,
            "id_order_document": order_detail.id_order_document,
            "id_origin": order_detail.id_origin,
            "id_tax": order_detail.id_tax,
            "id_product": order_detail.id_product,
            "product_name": order_detail.product_name,
            "product_reference": order_detail.product_reference,
            "product_qty": order_detail.product_qty,
            "product_price": order_detail.product_price,
            "product_weight": order_detail.product_weight,
            "reduction_percent": order_detail.reduction_percent,
            "rda": order_detail.rda,
            "reduction_percent": order_detail.reduction_percent,
            "reduction_amount": order_detail.reduction_amount
        }