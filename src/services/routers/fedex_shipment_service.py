# Standard library
import base64
from collections import namedtuple
import hashlib
import logging
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

# Third-party
import httpx
from pypdf import PdfReader, PdfWriter
from sqlalchemy import select

# Local - Core
from src.core.exceptions import (
    BusinessRuleException,
    InfrastructureException,
    NotFoundException,
    ValidationException,
)
from src.core.settings import get_cache_settings

# Local - Models
from src.models.fedex_configuration import FedexScopeEnum
from src.models.order_document import OrderDocument
from src.models.shipment_document import ShipmentDocument

# Local - Repositories
from src.repository.interfaces.address_repository_interface import IAddressRepository
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.repository.interfaces.country_repository_interface import ICountryRepository
from src.repository.interfaces.fedex_configuration_repository_interface import IFedexConfigurationRepository
from src.repository.interfaces.order_detail_repository_interface import IOrderDetailRepository
from src.repository.interfaces.order_package_repository_interface import IOrderPackageRepository
from src.repository.interfaces.order_repository_interface import IOrderRepository
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.repository.order_document_repository import OrderDocumentRepository
from src.repository.shipment_document_repository import ShipmentDocumentRepository

# Local - Services
from src.services.ecommerce.shipments.fedex_client import FedexClient
from src.services.ecommerce.shipments.fedex_mapper import FedexMapper
from src.services.interfaces.fedex_shipment_service_interface import IFedexShipmentService

logger = logging.getLogger(__name__)

# Namedtuple per rappresentare un package con peso corretto
PackageRow = namedtuple('PackageRow', ['id_order_package', 'id_order_document', 'weight', 'length', 'width', 'height'])


