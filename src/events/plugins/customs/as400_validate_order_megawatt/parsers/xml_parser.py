"""Parser XML per risposta SOAP AS400."""

import logging
import xml.etree.ElementTree as ET
from typing import Dict, Optional

logger = logging.getLogger("as400_validate_order_megawatt")


class AS400ResponseParser:
    """Parser per risposta SOAP AS400."""

    @staticmethod
    def parse_response(soap_response: str) -> Dict[str, str]:
        """
        Analizza risposta SOAP ed estrae risultato validazione ordine.
        
        Struttura SOAP attesa:
        <soap:Envelope>
          <soap:Body>
            <InserisciOrdineWebMarketResult>
              <ordine>
                <numeroOrdine>...</numeroOrdine>
                <stampataDistinta>S|N</stampataDistinta>
                <messaggioErrore>...</messaggioErrore>
              </ordine>
            </InserisciOrdineWebMarketResult>
          </soap:Body>
        </soap:Envelope>
        
        Args:
            soap_response: Stringa XML risposta SOAP
            
        Returns:
            Dizionario con chiavi: numeroOrdine, stampataDistinta, messaggioErrore
            
        Raises:
            ValueError: Se XML è malformato o struttura inattesa
        """
        try:
            root = ET.fromstring(soap_response)
            
            # Gestisci namespace SOAP
            namespaces = {
                'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                'ws': 'http://webservice.gruppomegawatt.it/WS_WebMarket'
            }
            
            # Trova elemento Body
            body = root.find('.//soap:Body', namespaces)
            if body is None:
                # Prova senza namespace
                body = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Body')
                if body is None:
                    raise ValueError("Elemento SOAP Body non trovato")
            
            # Trova InserisciOrdineWebMarketResult
            result_elem = body.find('.//InserisciOrdineWebMarketResult')
            if result_elem is None:
                # Prova con namespace
                result_elem = body.find('.//ws:InserisciOrdineWebMarketResult', namespaces)
                if result_elem is None:
                    raise ValueError("Elemento InserisciOrdineWebMarketResult non trovato")
            
            # Trova elemento ordine
            ordine_elem = result_elem.find('ordine')
            if ordine_elem is None:
                raise ValueError("Elemento ordine non trovato nella risposta")
            
            # Estrai campi
            numero_ordine = ""
            numero_elem = ordine_elem.find('numeroOrdine')
            if numero_elem is not None and numero_elem.text:
                numero_ordine = numero_elem.text.strip()
            
            stampata_distinta = ""
            stampata_elem = ordine_elem.find('stampataDistinta')
            if stampata_elem is not None and stampata_elem.text:
                stampata_distinta = stampata_elem.text.strip()
            
            messaggio_errore = ""
            errore_elem = ordine_elem.find('messaggioErrore')
            if errore_elem is not None and errore_elem.text:
                messaggio_errore = errore_elem.text.strip()
            
            return {
                "numeroOrdine": numero_ordine,
                "stampataDistinta": stampata_distinta,
                "messaggioErrore": messaggio_errore
            }
            
        except ET.ParseError as e:
            logger.error(f"Errore parsing XML: {e}")
            raise ValueError(f"Risposta XML malformata: {e}")
        except Exception as e:
            logger.error(f"Errore inatteso durante parsing risposta: {e}")
            raise ValueError(f"Errore durante parsing risposta: {e}")

