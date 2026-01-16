import os
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
import httpx
from sqlalchemy.engine import Row

from src.core.settings import get_cache_settings
from src.core.exceptions import NotFoundException, BusinessRuleException, InfrastructureException, ValidationException
from src.services.interfaces.fedex_shipment_service_interface import IFedexShipmentService
from src.repository.interfaces.order_repository_interface import IOrderRepository
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.repository.interfaces.fedex_configuration_repository_interface import IFedexConfigurationRepository
from src.repository.interfaces.address_repository_interface import IAddressRepository
from src.repository.interfaces.country_repository_interface import ICountryRepository
from src.repository.interfaces.order_package_repository_interface import IOrderPackageRepository
from src.repository.interfaces.order_detail_repository_interface import IOrderDetailRepository
from src.services.ecommerce.shipments.fedex_client import FedexClient
from src.services.ecommerce.shipments.fedex_mapper import FedexMapper
from src.models.shipment_document import ShipmentDocument
from src.models.fedex_configuration import FedexScopeEnum, FedexConfiguration

logger = logging.getLogger(__name__)


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
    
    async def create_shipment(self, order_id: int, id_shipping: Optional[int] = None) -> Dict[str, Any]:
        """
        Creazione spedizione FedEx per ordine
        
        Args:
            order_id: ID ordine per creare spedizione
            
        Returns:
            Dict con dettagli spedizione (awb, tracking_numbers, etc.)
        """
        try:
            # 1. Recupero informazioni Ordine
            order_data = self.order_repository.get_shipment_data(order_id)
            
            # 2. Determina quale shipping usare: se id_shipping è fornito, usalo; altrimenti usa quello dell'Order
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
            
            # 6. Recupero dimensioni dei colli
            packages = self.order_package_repository.get_dimensions_by_order(order_id)
            
            # 7. Recupero dettagli ordine per commodities
            order_details = self.order_detail_repository.get_by_order_id(order_id)
            
            # 8. Recupero internal_reference dell'ordine
            internal_reference = order_data.internal_reference or str(order_id)
            
            # 9. Controllo se è MPS (Multiple-Piece Shipping)
            package_count = len(packages) if packages else 0
            is_mps = package_count > 1
            
            if is_mps:
                # MPS Mode: creazione sequenziale "One label at a time"
                return await self._create_mps_shipment(
                    order_id=order_id,
                    order_data=order_data,
                    fedex_config=fedex_config,
                    receiver_address=receiver_address,
                    receiver_country_iso=receiver_country_iso,
                    packages=packages,
                    order_details=order_details,
                    internal_reference=internal_reference,
                    shipping_price_tax_incl=shipping_price_tax_incl,
                    credentials=credentials,
                    carrier_api_id=carrier_api_id
                )
            else:
                # Single package mode: comportamento attuale
                # 9. Costruzione FedEx payload
                fedex_payload = self.fedex_mapper.build_shipment_request(
                    order_data=order_data,
                    fedex_config=fedex_config,
                    receiver_address=receiver_address,
                    receiver_country_iso=receiver_country_iso,
                    packages=packages,
                    reference=internal_reference,
                    shipping_price_tax_incl=shipping_price_tax_incl,
                    order_details=order_details
                )
                
                # 9.1. Validazione payload prima della creazione
                logger.info(f"Validating FedEx shipment payload for order {order_id}")
                try:
                    validation_response = await self.fedex_client.validate_shipment(
                        payload=fedex_payload,
                        credentials=credentials,
                        fedex_config=fedex_config
                    )
                    # Se la validazione passa (200 OK), non ci sono eccezioni
                    
                    # Controlla se ci sono errori o warnings nella risposta (anche se status 200)
                    errors = validation_response.get("errors", [])
                    warnings = validation_response.get("warnings", [])
                    
                    if errors:
                        # Anche con status 200, se ci sono errori nella risposta, fallisce
                        error_messages = [f"{e.get('code', 'UNKNOWN')}: {e.get('message', 'Unknown error')}" for e in errors]
                        combined_errors = " | ".join(error_messages)
                        raise ValidationException(
                            f"FedEx validation failed: {combined_errors}",
                            details={
                                "order_id": order_id,
                                "errors": errors,
                                "warnings": warnings,
                                "transaction_id": validation_response.get("transactionId")
                            }
                        )
                    
                    if warnings:
                        logger.warning(f"FedEx validation warnings for order {order_id}: {warnings}")
                        
                except ValueError as e:
                    # Handle FedEx client validation errors (400, 401, 403, 404, 422)
                    error_str = str(e)
                    logger.error(f"FedEx Validation Error for order {order_id}: {error_str}")
                    
                    # Check error type for more specific handling
                    if "401" in error_str or "NOT.AUTHORIZED.ERROR" in error_str:
                        raise ValidationException(
                            f"FedEx authentication error during validation: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "authentication"}
                        )
                    elif "403" in error_str or "FORBIDDEN.ERROR" in error_str:
                        raise ValidationException(
                            f"FedEx access denied during validation: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "forbidden"}
                        )
                    elif "404" in error_str or "NOT.FOUND.ERROR" in error_str:
                        raise ValidationException(
                            f"FedEx resource not found during validation: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "not_found"}
                        )
                    else:
                        # Validation errors (400, 422)
                        raise ValidationException(
                            f"FedEx validation error: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "validation"}
                        )
                except RuntimeError as e:
                    # Handle FedEx server errors during validation (500, 503)
                    error_str = str(e)
                    logger.error(f"FedEx Server Error during validation for order {order_id}: {error_str}")
                    
                    if "503" in error_str or "SERVICE.UNAVAILABLE.ERROR" in error_str:
                        raise InfrastructureException(
                            f"FedEx service unavailable during validation: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "service_unavailable"}
                        )
                    else:
                        raise InfrastructureException(
                            f"FedEx server error during validation: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "server_error"}
                        )
                except Exception as e:
                    # Handle other validation errors
                    error_str = str(e)
                    logger.error(f"FedEx validation error for order {order_id}: {error_str}")
                    raise ValidationException(
                        f"FedEx validation failed: {error_str}",
                        details={"order_id": order_id, "error": error_str, "type": "unknown"}
                    )
                
                # 10. Chiama a API FedEx per creare la spedizione (solo se validazione OK)
                logger.info(f"Creating FedEx shipment for order {order_id} (validation passed)")
                try:
                    fedex_response = await self.fedex_client.create_shipment(
                        payload=fedex_payload,
                        credentials=credentials,
                        fedex_config=fedex_config
                    )
                except ValueError as e:
                    # Handle FedEx client errors (400, 401, 403, 404, 422)
                    error_str = str(e)
                    logger.error(f"FedEx Client Error for order {order_id}: {error_str}")
                    
                    # Check error type for more specific handling
                    if "401" in error_str or "NOT.AUTHORIZED.ERROR" in error_str:
                        # Authentication/Authorization error
                        raise ValidationException(
                            f"FedEx authentication error: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "authentication"}
                        )
                    elif "403" in error_str or "FORBIDDEN.ERROR" in error_str:
                        # Forbidden - permissions issue
                        raise ValidationException(
                            f"FedEx access denied: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "forbidden"}
                        )
                    elif "404" in error_str or "NOT.FOUND.ERROR" in error_str:
                        # Resource not found
                        raise ValidationException(
                            f"FedEx resource not found: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "not_found"}
                        )
                    else:
                        # Validation errors (400, 422)
                        raise ValidationException(
                            f"FedEx validation error: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "validation"}
                        )
                except RuntimeError as e:
                    # Handle FedEx server errors (500, 503)
                    error_str = str(e)
                    logger.error(f"FedEx Server Error for order {order_id}: {error_str}")
                    
                    # Check if it's a service unavailable error
                    if "503" in error_str or "SERVICE.UNAVAILABLE.ERROR" in error_str:
                        raise InfrastructureException(
                            f"FedEx service unavailable: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "service_unavailable"}
                        )
                    else:
                        # Internal server error (500)
                        raise InfrastructureException(
                            f"FedEx server error: {error_str}",
                            details={"order_id": order_id, "error": error_str, "type": "server_error"}
                        )
                except Exception as e:
                    # Handle other FedEx API errors
                    error_str = str(e)
                    logger.error(f"FedEx API Error for order {order_id}: {error_str}")
                    raise InfrastructureException(
                        f"FedEx API error: {error_str}",
                        details={"order_id": order_id, "error": error_str, "type": "unknown"}
                    )
            
            # 11. Estrazione tracking numbers e label
            tracking_numbers = self.fedex_mapper.extract_tracking_from_response(fedex_response)
            master_tracking = None
            
            # Get master tracking number
            output = fedex_response.get("output", {})
            transaction_shipments = output.get("transactionShipments", [])
            if transaction_shipments:
                master_tracking = transaction_shipments[0].get("masterTrackingNumber")
            
            # Use master tracking as primary AWB, fallback to first tracking number
            awb = master_tracking or (tracking_numbers[0] if tracking_numbers else None)
            
            # Extract label - try both base64 content and packageDocuments URLs
            label_b64 = self.fedex_mapper.extract_label_from_response(fedex_response)
            package_document_urls = self.fedex_mapper.extract_package_documents_urls(fedex_response)
            
            # If we have packageDocuments URLs, download and merge all PDFs
            if package_document_urls and not label_b64:
                try:
                    # Download all PDFs from URLs
                    pdf_bytes_list = []
                    for url in package_document_urls:
                        pdf_bytes = await self._download_pdf_from_url(url)
                        if pdf_bytes:
                            pdf_bytes_list.append(pdf_bytes)
                            logger.debug(f"Downloaded PDF from {url}, size: {len(pdf_bytes)} bytes")
                    
                    if pdf_bytes_list:
                        # Merge all PDFs into one
                        if len(pdf_bytes_list) > 1:
                            logger.info(f"Merging {len(pdf_bytes_list)} PDFs into one for AWB {awb}")
                            merged_pdf_bytes = self._merge_pdf_labels(pdf_bytes_list)
                        else:
                            merged_pdf_bytes = pdf_bytes_list[0]
                        
                        # Convert merged PDF to base64
                        label_b64 = base64.b64encode(merged_pdf_bytes).decode('utf-8')
                        logger.info(f"Successfully downloaded and merged {len(pdf_bytes_list)} PDF(s) for AWB {awb}, total size: {len(merged_pdf_bytes)} bytes")
                    else:
                        logger.warning(f"Failed to download any PDFs from packageDocuments URLs for AWB {awb}")
                        label_b64 = None
                except Exception as e:
                    logger.error(f"Error downloading/merging PDFs from packageDocuments URLs: {str(e)}", exc_info=True)
                    label_b64 = None
            # Fallback: try single URL (backward compatibility)
            elif not label_b64:
                label_url = self.fedex_mapper.extract_label_url_from_response(fedex_response)
                if label_url:
                    logger.info(f"Downloading label from single URL for AWB {awb}")
                    try:
                        label_b64 = await self._download_label_from_url(label_url)
                        if label_b64:
                            logger.info(f"Successfully downloaded label from URL for AWB {awb}")
                        else:
                            logger.warning(f"Failed to download label from URL for AWB {awb}")
                    except Exception as e:
                        logger.error(f"Error downloading label from URL {label_url}: {str(e)}")
                        label_b64 = None
            
            logger.info(f"FedEx label extracted: {label_b64 is not None}, AWB: {awb}")
            
            # 12. Salva PDF label e documenti
            if awb:
                if label_b64:
                    try:
                        result = await self._save_documents(
                            awb=awb,
                            label_b64=label_b64,
                            order_id=order_id,
                            carrier_api_id=carrier_api_id
                        )
                        if result:
                            logger.info(f"FedEx document saved successfully for AWB {awb}, SHA256: {result.get('sha256_hash', 'N/A')}")
                        else:
                            logger.warning(f"FedEx document save returned empty result for AWB {awb}")
                    except Exception as e:
                        logger.error(f"Error saving FedEx document for AWB {awb}: {str(e)}", exc_info=True)
                        # Continue even if document save fails
                else:
                    logger.warning(f"No label found in FedEx response for AWB {awb}, saving document without label")
                    # Save document record even without label (for tracking purposes)
                    try:
                        await self._save_document_record(
                            awb=awb,
                            order_id=order_id,
                            carrier_api_id=carrier_api_id
                        )
                        logger.info(f"FedEx document record saved successfully for AWB {awb}")
                    except Exception as e:
                        logger.error(f"Error saving FedEx document record for AWB {awb}: {str(e)}")
                        # Continue even if document record save fails
            
            # 12. Aggiornamento tracking e stato (2 = Tracking Assegnato)
            if awb:
                try:
                    self.shipping_repository.update_tracking_and_state(shipping_id_to_use, awb, 2)
                except Exception:
                    # fallback: almeno salva il tracking
                    self.shipping_repository.update_tracking(order_data.id_shipping, awb)
            
            # Get transaction ID
            transaction_id = fedex_response.get("transactionId")
            
            return {
                "awb": awb or "",
                "tracking_numbers": tracking_numbers,
                "master_tracking_number": master_tracking,
                "transaction_id": transaction_id
            }
            
        except Exception as e:
            logger.error(f"Error creating FedEx shipment for order {order_id}: {str(e)}")
            raise
    
    async def _create_mps_shipment(
        self,
        order_id: int,
        order_data: Row,
        fedex_config: FedexConfiguration,
        receiver_address: Row,
        receiver_country_iso: str,
        packages: List[Row],
        order_details: Optional[List],
        internal_reference: str,
        shipping_price_tax_incl: float,
        credentials: Row,
        carrier_api_id: int
    ) -> Dict[str, Any]:
        """
        Crea spedizione FedEx MPS (Multiple-Piece Shipping) in modalità "One label at a time"
        
        Args:
            order_id: ID ordine
            order_data: Order row con dati spedizione
            fedex_config: Configurazione FedEx
            receiver_address: Indirizzo destinatario
            receiver_country_iso: Codice ISO paese destinatario
            packages: Lista di package rows
            order_details: Dettagli ordine per commodities
            internal_reference: Riferimento interno ordine
            shipping_price_tax_incl: Prezzo spedizione con IVA
            credentials: Credenziali FedEx
            carrier_api_id: ID carrier API
            
        Returns:
            Dict con dettagli spedizione (awb, tracking_numbers, etc.)
        """
        total_package_count = len(packages)
        master_tracking = None
        all_tracking_numbers = []
        all_pdf_bytes = []
        master_awb = None
        
        # Calcola il peso totale di tutti i colli
        total_weight_all_packages = sum(
            float(getattr(pkg, 'weight', None) or fedex_config.default_weight or 1.0)
            for pkg in packages
        )
        
        # Recupera il peso shipping (order_data.total_weight) - questo è il peso corretto per le commodities
        shipping_total_weight = float(getattr(order_data, 'total_weight', None) or 0.0)
        if shipping_total_weight <= 0:
            # Fallback: usa il peso totale dei colli se shipping weight non disponibile
            shipping_total_weight = total_weight_all_packages
        
        # Validazione solo del master (primo collo) prima di iniziare
        logger.info(f"Validating FedEx MPS master piece for order {order_id}")
        master_package = packages[0]
        master_validation_payload = self.fedex_mapper.build_mps_shipment_request(
            order_data=order_data,
            fedex_config=fedex_config,
            receiver_address=receiver_address,
            receiver_country_iso=receiver_country_iso,
            package=master_package,
            sequence_number=1,
            total_package_count=total_package_count,
            master_tracking_id=None,  # Master non ha masterTrackingId
            reference=internal_reference,
            shipping_price_tax_incl=shipping_price_tax_incl,
            order_details=order_details,
            total_weight_all_packages=total_weight_all_packages,
            shipping_total_weight=shipping_total_weight
        )
        
        try:
            validation_response = await self.fedex_client.validate_shipment(
                payload=master_validation_payload,
                credentials=credentials,
                fedex_config=fedex_config
            )
            
            errors = validation_response.get("errors", [])
            warnings = validation_response.get("warnings", [])
            
            if errors:
                error_messages = [f"{e.get('code', 'UNKNOWN')}: {e.get('message', 'Unknown error')}" for e in errors]
                combined_errors = " | ".join(error_messages)
                raise ValidationException(
                    f"FedEx MPS validation failed: {combined_errors}",
                    details={
                        "order_id": order_id,
                        "errors": errors,
                        "warnings": warnings,
                        "transaction_id": validation_response.get("transactionId")
                    }
                )
            
            if warnings:
                logger.warning(f"FedEx MPS validation warnings for order {order_id}: {warnings}")
                
        except Exception as e:
            logger.error(f"FedEx MPS validation error for order {order_id}: {str(e)}")
            raise ValidationException(
                f"FedEx MPS validation failed: {str(e)}",
                details={"order_id": order_id, "error": str(e)}
            )
        
        # Creazione sequenziale di tutti i colli
        for sequence_number, package in enumerate(packages, start=1):
            logger.info(f"Creating FedEx MPS piece {sequence_number}/{total_package_count} for order {order_id}")
            
            try:
                # Costruisci payload MPS per questo collo
                # Per MPS, tutti i colli devono avere customsClearanceDetail identico
                mps_payload = self.fedex_mapper.build_mps_shipment_request(
                    order_data=order_data,
                    fedex_config=fedex_config,
                    receiver_address=receiver_address,
                    receiver_country_iso=receiver_country_iso,
                    package=package,
                    sequence_number=sequence_number,
                    total_package_count=total_package_count,
                    master_tracking_id=master_tracking,  # None per master, tracking per colli successivi
                    reference=internal_reference,
                    shipping_price_tax_incl=shipping_price_tax_incl,
                    order_details=order_details,  # Sempre incluso per tutti i colli MPS
                    total_weight_all_packages=total_weight_all_packages,
                    shipping_total_weight=shipping_total_weight
                )
                
                # Log payload per colli successivi al master
                if sequence_number > 1:
                    import json
                    logger.info(f"FedEx MPS payload for piece {sequence_number}/{total_package_count} (order {order_id}): {json.dumps(mps_payload, indent=2, ensure_ascii=False)}")
                
                # Crea spedizione per questo collo
                fedex_response = await self.fedex_client.create_shipment(
                    payload=mps_payload,
                    credentials=credentials,
                    fedex_config=fedex_config
                )
                
                # Estrai tracking numbers
                tracking_numbers = self.fedex_mapper.extract_tracking_from_response(fedex_response)
                all_tracking_numbers.extend(tracking_numbers)
                
                # Estrai master tracking dalla prima risposta
                if sequence_number == 1:
                    output = fedex_response.get("output", {})
                    transaction_shipments = output.get("transactionShipments", [])
                    if transaction_shipments:
                        master_tracking = transaction_shipments[0].get("masterTrackingNumber")
                        master_awb = master_tracking or (tracking_numbers[0] if tracking_numbers else None)
                        logger.info(f"FedEx MPS master tracking: {master_tracking}")
                
                # Estrai label da packageDocuments
                package_document_urls = self.fedex_mapper.extract_package_documents_urls(fedex_response)
                
                if package_document_urls:
                    # Download PDF per questo collo
                    for url in package_document_urls:
                        pdf_bytes = await self._download_pdf_from_url(url)
                        if pdf_bytes:
                            all_pdf_bytes.append(pdf_bytes)
                            logger.debug(f"Downloaded PDF for piece {sequence_number} from {url}, size: {len(pdf_bytes)} bytes")
                
            except Exception as e:
                logger.error(f"Error creating FedEx MPS piece {sequence_number} for order {order_id}: {str(e)}", exc_info=True)
                # Per MPS, se un collo fallisce, interrompiamo tutto
                raise InfrastructureException(
                    f"FedEx MPS piece {sequence_number} creation failed: {str(e)}",
                    details={
                        "order_id": order_id,
                        "sequence_number": sequence_number,
                        "total_package_count": total_package_count,
                        "error": str(e)
                    }
                )
        
        # Unisci tutte le label PDF in un unico PDF
        merged_label_b64 = None
        if all_pdf_bytes:
            try:
                if len(all_pdf_bytes) > 1:
                    logger.info(f"Merging {len(all_pdf_bytes)} PDFs into one for MPS shipment {master_awb}")
                    merged_pdf_bytes = self._merge_pdf_labels(all_pdf_bytes)
                else:
                    merged_pdf_bytes = all_pdf_bytes[0]
                
                # Converti in base64
                merged_label_b64 = base64.b64encode(merged_pdf_bytes).decode('utf-8')
                logger.info(f"Successfully merged {len(all_pdf_bytes)} PDF(s) for MPS shipment {master_awb}, total size: {len(merged_pdf_bytes)} bytes")
            except Exception as e:
                logger.error(f"Error merging PDFs for MPS shipment {master_awb}: {str(e)}", exc_info=True)
                # Continua anche se il merge fallisce
        
        # Salva PDF label unificato
        if master_awb and merged_label_b64:
            try:
                result = await self._save_documents(
                    awb=master_awb,
                    label_b64=merged_label_b64,
                    order_id=order_id,
                    carrier_api_id=carrier_api_id
                )
                if result:
                    logger.info(f"FedEx MPS document saved successfully for AWB {master_awb}, SHA256: {result.get('sha256_hash', 'N/A')}")
            except Exception as e:
                logger.error(f"Error saving FedEx MPS document for AWB {master_awb}: {str(e)}", exc_info=True)
        
        # Aggiorna tracking e stato (2 = Tracking Assegnato)
        if master_awb:
            try:
                self.shipping_repository.update_tracking_and_state(order_data.id_shipping, master_awb, 2)
            except Exception:
                # fallback: almeno salva il tracking
                self.shipping_repository.update_tracking(order_data.id_shipping, master_awb)
        
        return {
            "awb": master_awb or "",
            "tracking_numbers": all_tracking_numbers,
            "master_tracking_number": master_tracking,
            "transaction_id": None  # MPS può avere multiple transaction IDs, non restituiamo uno specifico
        }
    
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
            
            # 9.1. Controllo se è MPS (Multiple-Piece Shipping)
            package_count = len(packages) if packages else 0
            is_mps = package_count > 1
            
            # 9.2. Costruzione FedEx validation payload
            if is_mps:
                # MPS: validare solo il master (primo collo)
                logger.info(f"Validating FedEx MPS master piece for order {order_id}")
                master_package = packages[0]
                validation_payload = self.fedex_mapper.build_mps_shipment_request(
                    order_data=order_data,
                    fedex_config=fedex_config,
                    receiver_address=receiver_address,
                    receiver_country_iso=receiver_country_iso,
                    package=master_package,
                    sequence_number=1,
                    total_package_count=package_count,
                    master_tracking_id=None,  # Master non ha masterTrackingId
                    reference=internal_reference,
                    shipping_price_tax_incl=shipping_price_tax_incl,
                    order_details=order_details
                )
            else:
                # Single package: comportamento attuale
                validation_payload = self.fedex_mapper.build_validate_request(
                    order_data=order_data,
                    fedex_config=fedex_config,
                    receiver_address=receiver_address,
                    receiver_country_iso=receiver_country_iso,
                    packages=packages,
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
            from src.repository.shipment_document_repository import ShipmentDocumentRepository
            
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
                    f"No tracking number found for order {order_id}",
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
    
    def _cleanup_old_documents(self, order_id: int) -> None:
        """
        Elimina documenti esistenti per un ordine prima di salvare nuovi documenti
        
        Args:
            order_id: ID dell'ordine
        """
        try:
            from src.repository.shipment_document_repository import ShipmentDocumentRepository
            import shutil
            
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

