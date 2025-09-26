from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from datetime import datetime

from src.models.invoice import Invoice
from src.models.address import Address
from src.models.customer import Customer
from src.schemas.invoice_schema import InvoiceSchema, InvoiceUpdateSchema


class InvoiceRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def get_all(self, page: int = 1, limit: int = 10, order_ids: Optional[str] = None) -> List[Invoice]:
        """Recupera tutte le fatture con paginazione"""
        query = self.session.query(Invoice)
        
        if order_ids:
            ids = [int(i) for i in order_ids.split(',')]
            query = query.filter(Invoice.id_order.in_(ids))
        
        return query.offset((page - 1) * limit).limit(limit).all()
    
    def get_count(self, order_ids: Optional[str] = None) -> int:
        """Conta il numero totale di fatture"""
        query = self.session.query(Invoice)
        
        if order_ids:
            ids = [int(i) for i in order_ids.split(',')]
            query = query.filter(Invoice.id_order.in_(ids))
        
        return query.count()
    
    def get_by_id(self, invoice_id: int) -> Optional[Invoice]:
        """Recupera una fattura per ID"""
        return self.session.query(Invoice).filter(Invoice.id_invoice == invoice_id).first()
    
    def get_by_order_id(self, order_id: int) -> List[Invoice]:
        """Recupera tutte le fatture per un ordine"""
        return self.session.query(Invoice).filter(Invoice.id_order == order_id).all()
    
    def get_by_document_number(self, document_number: str) -> Optional[Invoice]:
        """Recupera una fattura per numero documento"""
        return self.session.query(Invoice).filter(Invoice.document_number == document_number).first()
    
    def create_invoice(self, data: dict) -> int:
        """Crea una nuova fattura"""
        invoice = Invoice(**data)
        self.session.add(invoice)
        self.session.commit()
        self.session.refresh(invoice)
        return invoice.id_invoice
    
    def update(self, invoice: Invoice, data: InvoiceUpdateSchema):
        """Aggiorna una fattura esistente"""
        entity_updated = data.model_dump(exclude_unset=True)
        for key, value in entity_updated.items():
            if hasattr(invoice, key) and value is not None:
                setattr(invoice, key, value)
        
        invoice.date_upd = datetime.now()
        self.session.add(invoice)
        self.session.commit()
    
    def delete(self, invoice: Invoice) -> bool:
        """Elimina una fattura"""
        self.session.delete(invoice)
        self.session.commit()
        return True
    
    def get_next_document_number(self, year: int = None) -> str:
        """Genera il prossimo numero di documento sequenziale per l'anno"""
        if year is None:
            year = datetime.now().year
        
        query = text("""
            SELECT MAX(CAST(SUBSTRING(document_number, 1, 5) AS UNSIGNED)) as max_num
            FROM invoices 
            WHERE YEAR(date_add) = :year
        """)
        
        result = self.session.execute(query, {"year": year}).fetchone()
        max_num = result.max_num if result and result.max_num else 0
        
        # Incrementa di 1 e formatta con padding a 5 cifre
        next_num = max_num + 1
        return f"{next_num:05d}"
    
    def get_pec_by_customer_id(self, customer_id: int) -> Optional[str]:
        """
        Recupera la PEC di un customer in base al suo ID.
        Cerca in tutti gli indirizzi collegati al customer e restituisce la prima PEC trovata.
        
        Args:
            customer_id (int): ID del customer
            
        Returns:
            Optional[str]: La PEC del customer se trovata, None altrimenti
        """
        # Cerca la PEC negli indirizzi del customer
        address_with_pec = self.session.query(Address).filter(
            Address.id_customer == customer_id,
            Address.pec.isnot(None),
            Address.pec != ""
        ).first()
        
        if address_with_pec and address_with_pec.pec and address_with_pec.pec.strip():
            return address_with_pec.pec
        
        return None
    
    def formatted_output(self, invoice: Invoice) -> dict:
        """Formatta l'output di una fattura per l'API"""
        return {
            "id_invoice": invoice.id_invoice,
            "id_order": invoice.id_order,
            "document_number": invoice.document_number,
            "filename": invoice.filename,
            "status": invoice.status,
            "upload_result": invoice.upload_result,
            "date_add": invoice.date_add.isoformat() if invoice.date_add else None,
            "date_upd": invoice.date_upd.isoformat() if invoice.date_upd else None
        }