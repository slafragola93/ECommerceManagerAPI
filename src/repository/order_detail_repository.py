"""
Order Detail Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from src.models.order_detail import OrderDetail
from src.repository.interfaces.order_detail_repository_interface import IOrderDetailRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException

class OrderDetailRepository(BaseRepository[OrderDetail, int], IOrderDetailRepository):
    """Order Detail Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, OrderDetail)
    
    def get_all(self, **filters) -> List[OrderDetail]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(OrderDetail.id_order_detail))
            
            # Filtri specifici per Order Detail
            if 'order_ids' in filters and filters['order_ids']:
                ids = [int(x.strip()) for x in filters['order_ids'].split(',') if x.strip().isdigit()]
                if ids:
                    query = query.filter(OrderDetail.id_order.in_(ids))
            
            if 'order_document_ids' in filters and filters['order_document_ids']:
                doc_ids = [int(x.strip()) for x in filters['order_document_ids'].split(',') if x.strip().isdigit()]
                if doc_ids:
                    query = query.filter(OrderDetail.id_order_document.in_(doc_ids))
            
            if 'product_ids' in filters and filters['product_ids']:
                prod_ids = [int(x.strip()) for x in filters['product_ids'].split(',') if x.strip().isdigit()]
                if prod_ids:
                    query = query.filter(OrderDetail.id_product.in_(prod_ids))
            
            # Paginazione
            page = filters.get('page', 1)
            limit = filters.get('limit', 100)
            offset = self.get_offset(limit, page)
            
            return query.offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__} list: {str(e)}")
    
    def get_count(self, **filters) -> int:
        """Conta le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class)
            
            # Applica gli stessi filtri di get_all
            if 'order_ids' in filters and filters['order_ids']:
                ids = [int(x.strip()) for x in filters['order_ids'].split(',') if x.strip().isdigit()]
                if ids:
                    query = query.filter(OrderDetail.id_order.in_(ids))
            
            if 'order_document_ids' in filters and filters['order_document_ids']:
                doc_ids = [int(x.strip()) for x in filters['order_document_ids'].split(',') if x.strip().isdigit()]
                if doc_ids:
                    query = query.filter(OrderDetail.id_order_document.in_(doc_ids))
            
            if 'product_ids' in filters and filters['product_ids']:
                prod_ids = [int(x.strip()) for x in filters['product_ids'].split(',') if x.strip().isdigit()]
                if prod_ids:
                    query = query.filter(OrderDetail.id_product.in_(prod_ids))
            
            return query.count()
        except Exception as e:
            raise InfrastructureException(f"Database error counting {self._model_class.__name__}: {str(e)}")
    
    def get_by_order_id(self, order_id: int) -> List[OrderDetail]:
        """Ottiene tutti i dettagli ordine per un ordine specifico"""
        try:
            return self._session.query(OrderDetail).filter(
                OrderDetail.id_order == order_id
            ).order_by(OrderDetail.id_order_detail).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving order details by order ID: {str(e)}")
    
    def get_by_order_document_id(self, order_document_id: int) -> List[OrderDetail]:
        """Ottiene tutti i dettagli ordine per un documento ordine specifico"""
        try:
            return self._session.query(OrderDetail).filter(
                OrderDetail.id_order_document == order_document_id
            ).order_by(OrderDetail.id_order_detail).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving order details by order document ID: {str(e)}")
    
    def get_by_product_id(self, product_id: int) -> List[OrderDetail]:
        """Ottiene tutti i dettagli ordine per un prodotto specifico"""
        try:
            return self._session.query(OrderDetail).filter(
                OrderDetail.id_product == product_id
            ).order_by(OrderDetail.id_order_detail).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving order details by product ID: {str(e)}")
    
    def formatted_output(self, order_detail: OrderDetail) -> dict:
        """Formatta un OrderDetail per la risposta API"""
        return {
            "id_order_detail": order_detail.id_order_detail,
            "id_order": order_detail.id_order,
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
            "reduction_amount": order_detail.reduction_amount
        }