class FedexShipmentService(IFedexShipmentService):
    """FedEx Shipment service for creating shipments and managing documents"""
    
    def __init__(
        self,
        order_repository: IOrderRepository,
        shipping_repository: IShippingRepository,
        carrier_api_repository: IApiCarrierRepository,
        fedex_config_repository: IFedexConfigurationRepository,
        address_repository: IAddressRepository,
        country_repository: ICountryRepository,
        order_package_repository: IOrderPackageRepository,
        order_detail_repository: IOrderDetailRepository,
        fedex_client: FedexClient,
        fedex_mapper: FedexMapper
    ):
        self.order_repository = order_repository
        self.shipping_repository = shipping_repository
        self.carrier_api_repository = carrier_api_repository
        self.fedex_config_repository = fedex_config_repository
        self.address_repository = address_repository
        self.country_repository = country_repository
        self.order_package_repository = order_package_repository
        self.order_detail_repository = order_detail_repository
        self.fedex_client = fedex_client
        self.fedex_mapper = fedex_mapper
        self.settings = get_cache_settings()
    
    def _get_shipping_document_minimal(self, id_order_document: int) -> Optional[Any]:
        """
        Recupera solo i campi necessari di un OrderDocument di tipo "shipping" (query idratata)
        
        Args:
            id_order_document: ID del documento
            
        Returns:
            SimpleNamespace con id_order_document, id_order, id_shipping, total_weight
            o None se non trovato
        """
        result = self.order_repository.session.execute(
            select(
                OrderDocument.id_order_document,
                OrderDocument.id_order,
                OrderDocument.id_shipping,
                OrderDocument.total_weight
            ).where(
                OrderDocument.id_order_document == id_order_document,
                OrderDocument.type_document == "shipping"
            )
        ).first()
        
        if not result:
            return None
        
        return SimpleNamespace(
            id_order_document=result.id_order_document,
            id_order=result.id_order,
            id_shipping=result.id_shipping,
            total_weight=result.total_weight
        )
    
    def _calculate_document_weights(self, order_documents: List[OrderDocument]) -> Dict[int, float]:
        """
        Calcola il peso per ogni OrderDocument.
        Priorità: Shipping.weight > OrderDocument.total_weight > calcolato da order_details
        
        Args:
            order_documents: Lista di OrderDocument
            
        Returns:
            Dict con id_order_document -> peso
        """
        doc_weight_map = {}
        for order_doc in order_documents:
            doc_weight = None
            # 1. Prova a recuperare il peso dallo Shipping collegato
            if order_doc.id_shipping:
                doc_weight = self.shipping_repository.get_weight(order_doc.id_shipping)
            
            # 2. Fallback: usa total_weight del documento
            if not doc_weight and order_doc.total_weight:
                doc_weight = float(order_doc.total_weight)
            
            # 3. Fallback: calcola dagli order_details
            if not doc_weight:
                doc_details = self.order_detail_repository.get_by_order_document_id(order_doc.id_order_document)
                if doc_details:
                    doc_weight = sum(
                        float(getattr(detail, 'product_weight', 0) or 0.0) * int(getattr(detail, 'product_qty', 1) or 1)
                        for detail in doc_details
                    )
            
            if doc_weight:
                doc_weight_map[order_doc.id_order_document] = doc_weight
        
        return doc_weight_map
    
    def _package_line_item(
        self,
        pkg: Any,
        sequence_number: int,
        fedex_config: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Costruisce un singolo requestedPackageLineItem per MPS (sequenceNumber, weight, dimensions)."""
        weight = float(getattr(pkg, 'weight', None) or (getattr(fedex_config, 'default_weight', None) if fedex_config else None) or 1.0)
        item: Dict[str, Any] = {
            "sequenceNumber": sequence_number,
            "weight": {"units": "KG", "value": round(weight, 2)}
        }
        length = getattr(pkg, 'length', None) or (getattr(fedex_config, 'package_depth', None) if fedex_config else None)
        width = getattr(pkg, 'width', None) or (getattr(fedex_config, 'package_width', None) if fedex_config else None)
        height = getattr(pkg, 'height', None) or (getattr(fedex_config, 'package_height', None) if fedex_config else None)
        if length is not None and width is not None and height is not None:
            item["dimensions"] = {
                "length": int(length),
                "width": int(width),
                "height": int(height),
                "units": "CM"
            }
        return item
    
    async def _validate_fedex_payload(
        self,
        payload: Dict[str, Any],
        order_id: int,
        credentials: Any,
        fedex_config: Any
    ) -> None:
        """Valida il payload FedEx tramite API validate prima della create."""
        await self.fedex_client.validate_shipment(
            payload=payload,
            credentials=credentials,
            fedex_config=fedex_config
        )
    
    async def create_shipment(
        self,
        order_id: int,
        id_shipping: Optional[int] = None,
        id_order_document: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Creazione spedizione FedEx per ordine
        
        Args:
            order_id: ID ordine per creare spedizione
            order_id: ID ordine per creare spedizione
            id_shipping: ID shipping opzionale (per multispedizione)
            id_order_document: ID OrderDocument opzionale (se fornito, crea la label solo per quel documento
                               con payload di spedizione singola)
            
        Returns:
            Dict con dettagli spedizione (awb, tracking_numbers, etc.)
        """
        try:
            # 1. Recupero informazioni Ordine
            order_data = self.order_repository.get_shipment_data(order_id)
            
            # 2. Determina quale shipping usare
            specific_doc = None
            if id_order_document is not None:
                specific_doc = self._get_shipping_document_minimal(id_order_document)
                if not specific_doc:
                    raise NotFoundException("OrderDocument", id_order_document)
                shipping_id_to_use = getattr(specific_doc, "id_shipping", None) or id_shipping or order_data.id_shipping
                if not shipping_id_to_use:
                    raise NotFoundException("Shipping", None, {"id_order_document": id_order_document, "reason": "Spedizione non trovata"})
            else:
                shipping_id_to_use = id_shipping if id_shipping is not None else order_data.id_shipping
            
            # 4. Recupero info di spedizione per poi recuperare id_carrier_api
            shipping_info = self.shipping_repository.get_carrier_info(shipping_id_to_use)
            carrier_api_id = shipping_info.id_carrier_api
            
            # 4.1. Recupero price_tax_incl dalla spedizione per totalCustomsValue
            shipping = self.shipping_repository.get_by_id(shipping_id_to_use)
            shipping_price_tax_incl = float(shipping.price_tax_incl or 0.0) if shipping else 0.0
            
            # 3. Recupero la configurazione FedEx con scope SHIP per creazione spedizioni
            fedex_config = self.fedex_config_repository.get_by_carrier_api_id_and_scope(carrier_api_id, FedexScopeEnum.SHIP)
            if not fedex_config:
                raise NotFoundException("FedexConfiguration", carrier_api_id, {"carrier_api_id": carrier_api_id, "scope": "SHIP"})
            
            # 4. Recupero credenziali FedEx
            credentials = self.carrier_api_repository.get_auth_credentials(carrier_api_id)
            
            # 5. Recupero indirizzo di consegna e paese
            receiver_address = self.address_repository.get_delivery_data(order_data.id_address_delivery)
            receiver_country_iso = self.country_repository.get_iso_code(receiver_address.id_country)
            
            # 6. Recupero dimensioni dei colli e order_details
            # Se id_order_document è fornito: packages e order_details solo del documento; total_customs_value del documento
            # Se id_shipping è fornito (senza id_order_document), recupera TUTTI gli OrderDocument e aggrega tutto
            total_customs_value = None
            if id_order_document is not None:
                # Multishipping: un documento = una spedizione con payload singolo
                packages = self.order_package_repository.get_dimensions_by_order_documents([id_order_document])
                order_details = self.order_detail_repository.get_by_order_document_id(id_order_document)
                # totalCustomsValue limitato al documento
                total_customs_doc = 0.0
                if order_details:
                    for detail in order_details:
                        total_customs_doc += float(getattr(detail, 'total_price_with_tax', 0) or 0.0)
                total_customs_value = total_customs_doc if total_customs_doc > 0 else None
            elif id_shipping is not None:
                # Recupera TUTTI gli OrderDocument di tipo "shipping" per questo ordine (multispedizione)
                order_document_repository = OrderDocumentRepository(self.order_repository.session)
                order_documents = order_document_repository.get_shipping_documents_by_order_id(order_id)
                
                if order_documents:
                    # Recupera packages di TUTTI i documenti
                    id_order_documents = [doc.id_order_document for doc in order_documents]
                    packages = self.order_package_repository.get_dimensions_by_order_documents(id_order_documents)
                    
                    # Recupera order_details di TUTTI i documenti e aggrega
                    all_order_details = []
                    total_customs = 0.0
                    for order_doc in order_documents:
                        doc_details = self.order_detail_repository.get_by_order_document_id(order_doc.id_order_document)
                        if doc_details:
                            all_order_details.extend(doc_details)
                            for detail in doc_details:
                                total_price = float(getattr(detail, 'total_price_with_tax', 0) or 0.0)
                                total_customs += total_price
                    
                    order_details = all_order_details
                    total_customs_value = total_customs if total_customs > 0 else None
                else:
                    order_details = self.order_detail_repository.get_by_order_id(order_id)
                    packages = self.order_package_repository.get_dimensions_by_order(order_id) or []
            else:
                order_details = self.order_detail_repository.get_by_order_id(order_id)
                packages = self.order_package_repository.get_dimensions_by_order(order_id) or []
            
            # 8. Recupero internal_reference dell'ordine
            internal_reference = order_data.internal_reference or str(order_id)
            
            # 9. Costruzione payload FedEx (sempre payload singolo; multishipping = N chiamate, una per documento)
            if id_order_document is not None and (not packages or len(packages) == 0):
                raise ValidationException(
                    "Nessun package per il documento di spedizione",
                    details={"id_order_document": id_order_document}
                )

            # MPS: > 1 collo = una request per collo; primo = master (no masterTrackingId), dal secondo masterTrackingId dalla prima risposta
            total_colli = len(packages)
            if total_colli > 1:
                master_tracking_id = None
                all_pdf_bytes = []
                all_tracking_numbers = []
                #await self._validate_fedex_payload(first_payload, order_id, credentials, fedex_config)
                # Una request per ogni collo
                for sequence_number in range(1, total_colli + 1):
                    pkg = packages[sequence_number - 1]
                    mps_dict = {
                        "oneLabelAtATime": True,
                        "totalPackageCount": total_colli,
                        "requestedPackageLineItems": [self._package_line_item(pkg, sequence_number, fedex_config)]
                    }
                    if sequence_number > 1 and master_tracking_id:
                        mps_dict["masterTrackingId"] = master_tracking_id
                    fedex_payload = self.fedex_mapper.build_shipment_request(
                        order_data=order_data,
                        fedex_config=fedex_config,
                        receiver_address=receiver_address,
                        receiver_country_iso=receiver_country_iso,
                        packages=[pkg],
                        shipping_price_tax_incl=shipping_price_tax_incl,
                        order_details=order_details,
                        total_customs_value=total_customs_value,
                        mps=mps_dict
                    )
                    fedex_response = await self.fedex_client.create_shipment(
                        payload=fedex_payload,
                        credentials=credentials,
                        fedex_config=fedex_config
                    )
                    if sequence_number == 1:
                        out = fedex_response.get("output", {})
                        tx = out.get("transactionShipments", [])
                        if tx:
                            master_tracking_id = tx[0].get("masterTrackingNumber")
                    all_tracking_numbers.extend(self.fedex_mapper.extract_tracking_from_response(fedex_response))
                    urls = self.fedex_mapper.extract_package_documents_urls(fedex_response)
                    if urls:
                        for url in urls:
                            pdf_bytes = await self._download_pdf_from_url(url)
                            if pdf_bytes:
                                all_pdf_bytes.append(pdf_bytes)
                awb = master_tracking_id or (all_tracking_numbers[0] if all_tracking_numbers else None)
                if all_pdf_bytes:
                    merged_pdf = self._merge_pdf_labels(all_pdf_bytes) if len(all_pdf_bytes) > 1 else all_pdf_bytes[0]
                    label_b64 = base64.b64encode(merged_pdf).decode("utf-8")
                else:
                    label_b64 = None
                if awb and label_b64:
                    try:
                        await self._save_documents(awb=awb, label_b64=label_b64, order_id=order_id, carrier_api_id=carrier_api_id)
                    except Exception as e:
                        logger.error(f"Error saving FedEx MPS document for AWB {awb}: {str(e)}", exc_info=True)
                if awb:
                    self.shipping_repository.update_tracking_and_state(shipping_id_to_use, awb, 2)
                return {"awb": awb or "", "tracking_numbers": all_tracking_numbers, "transaction_id": None}
            # Singolo collo: payload classico, una sola request
            fedex_payload = self.fedex_mapper.build_shipment_request(
                order_data=order_data,
                fedex_config=fedex_config,
                receiver_address=receiver_address,
                receiver_country_iso=receiver_country_iso,
                packages=packages,
                shipping_price_tax_incl=shipping_price_tax_incl,
                order_details=order_details,
                total_customs_value=total_customs_value,
                mps=None
            )
            await self._validate_fedex_payload(fedex_payload, order_id, credentials, fedex_config)
            fedex_response = await self.fedex_client.create_shipment(
                payload=fedex_payload,
                credentials=credentials,
                fedex_config=fedex_config
            )
            tracking_numbers = self.fedex_mapper.extract_tracking_from_response(fedex_response)
            output = fedex_response.get("output", {})
            transaction_shipments = output.get("transactionShipments", [])
            master_tracking = transaction_shipments[0].get("masterTrackingNumber") if transaction_shipments else None
            awb = master_tracking or (tracking_numbers[0] if tracking_numbers else None)
            label_b64 = self.fedex_mapper.extract_label_from_response(fedex_response)
            package_document_urls = self.fedex_mapper.extract_package_documents_urls(fedex_response)
            if package_document_urls and not label_b64:
                try:
                    pdf_bytes_list = []
                    for url in package_document_urls:
                        pdf_bytes = await self._download_pdf_from_url(url)
                        if pdf_bytes:
                            pdf_bytes_list.append(pdf_bytes)
                    if pdf_bytes_list:
                        merged_pdf_bytes = self._merge_pdf_labels(pdf_bytes_list) if len(pdf_bytes_list) > 1 else pdf_bytes_list[0]
                        label_b64 = base64.b64encode(merged_pdf_bytes).decode("utf-8")
                except Exception as e:
                    logger.error(f"Error downloading/merging PDFs: {str(e)}", exc_info=True)
            elif not label_b64:
                label_url = self.fedex_mapper.extract_label_url_from_response(fedex_response)
                if label_url:
                    try:
                        label_b64 = await self._download_label_from_url(label_url)
                    except Exception as e:
                        logger.error(f"Error downloading label from URL: {str(e)}")
            if awb and label_b64:
                try:
                    await self._save_documents(awb=awb, label_b64=label_b64, order_id=order_id, carrier_api_id=carrier_api_id)
                except Exception as e:
                    logger.error(f"Error saving FedEx document for AWB {awb}: {str(e)}", exc_info=True)
            elif awb:
                try:
                    await self._save_document_record(awb=awb, order_id=order_id, carrier_api_id=carrier_api_id)
                except Exception as e:
                    logger.error(f"Error saving FedEx document record for AWB {awb}: {str(e)}")
            if awb:
                self.shipping_repository.update_tracking_and_state(shipping_id_to_use, awb, 2)
            return {
                "awb": awb or "",
                "tracking_numbers": tracking_numbers,
                "transaction_id": fedex_response.get("transactionId")
            }
            
        except Exception as e:
            logger.error(f"Error creating FedEx shipment for order {order_id}: {str(e)}")
            raise
    
    async def validate_shipment(self, order_id: int) -> Dict[str, Any]:
        """
        Valida spedizione FedEx prima della creazione
        
        Args:
            order_id: ID ordine per validare spedizione
            
        Returns:
            Dict con risultato validazione
        """
        try:
            # 1. Recupero informazioni Ordine
            order_data = self.order_repository.get_shipment_data(order_id)
            
            # 2. Recupero info di spedizione
            shipping_info = self.shipping_repository.get_carrier_info(order_data.id_shipping)
            carrier_api_id = shipping_info.id_carrier_api
            
            # 3. Recupero la configurazione FedEx con scope SHIP
            fedex_config = self.fedex_config_repository.get_by_carrier_api_id_and_scope(carrier_api_id, FedexScopeEnum.SHIP)
            if not fedex_config:
                raise NotFoundException("FedexConfiguration", carrier_api_id, {"carrier_api_id": carrier_api_id, "scope": "SHIP"})
            
            # 4. Recupero credenziali FedEx
            credentials = self.carrier_api_repository.get_auth_credentials(carrier_api_id)
            
            # 5. Recupero indirizzo di consegna e paese
            receiver_address = self.address_repository.get_delivery_data(order_data.id_address_delivery)
            receiver_country_iso = self.country_repository.get_iso_code(receiver_address.id_country)
            
            # 6. Recupero dimensioni dei colli
            packages = self.order_package_repository.get_dimensions_by_order(order_id)
            
            # 7. Recupero dettagli ordine per commodities
            order_details = self.order_detail_repository.get_by_order_id(order_id)
            
            # 8. Recupero internal_reference dell'ordine
            internal_reference = order_data.internal_reference or str(order_id)
            
            # 9. Recupero price_tax_incl dalla spedizione per totalCustomsValue
            shipping = self.shipping_repository.get_by_id(order_data.id_shipping)
            shipping_price_tax_incl = float(shipping.price_tax_incl or 0.0) if shipping else 0.0
            
            # 9.2. Costruzione FedEx validation payload (sempre payload singolo)
            validation_payload = self.fedex_mapper.build_validate_request(
                order_data=order_data,
                fedex_config=fedex_config,
                receiver_address=receiver_address,
                receiver_country_iso=receiver_country_iso,
                packages=packages or [],
                reference=internal_reference,
                shipping_price_tax_incl=shipping_price_tax_incl,
                order_details=order_details
            )
            
            # 10. Chiama a API FedEx per validazione
            logger.info(f"Validating FedEx shipment for order {order_id}")
            try:
                validation_response = await self.fedex_client.validate_shipment(
                    payload=validation_payload,
                    credentials=credentials,
                    fedex_config=fedex_config
                )
                
                # Check for validation errors/warnings in response
                errors = validation_response.get("errors", [])
                warnings = validation_response.get("warnings", [])
                
                return {
                    "valid": len(errors) == 0,
                    "errors": errors,
                    "warnings": warnings,
                    "transaction_id": validation_response.get("transactionId")
                }
                
            except ValueError as e:
                # Validation failed
                return {
                    "valid": False,
                    "errors": [{"message": str(e)}],
                    "warnings": []
                }
            except Exception as e:
                logger.error(f"Error validating FedEx shipment for order {order_id}: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Error validating FedEx shipment for order {order_id}: {str(e)}")
            raise
    
    async def get_label_file_path(self, awb: str) -> Optional[str]:
        """
        Recupera il percorso del file PDF della label per un AWB
        
        Args:
            awb: Air Waybill number o tracking number FedEx
            
        Returns:
            Percorso del file PDF o None se non trovato
        """
        try:
            # Cerca il documento per AWB
            document_repo = ShipmentDocumentRepository(self.order_repository.session)
            documents = document_repo.get_by_awb(awb)
            
            if documents:
                # Restituisce il percorso del primo documento trovato
                return documents[0].file_path
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving label file path for AWB {awb}: {str(e)}")
            return None
    
    async def cancel_shipment(self, order_id: int) -> Dict[str, Any]:
        """
        Cancella spedizione FedEx per ordine
        
        Args:
            order_id: ID ordine per cancellare spedizione
            
        Returns:
            Dict con risultato cancellazione
        """
        try:
            # 1. Recupero informazioni Ordine
            order_data = self.order_repository.get_shipment_data(order_id)
            # 2. Recupero info di spedizione
            shipping_info = self.shipping_repository.get_carrier_info(order_data.id_shipping)
            carrier_api_id = shipping_info.id_carrier_api
            
            # 3. Recupero tracking number dalla spedizione
            tracking_number = shipping_info.tracking
            if not tracking_number:
                raise BusinessRuleException(
                    f"Tracking non trovato per l'ordine {order_id}",
                    details={"order_id": order_id}
                )
            
            # 4. Recupero la configurazione FedEx con scope SHIP
            fedex_config = self.fedex_config_repository.get_by_carrier_api_id_and_scope(carrier_api_id, FedexScopeEnum.SHIP)
            if not fedex_config:
                raise NotFoundException("FedexConfiguration", carrier_api_id, {"carrier_api_id": carrier_api_id, "scope": "SHIP"})
            
            # 5. Recupero credenziali FedEx
            credentials = self.carrier_api_repository.get_auth_credentials(carrier_api_id)
            
            # 6. Costruzione payload cancellazione
            account_number = str(fedex_config.account_number) if fedex_config.account_number else ""
            cancel_payload = self.fedex_mapper.build_cancel_request(
                tracking_number=tracking_number,
                account_number=account_number,
                deletion_control=None  # FedEx will determine based on shipment type
            )
            
            # 7. Esegui cancellazione
            logger.info(f"Cancelling FedEx shipment for order {order_id} with tracking {tracking_number}")
            try:
                cancel_response = await self.fedex_client.cancel_shipment(
                    payload=cancel_payload,
                    credentials=credentials,
                    fedex_config=fedex_config
                )
                
                # Check response for success
                # FedEx cancel response structure may vary
                success = True
                message = "Shipment cancelled successfully"
                
                # Try to extract message from response
                if "output" in cancel_response:
                    output = cancel_response["output"]
                    alerts = output.get("alerts", [])
                    if alerts:
                        message = alerts[0].get("message", message)
                
                # 8. Aggiorna lo stato della shipping a 11 (Annullato)
                self.shipping_repository.update_shipping_to_cancelled_state(order_data.id_shipping)
                logger.info(f"Updated shipping state to 11 (Annullato) for shipping {order_data.id_shipping}")
                
                transaction_id = cancel_response.get("transactionId")
                
                return {
                    "success": success,
                    "message": message,
                    "transaction_id": transaction_id
                }
                
            except ValueError as e:
                raise BusinessRuleException(
                    f"FedEx cancellation failed: {str(e)}",
                    details={"order_id": order_id, "tracking_number": tracking_number, "error": str(e)}
                )
            except RuntimeError as e:
                raise InfrastructureException(
                    f"FedEx cancellation server error: {str(e)}",
                    details={"order_id": order_id, "tracking_number": tracking_number, "error": str(e)}
                )
                
        except Exception as e:
            logger.error(f"Error cancelling FedEx shipment for order {order_id}: {str(e)}")
            raise
    
    async def get_async_results(
        self,
        job_id: str,
        account_number: str,
        carrier_api_id: int
    ) -> Dict[str, Any]:
        """
        Recupera risultati asincroni di una spedizione FedEx
        
        Args:
            job_id: Job ID dalla creazione asincrona
            account_number: Numero account FedEx
            carrier_api_id: Carrier API ID
            
        Returns:
            Dict con risultati asincroni
        """
        try:
            # 1. Recupero la configurazione FedEx con scope SHIP
            fedex_config = self.fedex_config_repository.get_by_carrier_api_id_and_scope(carrier_api_id, FedexScopeEnum.SHIP)
            if not fedex_config:
                raise NotFoundException("FedexConfiguration", carrier_api_id, {"carrier_api_id": carrier_api_id, "scope": "SHIP"})
            
            # 2. Recupero credenziali FedEx
            credentials = self.carrier_api_repository.get_auth_credentials(carrier_api_id)
            
            # 3. Chiama API per risultati asincroni
            logger.info(f"Getting FedEx async results for job {job_id}")
            try:
                results = await self.fedex_client.get_async_results(
                    job_id=job_id,
                    account_number=account_number,
                    credentials=credentials,
                    fedex_config=fedex_config
                )
                
                return results
                
            except Exception as e:
                logger.error(f"Error getting FedEx async results for job {job_id}: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Error getting FedEx async results: {str(e)}")
            raise
    
    async def _save_documents(
        self,
        awb: str,
        label_b64: str,
        order_id: int,
        carrier_api_id: int
    ) -> Dict[str, Any]:
        """
        Salva documenti FedEx (PDF) sul filesystem e nel database
        
        Args:
            awb: Numero tracking FedEx
            label_b64: Base64 encoded PDF label
            order_id: Order ID
            carrier_api_id: Carrier API ID
            
        Returns:
            Dict con metadati documento salvato
        """
        try:
            # Cleanup documenti esistenti
            self._cleanup_old_documents(order_id)
            
            # Decodifica base64
            try:
                content_bytes = base64.b64decode(label_b64)
            except Exception as e:
                logger.error(f"Error decoding FedEx label base64: {str(e)}")
                return {}
            
            # Genero file path con struttura anno/mese
            now = datetime.now()
            year = now.year
            month = now.month
            
            # Creazione directory: /media/shipments/{year}/{month}/{id_order}/
            base_dir = Path("media") / "shipments" / str(year) / str(month).zfill(2) / str(order_id)
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # Genero nome file con AWB incluso
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            filename = f"label_{awb}_{timestamp}.pdf"
            file_path = base_dir / filename
            
            # Salvo file
            with open(file_path, "wb") as f:
                f.write(content_bytes)
            
            # Calcolo metadati file
            file_size = len(content_bytes)
            sha256_hash = hashlib.sha256(content_bytes).hexdigest()
            
            # Salvo a database
            document = ShipmentDocument(
                awb=awb,
                order_id=order_id,
                carrier_api_id=carrier_api_id,
                type_code="label",
                file_path=str(file_path),
                mime_type="application/pdf",
                sha256_hash=sha256_hash,
                size_bytes=file_size,
                created_at=now,
                expires_at=now + timedelta(days=365)  # 1 year TTL
            )
            
            # Aggiungo a sessione e salvo
            self.order_repository.session.add(document)
            self.order_repository.session.commit()
            
            logger.info(f"Saved FedEx document label for AWB {awb}: {file_path}")
            
            return {
                "type_code": "label",
                "file_path": str(file_path),
                "size_bytes": file_size,
                "sha256_hash": sha256_hash,
                "order_id": order_id,
                "carrier_api_id": carrier_api_id
            }
            
        except Exception as e:
            logger.error(f"Error saving FedEx document for AWB {awb}: {str(e)}")
            raise
    
    async def _save_document_record(
        self,
        awb: str,
        order_id: int,
        carrier_api_id: int
    ) -> Dict[str, Any]:
        """
        Salva solo il record del documento nel database senza file (quando label non disponibile)
        
        Args:
            awb: Numero tracking FedEx
            order_id: Order ID
            carrier_api_id: Carrier API ID
            
        Returns:
            Dict con metadati documento salvato
        """
        try:
            now = datetime.now()
            
            # Genero un file_path placeholder anche se non c'è il file
            # Questo è necessario perché file_path è NOT NULL nel database
            file_path_placeholder = f"media/shipments/placeholder/{order_id}/label_{awb}_no_file.pdf"
            
            # Salvo a database con file_path placeholder
            document = ShipmentDocument(
                awb=awb,
                order_id=order_id,
                carrier_api_id=carrier_api_id,
                type_code="label",
                file_path=file_path_placeholder,
                mime_type="application/pdf",
                sha256_hash="",  # No hash available
                size_bytes=0,
                created_at=now,
                expires_at=now + timedelta(days=365)  # 1 year TTL
            )
            
            # Aggiungo a sessione e salvo
            self.order_repository.session.add(document)
            self.order_repository.session.commit()
            
            logger.info(f"Saved FedEx document record (no file) for AWB {awb}")
            
            return {
                "type_code": "label",
                "awb": awb,
                "order_id": order_id,
                "carrier_api_id": carrier_api_id
            }
            
        except Exception as e:
            logger.error(f"Error saving FedEx document record for AWB {awb}: {str(e)}")
            raise
    
    async def _download_pdf_from_url(self, url: str) -> Optional[bytes]:
        """
        Download PDF from URL and return as bytes
        
        Args:
            url: URL of the PDF
            
        Returns:
            PDF bytes or None if download fails
        """
        try:
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Get PDF content as bytes
                pdf_bytes = response.content
                
                # Check if it's actually a PDF
                if not pdf_bytes.startswith(b'%PDF'):
                    logger.warning(f"Downloaded content from {url} doesn't appear to be a PDF")
                    return None
                
                return pdf_bytes
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading PDF from URL {url}: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.TimeoutException:
            logger.error(f"Timeout downloading PDF from URL {url}")
            return None
        except Exception as e:
            logger.error(f"Error downloading PDF from URL {url}: {str(e)}")
            return None
    
    async def _download_label_from_url(self, url: str) -> Optional[str]:
        """
        Download label PDF from URL and convert to base64 (legacy method for backward compatibility)
        
        Args:
            url: URL of the label PDF
            
        Returns:
            Base64 encoded label string or None if download fails
        """
        pdf_bytes = await self._download_pdf_from_url(url)
        if pdf_bytes:
            return base64.b64encode(pdf_bytes).decode('utf-8')
        return None
    
    def _merge_pdf_labels(self, pdf_bytes_list: List[bytes]) -> bytes:
        """
        Unisce multiple label PDF in un unico PDF
        
        Args:
            pdf_bytes_list: Lista di bytes di PDF da unire
            
        Returns:
            bytes del PDF unito
            
        Raises:
            ValueError: Se un PDF non è valido o l'unione fallisce
        """
        if not pdf_bytes_list:
            raise ValueError("Cannot merge empty list of PDFs")
        
        if len(pdf_bytes_list) == 1:
            return pdf_bytes_list[0]
        
        try:
            writer = PdfWriter()
            
            for pdf_bytes in pdf_bytes_list:
                try:
                    pdf_reader = PdfReader(BytesIO(pdf_bytes))
                    # Aggiungi tutte le pagine del PDF al writer
                    for page in pdf_reader.pages:
                        writer.add_page(page)
                except Exception as e:
                    raise ValueError(f"Invalid PDF in merge operation: {str(e)}")
            
            # Crea il PDF unito
            output_buffer = BytesIO()
            writer.write(output_buffer)
            output_buffer.seek(0)
            
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error merging PDF labels: {str(e)}")
            raise ValueError(f"Failed to merge PDF labels: {str(e)}")
    
    def _cleanup_old_documents(self, order_id: int) -> None:
        """
        Elimina documenti esistenti per un ordine prima di salvare nuovi documenti
        
        Args:
            order_id: ID dell'ordine
        """
        try:
            # Recupera tutti i documenti esistenti per l'ordine
            document_repo = ShipmentDocumentRepository(self.order_repository.session)
            existing_documents = document_repo.get_by_order_id(order_id)
            
            if not existing_documents:
                return
            
            # Raggruppa documenti per cartella per eliminare una volta sola
            folders_to_delete = set()
            
            for doc in existing_documents:
                if doc.file_path:
                    try:
                        # Estrai la cartella dell'ordine dal file_path
                        file_path = Path(doc.file_path)
                        order_folder = file_path.parent  # cartella {id_order}
                        folders_to_delete.add(str(order_folder))
                        
                        # Elimina il record dal database
                        document_repo.delete_by_id(doc.id)
                        
                    except Exception as e:
                        logger.warning(f"Errore nel processare il documento {doc.id}: {str(e)}")
            
            # Elimina le cartelle fisiche
            for folder_path in folders_to_delete:
                try:
                    if Path(folder_path).exists():
                        shutil.rmtree(folder_path)
                except Exception as e:
                    logger.error(f"Errore nell'eliminare la cartella {folder_path}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Errore durante la pulizia per l'ordine {order_id}: {str(e)}")

