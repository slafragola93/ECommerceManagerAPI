"""
Interfaccia per Order Repository seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from sqlalchemy.engine import Row
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.schemas.order_schema import OrderSchema, OrderUpdateSchema


class IOrderRepository(ABC):
    """Interface per la repository degli ordini"""
    
    @abstractmethod
    def get_all(self,
                orders_ids: Optional[str] = None,
                customers_ids: Optional[str] = None,
                order_states_ids: Optional[str] = None,
                shipping_states_ids: Optional[str] = None,
                delivery_countries_ids: Optional[str] = None,
                store_ids: Optional[str] = "1",
                platforms_ids: Optional[str] = None,
                payments_ids: Optional[str] = None,
                is_payed: Optional[bool] = None,
                is_invoice_requested: Optional[bool] = None,
                date_from: Optional[str] = None,
                date_to: Optional[str] = None,
                show_details: bool = False,
                page: int = 1,
                limit: int = 10
                ) -> List[Order]:
        """Recupera tutti gli ordini con filtri opzionali"""
        pass
    
    @abstractmethod
    def get_count(self,
                  orders_ids: Optional[str] = None,
                  customers_ids: Optional[str] = None,
                  order_states_ids: Optional[str] = None,
                  shipping_states_ids: Optional[str] = None,
                  delivery_countries_ids: Optional[str] = None,
                  store_ids: Optional[str] = "1",
                  platforms_ids: Optional[str] = None,
                  payments_ids: Optional[str] = None,
                  is_payed: Optional[bool] = None,
                  is_invoice_requested: Optional[bool] = None,
                  date_from: Optional[str] = None,
                  date_to: Optional[str] = None
                  ) -> int:
        """Conta gli ordini con filtri opzionali"""
        pass
    
    @abstractmethod
    def get_by_id(self, _id: int) -> Optional[Order]:
        """Recupera un ordine per ID"""
        pass
    
    @abstractmethod
    def get_order_history_by_id_order(self, id_order: int) -> list[dict]:
        """Restituisce la cronologia dell'ordine in formato [{state, data}]"""
        pass
    
    @abstractmethod
    def generate_shipping(self, data: OrderSchema) -> int:
        """Genera una spedizione di default basata sull'indirizzo di consegna"""
        pass
    
    @abstractmethod
    def create(self, data: OrderSchema) -> int:
        """Crea un nuovo ordine e restituisce l'ID"""
        pass
    
    @abstractmethod
    def update(self, edited_order: Order, data: OrderSchema | OrderUpdateSchema) -> Order:
        """Aggiorna un ordine esistente"""
        pass
    
    @abstractmethod
    def set_price(self, id_order: int, order_details: list[OrderDetail]) -> None:
        """Imposta il prezzo dell'ordine basandosi sugli order_details"""
        pass
    
    @abstractmethod
    def set_weight(self, id_order: int, order_details: list[OrderDetail]) -> None:
        """Imposta il peso dell'ordine basandosi sugli order_details"""
        pass
    
    @abstractmethod
    def update_order_status(self, id_order: int, id_order_state: int) -> bool:
        """Aggiorna lo stato di un ordine e aggiunge alla cronologia"""
        pass
    
    @abstractmethod
    def delete(self, order: Order) -> bool:
        """Elimina un ordine"""
        pass
    
    @abstractmethod
    def bulk_create_csv_import(self, data_list: List, id_platform: int = 1, batch_size: int = 1000) -> int:
        """Crea multiple ordini da CSV import"""
        pass
    
    @abstractmethod
    def formatted_output(self, order: Order, show_details: bool = False) -> dict:
        """Formatta un ordine per la risposta API"""
        pass
    
    @abstractmethod
    def get_by_origin_id(self, id_origin: int) -> Optional[Order]:
        """Recupera un ordine per origin ID"""
        pass
    
    @abstractmethod
    def get_id_by_origin_id(self, id_origin: int) -> Optional[int]:
        """Recupera l'ID di un ordine per origin ID (query idratata)"""
        pass
    
    @abstractmethod
    def get_shipment_data(self, order_id: int) -> Row:
        """Recupera solo i campi necessari per la creazione della spedizione (query idratata)"""
        pass
