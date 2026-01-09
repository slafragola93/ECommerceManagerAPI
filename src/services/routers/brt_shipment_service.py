import os
import hashlib
import base64
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

from src.core.settings import get_cache_settings
from src.core.exceptions import NotFoundException, BusinessRuleException, InfrastructureException
from src.services.interfaces.brt_shipment_service_interface import IBrtShipmentService
from src.repository.interfaces.order_repository_interface import IOrderRepository
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.repository.interfaces.brt_configuration_repository_interface import IBrtConfigurationRepository
from src.repository.interfaces.address_repository_interface import IAddressRepository
from src.repository.interfaces.country_repository_interface import ICountryRepository
from src.repository.interfaces.order_package_repository_interface import IOrderPackageRepository
from src.services.ecommerce.shipments.brt_client import BrtClient
from src.services.ecommerce.shipments.brt_mapper import BrtMapper
from src.models.shipment_document import ShipmentDocument

logger = logging.getLogger(__name__)


class BrtShipmentService(IBrtShipmentService):
    """BRT Shipment service for creating shipments and managing documents"""
    
    def __init__(
        self,
        order_repository: IOrderRepository,
        shipping_repository: IShippingRepository,
        carrier_api_repository: IApiCarrierRepository,
        brt_config_repository: IBrtConfigurationRepository,
        address_repository: IAddressRepository,
        country_repository: ICountryRepository,
        order_package_repository: IOrderPackageRepository,
        brt_client: BrtClient,
        brt_mapper: BrtMapper
    ):
        self.order_repository = order_repository
        self.shipping_repository = shipping_repository
        self.carrier_api_repository = carrier_api_repository
        self.brt_config_repository = brt_config_repository
        self.address_repository = address_repository
        self.country_repository = country_repository
        self.order_package_repository = order_package_repository
        self.brt_client = brt_client
        self.brt_mapper = brt_mapper
        self.settings = get_cache_settings()
    
    async def create_shipment(self, order_id: int) -> Dict[str, Any]:
        """
        Creazione spedizione BRT per ordine
        
        Args:
            order_id: ID ordine per creare spedizione
            
        Returns:
            Dict con dettagli spedizione (awb)
        """
        # 1. Recupero informazioni Ordine
        order_data = self.order_repository.get_shipment_data(order_id)
        
        # 2. Recupero info di spedizione per poi recuperare id_carrier_api
        shipping_info = self.shipping_repository.get_carrier_info(order_data.id_shipping)
        carrier_api_id = shipping_info.id_carrier_api
        
        # 2.1. Recupero shipping_message dalla spedizione
        shipping_message = self.shipping_repository.get_message_shipping(order_data.id_shipping) or ""
        
        # 3. Recupero la configurazione BRT
        brt_config = self.brt_config_repository.get_by_carrier_api_id(carrier_api_id)
        if not brt_config:
            raise NotFoundException("BrtConfiguration", carrier_api_id, {"carrier_api_id": carrier_api_id})
        
        # 4. Recupero credenziali (per consistenza con DHL, ma BRT usa brt_config)
        credentials = self.carrier_api_repository.get_auth_credentials(carrier_api_id)
        
        # 5. Recupero indirizzo di consegna
        receiver_address = self.address_repository.get_delivery_data(order_data.id_address_delivery)
        # 6. Recupero codice ISO paese destinatario
        receiver_country_iso = self.country_repository.get_iso_code(receiver_address.id_country)
        
        # 6.1. Validazione: BRT supporta solo spedizioni in Italia
        if receiver_country_iso.upper() != "IT":
            raise BusinessRuleException(
                f"BRT supports only shipments to Italy. Destination country: {receiver_country_iso}",
                details={
                    "destination_country_iso": receiver_country_iso,
                    "supported_country": "IT"
                }
            )
        # 7. Recupero dimensioni dei colli
        packages = self.order_package_repository.get_dimensions_by_order(order_id)
        
        # 7.1. Conta il numero di order_package collegate all'ordine
        number_of_parcels = len(packages) if packages else 0
        
        # 8. Recupero internal_reference dell'ordine
        internal_reference = order_data.internal_reference or str(order_id)
        
        # 9. STEP 1: Routing per normalizzare indirizzo
        logger.info(f"BRT Routing for order {order_id}")
        routing_payload = self.brt_mapper.build_routing_request(
            brt_config=brt_config,
            receiver_address=receiver_address,
            packages=packages,
            receiver_country_iso=receiver_country_iso,
            number_of_parcels=number_of_parcels
        )
        
        routing_response = await self.brt_client.routing(
            payload=routing_payload,
            credentials=credentials,
            brt_config=brt_config
        )
        # Extract normalized address from routing response
        normalized_address = routing_response.get("routingData") or {}
        
        # 10. STEP 2: Create shipment
        logger.info(f"Creating BRT shipment for order {order_id}")
        create_payload = self.brt_mapper.build_create_request(
            brt_config=brt_config,
            receiver_address=receiver_address,
            packages=packages,
            reference=internal_reference,
            receiver_country_iso=receiver_country_iso,
            normalized_address=normalized_address,
            number_of_parcels=number_of_parcels,
            shipping_message=shipping_message,
            order_id=order_id
        )
        
        create_response = await self.brt_client.create_shipment(
            payload=create_payload,
            credentials=credentials,
            brt_config=brt_config
        )
        
        # 11. Estrazione tracking e label
        tracking = self.brt_mapper.extract_tracking_from_response(create_response)
        logger.info(f"Extracted tracking for order {order_id}: {tracking}")
        
        # Estrai tutte le label dalla risposta
        all_labels_b64 = self.brt_mapper.extract_all_labels_from_response(create_response)
        
        # Se ci sono multiple label e numberOfParcels > 1, uniscile
        if number_of_parcels > 1 and len(all_labels_b64) > 1:
            # Decodifica tutte le label da base64 a bytes
            pdf_bytes_list = []
            for label_b64 in all_labels_b64:
                try:
                    pdf_bytes = base64.b64decode(label_b64)
                    pdf_bytes_list.append(pdf_bytes)
                except Exception as e:
                    logger.error(f"Error decoding label base64: {str(e)}")
                    raise ValueError(f"Invalid base64 PDF label: {str(e)}")
            
            # Unisci i PDF
            merged_pdf_bytes = self._merge_pdf_labels(pdf_bytes_list)
            
            # Codifica il risultato in base64
            label_b64 = base64.b64encode(merged_pdf_bytes).decode('utf-8')
            logger.info(f"Merged {len(all_labels_b64)} labels into single PDF for order {order_id}")
        elif all_labels_b64:
            # Usa la prima label se c'è solo una o numberOfParcels == 1
            label_b64 = all_labels_b64[0]
        else:
            label_b64 = None
        
        if not label_b64:
            # Try to get label from confirm response if autoconfirm is enabled
            # For now, we'll check if autoconfirm is needed
            # Note: BRT config doesn't have autoconfirm field yet, so we skip for now
            pass
        

        
        # 13. Salva PDF label
        if label_b64:
            await self._save_documents(
                awb=tracking or f"BRT_{order_id}",
                label_b64=label_b64,
                order_id=order_id,
                carrier_api_id=carrier_api_id
            )
            
        # 13. Aggiornamento tracking e stato (2 = Presa In Carico)
        if tracking:
            self.shipping_repository.update_tracking_and_state(order_data.id_shipping, tracking, 2)
        
        return {
            "awb": tracking or ""
        }
    
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
        try:
            from pypdf import PdfWriter, PdfReader
            from io import BytesIO
        except ImportError:
            raise ImportError("pypdf library is required. Install with: pip install pypdf")
        
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
            
    
    async def _save_documents(
        self,
        awb: str,
        label_b64: str,
        order_id: int,
        carrier_api_id: int
    ) -> Dict[str, Any]:
        """
        Salva documenti BRT (PDF) sul filesystem e nel database
        
        Args:
            awb: Numero tracking BRT
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
                logger.error(f"Error decoding BRT label base64: {str(e)}")
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
            
            logger.info(f"Saved BRT document label for AWB {awb}: {file_path}")
            
            return {
                "type_code": "label",
                "file_path": str(file_path),
                "size_bytes": file_size,
                "sha256_hash": sha256_hash,
                "order_id": order_id,
                "carrier_api_id": carrier_api_id
            }
            
        except Exception as e:
            logger.error(f"Error saving BRT document for AWB {awb}: {str(e)}")
            raise
    
    def _cleanup_old_documents(self, order_id: int) -> None:
        """
        Elimina documenti esistenti per un ordine prima di salvare nuovi documenti
        
        Args:
            order_id: ID dell'ordine
        """
        try:
            from src.repository.shipment_document_repository import ShipmentDocumentRepository
            import shutil
            from pathlib import Path
            
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
            # Non sollevo eccezione per non bloccare la creazione spedizione
    
    async def get_label_file_path(self, awb: str) -> Optional[str]:
        """
        Recupera il percorso del file PDF della label per un AWB
        
        Args:
            awb: Air Waybill number o tracking number BRT
            
        Returns:
            Percorso del file PDF o None se non trovato
        """
        try:
            from src.repository.shipment_document_repository import ShipmentDocumentRepository
            
            # Cerca il documento per AWB
            document_repo = ShipmentDocumentRepository(self.order_repository.session)
            documents = document_repo.get_by_awb(awb)
            
            if not documents:
                logger.warning(f"Nessun documento trovato per AWB: {awb}")
                return None
            
            # Cerca il documento di tipo "label"
            for doc in documents:
                if doc.type_code in ["label", "LABEL"] and doc.file_path:
                    return doc.file_path
            
            # Se non trova "label", prova con qualsiasi documento PDF
            for doc in documents:
                if doc.file_path and doc.file_path.endswith('.pdf'):
                    return doc.file_path
            
            logger.warning(f"Nessun documento label trovato per AWB: {awb}")
            return None
            
        except Exception as e:
            logger.error(f"Errore nel recuperare il percorso del file per AWB {awb}: {str(e)}")
            return None
    
    async def cancel_shipment(self, order_id: int) -> Dict[str, Any]:
        """
        Cancella una spedizione BRT per ordine
        
        Args:
            order_id: ID ordine per cancellare spedizione
            
        Returns:
            Dict con risultato cancellazione
        """
        # 1. Recupero informazioni Ordine
        order_data = self.order_repository.get_shipment_data(order_id)
        
        # 2. Recupero info di spedizione per poi recuperare id_carrier_api
        shipping_info = self.shipping_repository.get_carrier_info(order_data.id_shipping)
        carrier_api_id = shipping_info.id_carrier_api
        
        # 3. Recupero la configurazione BRT
        brt_config = self.brt_config_repository.get_by_carrier_api_id(carrier_api_id)
        if not brt_config:
            raise NotFoundException("BrtConfiguration", carrier_api_id, {"carrier_api_id": carrier_api_id})
        
        # 4. Recupero credenziali
        credentials = self.carrier_api_repository.get_auth_credentials(carrier_api_id)
        
        # 5. Recupero internal_reference dell'ordine per generare i riferimenti
        internal_reference = order_data.internal_reference or str(order_id)
        
        # 6. Genera numeric e alphanumeric reference (stessa logica della creazione)
        # Usa order_id come fallback invece di timestamp per garantire consistenza
        try:
            numeric_ref = int(internal_reference) if internal_reference and internal_reference.isdigit() else None
        except (ValueError, AttributeError):
            numeric_ref = None
        
        if numeric_ref is None:
            # Use order_id as fallback for consistency with creation
            numeric_ref = order_id
        
        alphanumeric_ref = internal_reference or str(numeric_ref)
        
        # 7. Costruisci payload di cancellazione
        delete_payload = self.brt_mapper.build_delete_request(
            brt_config=brt_config,
            numeric_reference=numeric_ref,
            alphanumeric_reference=alphanumeric_ref
        )
        
        # 8. Esegui cancellazione
        logger.info(f"Cancelling BRT shipment for order {order_id}")
        delete_response = await self.brt_client.cancel_shipment(
            payload=delete_payload,
            credentials=credentials,
            brt_config=brt_config
        )
        
        # 9. Se arriviamo qui, la cancellazione è riuscita
        # _check_brt_response_errors() nel client ha già gestito tutti gli errori
        # Estrai informazioni dalla risposta per il risultato
        delete_result = delete_response.get("deleteResponse", {})
        execution_message = delete_result.get("executionMessage", {})
        code = execution_message.get("code", 0)
        severity = execution_message.get("severity", "SUCCESS")
        message = execution_message.get("message", "Shipment cancelled successfully")
        
        # 10. Aggiorna lo stato della shipping a 11 (Annullato)
        self.shipping_repository.update_shipping_to_cancelled_state(order_data.id_shipping)
        
        logger.info(f"BRT shipment cancelled successfully for order {order_id}. Code: {code}, Message: {message}")
        
        return {
            "success": True,
            "code": code,
            "message": message,
            "severity": severity
        }

