from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from src.repository.ddt_repository import DDTRepository
from src.services.routers.order_document_service import OrderDocumentService
from src.models.app_configuration import AppConfiguration
from src.schemas.ddt_schema import (
    DDTResponseSchema, 
    DDTDetailSchema, 
    DDTPackageSchema, 
    DDTSenderSchema,
    DDTGenerateResponseSchema
)
from src.models.customer import Customer
from src.models.address import Address
from src.models.shipping import Shipping
from src.models.order_package import OrderPackage


class DDTService:
    """Service per la logica business dei DDT"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ddt_repo = DDTRepository(db)
        self.order_doc_service = OrderDocumentService(db)
    
    def generate_ddt_from_order(self, id_order: int, user_id: int) -> DDTGenerateResponseSchema:
        """
        Genera un DDT a partire da un ordine
        
        Args:
            id_order: ID dell'ordine
            user_id: ID dell'utente
            
        Returns:
            DDTGenerateResponseSchema: Risposta con il DDT generato
        """
        try:
            # Crea il DDT
            ddt = self.ddt_repo.create_ddt_from_order(id_order, user_id)
            
            if not ddt:
                return DDTGenerateResponseSchema(
                    success=False,
                    message="Ordine non trovato"
                )
            
            # Recupera il DDT completo con tutti i dati
            ddt_complete = self.get_ddt_complete(ddt.id_order_document)
            
            return DDTGenerateResponseSchema(
                success=True,
                message=f"DDT {ddt.document_number} generato con successo",
                ddt=ddt_complete
            )
            
        except ValueError as e:
            return DDTGenerateResponseSchema(
                success=False,
                message=str(e)
            )
        except Exception as e:
            return DDTGenerateResponseSchema(
                success=False,
                message=f"Errore durante la generazione del DDT: {str(e)}"
            )
    
    def get_ddt_complete(self, id_order_document: int) -> Optional[DDTResponseSchema]:
        """
        Recupera un DDT completo con tutti i dati
        
        Args:
            id_order_document: ID del DDT
            
        Returns:
            DDTResponseSchema: DDT completo
        """
        ddt = self.ddt_repo.get_ddt_with_details(id_order_document)
        if not ddt:
            return None
        
        # Recupera i dettagli (articoli)
        details = self.ddt_repo.get_ddt_details(id_order_document)
        details_schema = [
            DDTDetailSchema(
                id_order_detail=d.id_order_detail,
                id_product=d.id_product,
                product_name=d.product_name,
                product_reference=d.product_reference,
                product_qty=d.product_qty,
                product_price=d.product_price,
                product_weight=d.product_weight,
                id_tax=d.id_tax,
                reduction_percent=d.reduction_percent,
                reduction_amount=d.reduction_amount
            ) for d in details
        ]
        
        # Recupera i pacchi se c'è un ordine collegato
        packages_schema = []
        if ddt.id_order:
            packages = self.ddt_repo.get_ddt_packages(ddt.id_order)
            packages_schema = [
                DDTPackageSchema(
                    id_order_package=p.id_order_package,
                    height=p.height,
                    width=p.width,
                    depth=p.depth,
                    weight=p.weight,
                    value=p.value
                ) for p in packages
            ]
        
        # Recupera dati cliente
        customer_data = None
        if ddt.id_customer:
            customer = self.db.query(Customer).filter(Customer.id_customer == ddt.id_customer).first()
            if customer:
                customer_data = {
                    "id_customer": customer.id_customer,
                    "firstname": customer.firstname,
                    "lastname": customer.lastname,
                    "email": customer.email
                }
        
        # Recupera indirizzo di consegna
        address_delivery_data = None
        if ddt.id_address_delivery:
            address = self.db.query(Address).filter(Address.id_address == ddt.id_address_delivery).first()
            if address:
                address_delivery_data = {
                    "id_address": address.id_address,
                    "firstname": address.firstname,
                    "lastname": address.lastname,
                    "address1": address.address1,
                    "address2": address.address2,
                    "city": address.city,
                    "postcode": address.postcode,
                    "phone": address.phone
                }
        
        # Recupera indirizzo di fatturazione
        address_invoice_data = None
        if ddt.id_address_invoice:
            address = self.db.query(Address).filter(Address.id_address == ddt.id_address_invoice).first()
            if address:
                address_invoice_data = {
                    "id_address": address.id_address,
                    "firstname": address.firstname,
                    "lastname": address.lastname,
                    "address1": address.address1,
                    "address2": address.address2,
                    "city": address.city,
                    "postcode": address.postcode,
                    "phone": address.phone
                }
        
        # Recupera dati spedizione
        shipping_data = None
        if ddt.id_shipping:
            shipping = self.db.query(Shipping).filter(Shipping.id_shipping == ddt.id_shipping).first()
            if shipping:
                shipping_data = {
                    "id_shipping": shipping.id_shipping,
                    "tracking": shipping.tracking,
                    "weight": shipping.weight,
                    "price_tax_incl": shipping.price_tax_incl,
                    "price_tax_excl": shipping.price_tax_excl,
                    "shipping_message": shipping.shipping_message
                }
        
        # Recupera dati mittente
        sender_config = self.order_doc_service.get_sender_config()
        
        # Recupera il logo dalla configurazione company_logo
        company_logo_config = self.db.query(AppConfiguration).filter(
            and_(
                AppConfiguration.category == "company_info",
                AppConfiguration.name == "company_logo"
            )
        ).first()
        
        logo_path = company_logo_config.value if company_logo_config else None
        
        sender_schema = DDTSenderSchema(
            company_name=sender_config.get("ddt_sender_company_name", ""),
            address=sender_config.get("ddt_sender_address", ""),
            vat=sender_config.get("ddt_sender_vat", ""),
            phone=sender_config.get("ddt_sender_phone", ""),
            email=sender_config.get("ddt_sender_email", ""),
            logo_path=logo_path
        )
        
        # Verifica se il DDT è modificabile
        is_modifiable = self.ddt_repo.is_ddt_modifiable(id_order_document)
        
        return DDTResponseSchema(
            id_order_document=ddt.id_order_document,
            document_number=ddt.document_number,
            type_document=ddt.type_document,
            date_add=ddt.date_add,
            updated_at=ddt.updated_at,
            note=ddt.note,
            total_weight=ddt.total_weight,
            total_price_with_tax=ddt.total_price_with_tax,
            id_order=ddt.id_order or 0,
            customer=customer_data,
            address_delivery=address_delivery_data,
            address_invoice=address_invoice_data,
            shipping=shipping_data,
            details=details_schema,
            packages=packages_schema,
            sender=sender_schema,
            is_modifiable=is_modifiable
        )
    
    def generate_ddt_pdf(self, id_order_document: int) -> bytes:
        """
        Genera il PDF del DDT
        
        Args:
            id_order_document: ID del DDT
            
        Returns:
            bytes: Contenuto del PDF
        """
        try:
            from src.services.pdf.ddt_pdf_service import DDTPDFService
            
            # Recupera i dati del DDT
            ddt_data = self.get_ddt_complete(id_order_document)
            if not ddt_data:
                raise ValueError("DDT non trovato")
            
            # Usa DDTPDFService per generare il PDF
            pdf_service = DDTPDFService()
            return pdf_service.generate_pdf(ddt_data=ddt_data)
            
        except ImportError:
            raise Exception("Libreria fpdf2 non installata. Installare con: pip install fpdf2")
        except Exception as e:
            raise Exception(f"Errore durante la generazione del PDF: {str(e)}")
    
    def update_ddt_detail(self, id_order_detail: int, detail_data: dict) -> Optional[DDTDetailSchema]:
        """
        Aggiorna un dettaglio del DDT
        
        Args:
            id_order_detail: ID del dettaglio
            detail_data: Dati da aggiornare
            
        Returns:
            DDTDetailSchema: Dettaglio aggiornato
        """
        try:
            updated_detail = self.ddt_repo.update_ddt_detail(id_order_detail, **detail_data)
            
            if not updated_detail:
                return None
            
            return DDTDetailSchema(
                id_order_detail=updated_detail.id_order_detail,
                id_product=updated_detail.id_product,
                product_name=updated_detail.product_name,
                product_reference=updated_detail.product_reference,
                product_qty=updated_detail.product_qty,
                product_price=updated_detail.product_price,
                product_weight=updated_detail.product_weight,
                id_tax=updated_detail.id_tax,
                reduction_percent=updated_detail.reduction_percent,
                reduction_amount=updated_detail.reduction_amount
            )
            
        except ValueError as e:
            raise e
        except Exception as e:
            raise Exception(f"Errore durante l'aggiornamento del dettaglio: {str(e)}")
    
    def delete_ddt_detail(self, id_order_detail: int) -> bool:
        """
        Elimina un dettaglio del DDT
        
        Args:
            id_order_detail: ID del dettaglio
            
        Returns:
            bool: True se eliminato con successo
        """
        try:
            return self.ddt_repo.delete_ddt_detail(id_order_detail)
        except ValueError as e:
            raise e
        except Exception as e:
            raise Exception(f"Errore durante l'eliminazione del dettaglio: {str(e)}")
