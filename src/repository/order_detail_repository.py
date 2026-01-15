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
from src.models.order_document import OrderDocument
from src.schemas.order_detail_schema import OrderDetailSchema

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
    
    def formatted_output(self, order_detail: OrderDetail, img_url: Optional[str] = None) -> dict:
        """
        Formatta un OrderDetail per la risposta API.
        Segue OCP: aperto all'estensione (img_url) senza modificare la logica base.
        
        Args:
            order_detail: OrderDetail da formattare
            img_url: URL immagine prodotto (opzionale, per evitare query duplicate)
        
        Returns:
            Dictionary formattato per la risposta API
        """
        # Recupera img_url dal prodotto se non fornita
        if img_url is None:
            if order_detail.id_product:
                from src.models.product import Product
                product = self._session.query(Product.id_product, Product.img_url).filter(
                    Product.id_product == order_detail.id_product
                ).first()
                if product and product.img_url:
                    img_url = product.img_url
                else:
                    img_url = "media/product_images/fallback/product_not_found.jpg"
            else:
                img_url = "media/product_images/fallback/product_not_found.jpg"
        
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
            "unit_price_net": order_detail.unit_price_net,
            "unit_price_with_tax": order_detail.unit_price_with_tax,
            "total_price_net": order_detail.total_price_net,
            "total_price_with_tax": order_detail.total_price_with_tax,
            "product_weight": order_detail.product_weight,
            "reduction_percent": order_detail.reduction_percent,
            "reduction_amount": order_detail.reduction_amount,
            "rda": order_detail.rda,
            "rda_quantity": order_detail.rda_quantity,
            "note": order_detail.note,
            "img_url": img_url
        }
    
    def get_by_order_detail_and_order(self, id_order_detail: int, id_order: int) -> Optional[OrderDetail]:
        """
        Ottiene un OrderDetail per id_order_detail e id_order
        
        Args:
            id_order_detail: ID dell'OrderDetail
            id_order: ID dell'ordine
            
        Returns:
            OrderDetail se trovato, None altrimenti
        """
        return self._session.query(OrderDetail).filter(
                OrderDetail.id_order_detail == id_order_detail,
                OrderDetail.id_order == id_order
            ).first()
    
    def check_order_detail(self, id_order_detail: int, id_order: int) -> Optional[OrderDetail]:
        """
        Verifica e ottiene un OrderDetail per id_order_detail e id_order.
        Alias di get_by_order_detail_and_order per compatibilità.
        
        Args:
            id_order_detail: ID dell'OrderDetail
            id_order: ID dell'ordine
            
        Returns:
            OrderDetail se trovato, None altrimenti
        """
        return self.get_by_order_detail_and_order(id_order_detail, id_order)
    
    def get_first_order_detail_by_id(self, id_order_detail: int) -> Optional[OrderDetail]:
        """
        Ottiene il primo OrderDetail per id_order_detail
        
        Args:
            id_order_detail: ID dell'OrderDetail
            
        Returns:
            OrderDetail se trovato, None altrimenti
        """
        return self._session.query(OrderDetail).filter(
                OrderDetail.id_order_detail == id_order_detail
            ).first()
    
    def get_by_id_order_detail(self, id_order_detail: int) -> Optional[OrderDetail]:
        """
        Ottiene un OrderDetail per id_order_detail.
        Alias di get_first_order_detail_by_id per compatibilità.
        
        Args:
            id_order_detail: ID dell'OrderDetail
            
        Returns:
            OrderDetail se trovato, None altrimenti
        """
        return self.get_first_order_detail_by_id(id_order_detail)
    
    
    def get_by_order_document_and_order_zero(
        self, 
        id_order_document: int
    ) -> List[OrderDetail]:
        """
        Ottiene tutti gli OrderDetail per un documento ordine con id_order=0
        (solo righe documento, non righe ordine)
        
        Args:
            id_order_document: ID del documento ordine
            
        Returns:
            Lista di OrderDetail
        """
        return self._session.query(OrderDetail).filter(
                OrderDetail.id_order_document == id_order_document,
                OrderDetail.id_order == 0
            ).all()
    
    def bulk_create_csv_import(self, data_list: List[OrderDetailSchema], batch_size: int = 1000) -> int:
        """
        Bulk insert order details da CSV import.
        
        Order details non hanno id_platform diretto, dipendono dall'ordine.
        
        Args:
            data_list: Lista OrderDetailSchema da inserire
            batch_size: Dimensione batch (default: 1000)
            
        Returns:
            Numero order details inseriti
        """
        if not data_list:
            return 0
        
        try:
            # Order details non hanno duplicate check su id_origin
            # Vengono sempre inseriti se l'ordine esiste
            total_inserted = 0
            for i in range(0, len(data_list), batch_size):
                batch = data_list[i:i + batch_size]
                details = [OrderDetail(**d.model_dump()) for d in batch]
                self._session.bulk_save_objects(details)
                total_inserted += len(details)
            
            self._session.commit()
            return total_inserted
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error bulk creating order details: {str(e)}")