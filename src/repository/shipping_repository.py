"""
Shipping Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List, Union
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc, select, update
from sqlalchemy.engine import Row
from src.models.shipping import Shipping
from src.models.order import Order
from src.models.order_document import OrderDocument
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.schemas.shipping_schema import ShippingSchema

class ShippingRepository(BaseRepository[Shipping, int], IShippingRepository):
    """Shipping Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Shipping)
    
    def get_all(self, **filters) -> List[Shipping]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Shipping.id_shipping))
            
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
            return query.count()
        except Exception as e:
            raise InfrastructureException(f"Database error counting {self._model_class.__name__}: {str(e)}")
    
    def get_by_name(self, name: str) -> Optional[Shipping]:
        """Ottiene un shipping per nome (case insensitive)"""
        try:
            return self._session.query(Shipping).filter(
                func.lower(Shipping.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving shipping by name: {str(e)}")
    
    def create_and_get_id(self, data: Union[ShippingSchema, dict], id_order: int = None) -> int:
        """
        Crea un shipping e restituisce l'ID.
        IMPORTANTE: Questo metodo viene chiamato solo quando necessario durante la creazione dell'ordine.
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[DEBUG] ShippingRepository.create_and_get_id chiamato - id_order: {id_order}")
        
        try:
            # Converti ShippingSchema in dict se necessario
            if isinstance(data, ShippingSchema):
                shipping_data = data.model_dump()
            else:
                shipping_data = data
            
            # Se price_tax_excl non fornito ma price_tax_incl sì, calcolalo
            if (shipping_data.get('price_tax_excl') is None or shipping_data.get('price_tax_excl') == 0) and shipping_data.get('price_tax_incl'):
                from src.services.core.tool import get_tax_percentage_by_address_delivery_id, calculate_price_without_tax
                from src.repository.tax_repository import TaxRepository
                
                tax_percentage = None
                # Se shipping è collegato a un ordine, recupera id_country da address_delivery dell'ordine
                if id_order:
                    from src.models.order import Order
                    id_address_delivery = self._session.query(Order.id_address_delivery).filter(Order.id_order == id_order).scalar()
                    if id_address_delivery:
                        tax_percentage = get_tax_percentage_by_address_delivery_id(self._session, id_address_delivery, default=None)
                
                # Se non trovato, usa percentuale default da app_configuration
                if tax_percentage is None:
                    tax_repo = TaxRepository(self._session)
                    tax_percentage = tax_repo.get_default_tax_percentage_from_app_config(default=22.0)
                
                shipping_data['price_tax_excl'] = calculate_price_without_tax(shipping_data['price_tax_incl'], tax_percentage)
            
            logger.warning(f"[DEBUG] ShippingRepository.create_and_get_id - creando shipping con dati: {shipping_data}")
            
            # Crea l'istanza del modello
            shipping = Shipping(**shipping_data)
            
            # Salva nel database
            self._session.add(shipping)
            self._session.commit()
            self._session.refresh(shipping)
            
            logger.warning(f"[DEBUG] ShippingRepository.create_and_get_id - shipping creato con ID: {shipping.id_shipping}")
            
            return shipping.id_shipping
        except Exception as e:
            self._session.rollback()
            logger.error(f"[DEBUG] ShippingRepository.create_and_get_id - ERRORE: {str(e)}")
            raise InfrastructureException(f"Database error creating shipping: {str(e)}")
    
    def get_carrier_info(self, id_shipping: int) -> Row:
        """Get id_carrier_api from shipping"""
        try:
            stmt = select(
                Shipping.id_shipping,
                Shipping.id_carrier_api,
                Shipping.tracking
            ).where(Shipping.id_shipping == id_shipping)
            
            result = self._session.execute(stmt).first()
            if not result:
                raise InfrastructureException(f"Shipping {id_shipping} not found")
            return result
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving carrier info: {str(e)}")
    
    def update_tracking(self, id_shipping: int, tracking: str) -> None:
        """Update tracking field"""
        try:
            stmt = update(Shipping).where(
                Shipping.id_shipping == id_shipping
            ).values(tracking=tracking)
            
            self._session.execute(stmt)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error updating tracking number: {str(e)}")
    
    def update_tracking_and_state(self, id_shipping: int, tracking: str, state_id: int) -> None:
        """Update tracking and id_shipping_state atomically"""
        try:
            stmt = update(Shipping).where(
                Shipping.id_shipping == id_shipping
            ).values(tracking=tracking, id_shipping_state=state_id)
            self._session.execute(stmt)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error updating tracking/state: {str(e)}")

    def update_state_by_tracking(self, tracking: str, state_id: int) -> int:
        """Update id_shipping_state by tracking. Returns affected rows count."""
        try:
            stmt = update(Shipping).where(
                Shipping.tracking == tracking
            ).values(id_shipping_state=state_id)
            result = self._session.execute(stmt)
            self._session.commit()
            return result.rowcount if hasattr(result, "rowcount") else 0
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Errore aggiornamento stato spedizione: {str(e)}")
    
    def update_shipping_to_cancelled_state(self, id_shipping: int) -> None:
        """Imposta lo stato della shipping a 11 (Annullato)"""
        try:
            stmt = update(Shipping).where(
                Shipping.id_shipping == id_shipping
            ).values(id_shipping_state=11)
            self._session.execute(stmt)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error updating shipping to cancelled state: {str(e)}")

    def update_weight(self, id_shipping: int, weight: float) -> None:
        """Aggiorna il peso della spedizione, degli ordini e dei preventivi associati"""
        try:
            # Aggiorna il peso della spedizione
            stmt = update(Shipping).where(
                Shipping.id_shipping == id_shipping
            ).values(weight=weight)
            self._session.execute(stmt)
            
            # Aggiorna il peso degli ordini associati a questa spedizione (solo con id_order_state = 1)
            stmt_orders = update(Order).where(
                Order.id_shipping == id_shipping,
                Order.id_order_state == 1
            ).values(total_weight=weight)
            self._session.execute(stmt_orders)
            
            # Aggiorna il peso dei preventivi (OrderDocument) associati a questa spedizione
            stmt_preventivi = update(OrderDocument).where(
                OrderDocument.id_shipping == id_shipping
            ).values(total_weight=weight)
            self._session.execute(stmt_preventivi)
            
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Errore aggiornamento peso spedizione: {str(e)}")
    
    def get_message_shipping(self, id_shipping: int) -> Optional[str]:
        """Recupera shipping_message dalla spedizione"""
        try:
            result = self._session.query(Shipping.shipping_message).filter(
                Shipping.id_shipping == id_shipping
            ).first()
            if result:
                # result è una tupla (shipping_message,), estraiamo il primo elemento
                return result[0] if isinstance(result, tuple) else result
            return None
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving shipping message: {str(e)}")
    
    def update_customs_value_from_order(self, id_shipping: int) -> None:
        """Aggiorna customs_value della spedizione basandosi sul totale dell'ordine associato"""
        try:
            # Recupera lo shipping
            shipping = self._session.query(Shipping).filter(
                Shipping.id_shipping == id_shipping
            ).first()
            
            if not shipping:
                return
            
            # Se customs_value è già impostato, non fare nulla
            if shipping.customs_value is not None:
                return
            
            # Recupera l'ordine associato a questa spedizione
            order = self._session.query(Order).filter(
                Order.id_shipping == id_shipping
            ).first()
            
            if order and order.total_price_with_tax:
                # Imposta customs_value al totale dell'ordine (con IVA)
                shipping.customs_value = order.total_price_with_tax
                self._session.commit()
        except Exception as e:
            self._session.rollback()
            # Non sollevare eccezione per non bloccare il flusso
            pass
    