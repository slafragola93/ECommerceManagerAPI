"""Cliente SOAP per integrazione web service AS400."""

import logging
import time
import requests
from typing import Dict, Optional
from ..config.settings import get_settings
from ..builders.xml_builder import OrderXMLBuilder
from ..parsers.xml_parser import AS400ResponseParser
from ..services.order_service import OrderDataService
from src.models.order import Order

logger = logging.getLogger("as400_validate_order_megawatt")


class AS400SoapClient:
    """Cliente SOAP per web service AS400."""

    def __init__(self, order_service: OrderDataService):
        """Inizializza cliente SOAP con servizio ordini."""
        self.order_service = order_service
        self.xml_builder = OrderXMLBuilder(order_service)
        self.parser = AS400ResponseParser()
        self.settings = get_settings()

    def send_order(self, order: Order) -> Dict[str, str]:
        """
        Invia ordine al web service AS400 via SOAP.
        
        Args:
            order: Oggetto Order con tutte le relazioni caricate
            
        Returns:
            Dizionario con risposta: numeroOrdine, stampataDistinta, messaggioErrore
            
        Raises:
            requests.RequestException: Su errori di rete/HTTP
            ValueError: Su errori di parsing XML
        """
        # Costruisci XML ordine
        order_xml = self.xml_builder.build_order_xml(order)
        
        # Log XML in modalità test o per debug
        logger.info(f"XML ordine generato per ordine {order.id_order}")
        logger.debug(f"XML ordine:\n{order_xml}")
        
        # Costruisci envelope SOAP
        soap_envelope = self._build_soap_envelope(order_xml)
        
        # Invia richiesta con logica retry
        max_retries = self.settings["max_retries"]
        retry_backoff = self.settings["retry_backoff"]
        
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                response = self._send_soap_request(soap_envelope)
                return self.parser.parse_response(response.text)
                
            except (requests.RequestException, ValueError) as e:
                last_exception = e
                if attempt < max_retries:
                    wait_time = retry_backoff[min(attempt, len(retry_backoff) - 1)]
                    logger.warning(
                        f"Tentativo {attempt + 1} fallito per ordine {order.id_order}: {e}. "
                        f"Riprova tra {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Tutti i {max_retries + 1} tentativi falliti per ordine {order.id_order}: {e}"
                    )
                    raise
        
        # Non dovrebbe arrivare qui, ma per sicurezza
        if last_exception:
            raise last_exception

    def _build_soap_envelope(self, xml_content: str) -> str:
        """
        Costruisce envelope SOAP 1.1 con XML ordine.
        
        Args:
            xml_content: Stringa XML ordine (con dichiarazione XML)
            
        Returns:
            Stringa XML envelope SOAP completa
        """
        # Rimuovi dichiarazione XML se presente (serve solo il contenuto)
        xml_content_clean = xml_content
        if xml_content_clean.startswith('<?xml'):
            xml_content_clean = xml_content_clean.split('?>', 1)[1].strip()
        
        # Escape XML per inclusione nel body SOAP (escape caratteri XML speciali)
        # ElementTree fa escape del contenuto testo, ma dobbiamo fare escape dell'intera stringa XML
        escaped_xml = (
            xml_content_clean
            .replace("&", "&amp;")  # Deve essere primo!
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
        
        soap_action = self.settings["soap_action"]
        # Estrai namespace da SOAPAction (rimuovi nome metodo)
        # SOAPAction: "http://webservice.gruppomegawatt.it/WS_WebMarket/InserisciOrdineWebMarket"
        # Namespace dovrebbe essere: "http://webservice.gruppomegawatt.it/WS_WebMarket"
        namespace = soap_action.rsplit('/', 1)[0] if '/' in soap_action else soap_action
        
        envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <InserisciOrdineWebMarket xmlns="{namespace}">
      <XML_in>{escaped_xml}</XML_in>
    </InserisciOrdineWebMarket>
  </soap:Body>
</soap:Envelope>'''
        
        return envelope

    def _send_soap_request(self, soap_envelope: str) -> requests.Response:
        """
        Invia richiesta SOAP al web service.
        
        Args:
            soap_envelope: Stringa XML envelope SOAP completa
            
        Returns:
            Oggetto requests.Response
            
        Raises:
            requests.RequestException: Su errori di rete/HTTP
        """
        endpoint = self.settings["soap_endpoint"]
        soap_action = self.settings["soap_action"]
        
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{soap_action}"'
        }
        
        connect_timeout = self.settings["connect_timeout"]
        total_timeout = self.settings["total_timeout"]
        
        try:
            response = requests.post(
                endpoint,
                data=soap_envelope.encode("utf-8"),
                headers=headers,
                timeout=(connect_timeout, total_timeout)
            )
            
            response.raise_for_status()
            return response
            
        except requests.Timeout as e:
            logger.error(f"Timeout richiesta: {e}")
            raise
        except requests.RequestException as e:
            logger.error(f"Errore richiesta: {e}")
            raise

