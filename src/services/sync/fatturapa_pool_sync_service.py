"""
Servizio per la sincronizzazione delle fatture di acquisto dal POOL FatturaPA.

Questo servizio si occupa di:
1. Recuperare l'API key da app_configurations
2. Chiamare l'API FatturaPA per ottenere il feed POOL
3. Parsare il feed XML/ATOM
4. Filtrare i documenti di acquisto e tipi utili (es. 'Ricezione')
5. Scaricare i file XML/P7M
6. Salvare nel database con idempotenza
7. Opzionalmente marcare come consumate le righe nel POOL
"""

import httpx
import xml.etree.ElementTree as ET
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from src.repository.app_configuration_repository import AppConfigurationRepository
from src.repository.purchase_invoice_sync_repository import PurchaseInvoiceSyncRepository

logger = logging.getLogger(__name__)


class FatturaPAPoolSyncService:
    """Servizio per sincronizzazione fatture di acquisto dal POOL FatturaPA"""
    
    # Namespace XML/ATOM per il feed
    ATOM_NS = {'atom': 'http://www.w3.org/2005/Atom'}
    METADATA_NS = {'m': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata'}
    DATA_NS = {'d': 'http://schemas.microsoft.com/ado/2007/08/dataservices'}
    
    def __init__(
        self, 
        db: Session, 
        download_dir: Optional[str] = None,
        timeout: int = 60
    ):
        """
        Inizializza il servizio
        
        Args:
            db: Sessione database SQLAlchemy
            download_dir: Directory dove salvare i file scaricati (default: fatture_download/)
            timeout: Timeout per le richieste HTTP in secondi
        """
        self.db = db
        self.config_repo = AppConfigurationRepository(db)
        self.invoice_repo = PurchaseInvoiceSyncRepository(db)
        self.timeout = timeout
        
        # Directory download (default: fatture_download/)
        self.download_dir = download_dir or os.path.join(
            os.getcwd(), 
            'fatture_download'
        )
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Recupera API key da configurazione
        self.api_key = self._get_api_key()
        if not self.api_key:
            raise ValueError("API key FatturaPA non configurata in app_configurations")
        
        # Base URL API FatturaPA
        self.base_url = self._get_config_value(
            "fatturapa", 
            "base_url", 
            "https://api.fatturapa.com/ws/V10.svc/rest"
        )
        
        logger.info(f"FatturaPAPoolSyncService inizializzato con API key: {self.api_key[:10]}...")
    
    def _get_api_key(self) -> Optional[str]:
        """Recupera l'API key da app_configurations"""
        try:
            config = self.config_repo.get_by_name_and_category('api_key', 'fatturapa')
            return config.value if config else None
        except Exception as e:
            logger.error(f"Errore nel recupero API key: {e}")
            return None
    
    def _get_config_value(self, category: str, name: str, default: str = None) -> str:
        """Recupera un valore dalla configurazione"""
        try:
            config = self.config_repo.get_by_name_and_category(name, category)
            return config.value if config else default
        except Exception as e:
            logger.warning(f"Errore nel recupero configurazione {category}.{name}: {e}")
            return default
    
    async def sync_pool(self) -> Dict[str, Any]:
        """
        Esegue la sincronizzazione completa dal POOL FatturaPA
        
        Returns:
            Dict con statistiche della sincronizzazione
        """
        stats = {
            'start_time': datetime.now().isoformat(),
            'status': 'success',
            'entries_found': 0,
            'entries_processed': 0,
            'entries_downloaded': 0,
            'entries_saved': 0,
            'entries_skipped': 0,
            'errors': []
        }
        
        try:
            logger.info("Inizio sincronizzazione POOL FatturaPA")
            
            # 1. Ottieni il SAS URL dal POOL
            pool_data = await self._get_pool_data()
            if not pool_data or 'Complete' not in pool_data:
                error_msg = "Impossibile recuperare dati POOL o campo 'Complete' mancante"
                logger.error(error_msg)
                stats['status'] = 'error'
                stats['errors'].append(error_msg)
                return stats
            
            complete_url = pool_data['Complete']
            logger.info(f"SAS URL POOL ottenuto: {complete_url[:50]}...")
            
            # 2. Scarica il feed ATOM dalla SAS Table URL
            feed_xml = await self._download_feed(complete_url)
            if not feed_xml:
                error_msg = "Feed ATOM vuoto o non scaricabile"
                logger.warning(error_msg)
                stats['status'] = 'warning'
                stats['errors'].append(error_msg)
                return stats
            
            # 3. Parsare il feed e estrarre entries
            entries = self._parse_feed(feed_xml)
            stats['entries_found'] = len(entries)
            logger.info(f"Trovati {len(entries)} entries nel feed")
            
            if len(entries) == 0:
                logger.info("Nessuna entry da processare nel feed")
                return stats
            
            # 4. Filtra e processa ogni entry
            for entry in entries:
                try:
                    # Filtra solo Acquisto e tipi utili
                    if not self._should_process_entry(entry):
                        stats['entries_skipped'] += 1
                        continue
                    
                    stats['entries_processed'] += 1
                    
                    # Verifica se già esiste (idempotenza)
                    if self.invoice_repo.exists(
                        entry.get('IdentificativoSdI', ''),
                        entry.get('NomeFile', '')
                    ):
                        logger.debug(
                            f"Entry già esistente (skip): SDI={entry.get('IdentificativoSdI')}, "
                            f"File={entry.get('NomeFile')}"
                        )
                        stats['entries_skipped'] += 1
                        continue
                    
                    # Scarica il file XML/P7M
                    file_content, file_path = await self._download_file(entry)
                    if file_content:
                        stats['entries_downloaded'] += 1
                        entry['xml_content'] = file_content
                        entry['file_path'] = file_path
                    
                    # Salva nel database
                    invoice_data = self._prepare_invoice_data(entry)
                    created_invoice = self.invoice_repo.create(invoice_data)
                    
                    if created_invoice:
                        stats['entries_saved'] += 1
                        logger.info(
                            f"Salvata fattura: SDI={created_invoice.identificativo_sdi}, "
                            f"File={created_invoice.nome_file}"
                        )
                    else:
                        stats['entries_skipped'] += 1
                    
                except Exception as e:
                    error_msg = f"Errore processamento entry: {e}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)
                    continue
            
            stats['end_time'] = datetime.now().isoformat()
            logger.info(
                f"Sincronizzazione completata: {stats['entries_saved']} salvate, "
                f"{stats['entries_skipped']} saltate, {len(stats['errors'])} errori"
            )
            
            return stats
            
        except Exception as e:
            error_msg = f"Errore durante sincronizzazione: {e}"
            logger.error(error_msg)
            stats['status'] = 'error'
            stats['errors'].append(error_msg)
            stats['end_time'] = datetime.now().isoformat()
            return stats
    
    async def _get_pool_data(self) -> Optional[Dict[str, Any]]:
        """
        Chiama GET https://api.fatturapa.com/ws/V10.svc/rest/pool/{apiKey}
        
        Returns:
            Dict con dati POOL (include 'Complete' SAS URL)
        """
        try:
            url = f"{self.base_url}/pool/{self.api_key}"
            logger.debug(f"Chiamata API POOL: {url}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                data = response.json()
                logger.debug(f"Risposta POOL: {data}")
                return data
                
        except httpx.HTTPError as e:
            logger.error(f"Errore HTTP nella chiamata POOL: {e}")
            return None
        except Exception as e:
            logger.error(f"Errore generico nella chiamata POOL: {e}")
            return None
    
    async def _download_feed(self, sas_url: str) -> Optional[str]:
        """
        Scarica il feed XML/ATOM dalla SAS Table URL
        
        Args:
            sas_url: URL SAS della tabella Azure
        
        Returns:
            Contenuto XML come stringa
        """
        try:
            logger.debug(f"Download feed da SAS URL: {sas_url[:50]}...")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(sas_url)
                response.raise_for_status()
                
                xml_content = response.text
                logger.debug(f"Feed scaricato, dimensione: {len(xml_content)} caratteri")
                return xml_content
                
        except httpx.HTTPError as e:
            logger.error(f"Errore HTTP nel download feed: {e}")
            return None
        except Exception as e:
            logger.error(f"Errore generico nel download feed: {e}")
            return None
    
    def _parse_feed(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Parsare il feed XML/ATOM e estrarre le entries
        
        Args:
            xml_content: Contenuto XML del feed
        
        Returns:
            Lista di dizionari con dati delle entries
        """
        try:
            root = ET.fromstring(xml_content)
            entries = []
            
            # Trova tutti gli elementi <entry>
            # Il feed può usare namespace atom o essere senza namespace
            for entry_elem in root.findall('.//atom:entry', self.ATOM_NS):
                entry_data = self._extract_entry_data(entry_elem)
                if entry_data:
                    entries.append(entry_data)
            
            # Se non trova entries con namespace atom, prova senza namespace
            if not entries:
                for entry_elem in root.findall('.//entry'):
                    entry_data = self._extract_entry_data_no_ns(entry_elem)
                    if entry_data:
                        entries.append(entry_data)
            
            logger.info(f"Parsate {len(entries)} entries dal feed")
            return entries
            
        except ET.ParseError as e:
            logger.error(f"Errore parsing XML: {e}")
            return []
        except Exception as e:
            logger.error(f"Errore generico nel parsing feed: {e}")
            return []
    
    def _extract_entry_data(self, entry_elem: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Estrae i dati da un elemento <entry> con namespace
        
        Args:
            entry_elem: Elemento XML <entry>
        
        Returns:
            Dizionario con dati dell'entry
        """
        try:
            # Trova l'elemento <content><m:properties>
            properties = entry_elem.find('.//m:properties', self.METADATA_NS)
            if properties is None:
                return None
            
            # Estrai i campi
            data = {}
            for child in properties:
                # Rimuovi namespace dal tag
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                data[tag] = child.text if child.text else ''
            
            return data
            
        except Exception as e:
            logger.error(f"Errore estrazione dati entry: {e}")
            return None
    
    def _extract_entry_data_no_ns(self, entry_elem: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Estrae i dati da un elemento <entry> senza namespace
        
        Args:
            entry_elem: Elemento XML <entry>
        
        Returns:
            Dizionario con dati dell'entry
        """
        try:
            # Cerca properties o content
            properties = entry_elem.find('.//properties')
            if properties is None:
                properties = entry_elem.find('.//content')
            
            if properties is None:
                return None
            
            # Estrai i campi
            data = {}
            for child in properties:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                data[tag] = child.text if child.text else ''
            
            return data
            
        except Exception as e:
            logger.error(f"Errore estrazione dati entry (no ns): {e}")
            return None
    
    def _should_process_entry(self, entry: Dict[str, Any]) -> bool:
        """
        Determina se un'entry deve essere processata
        
        Filtra per:
        - Direzione = 'Acquisto'
        - Tipo = 'Ricezione' (o altri tipi configurabili)
        
        Args:
            entry: Dati dell'entry
        
        Returns:
            True se deve essere processata, False altrimenti
        """
        direzione = entry.get('Direzione', '')
        tipo = entry.get('Tipo', '')
        
        # Filtra solo acquisti
        if direzione.lower() != 'acquisto':
            return False
        
        # Filtra tipi utili (configurabile)
        # Tipi comuni: 'Ricezione', 'Notifica', etc.
        tipi_validi = ['ricezione', 'notifica', 'ricevuta']
        if tipo.lower() not in tipi_validi:
            logger.debug(f"Tipo '{tipo}' non valido per processamento")
            return False
        
        return True
    
    async def _download_file(
        self, 
        entry: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Scarica il file XML/P7M dal campo URI
        
        Args:
            entry: Dati dell'entry contenente il campo URI
        
        Returns:
            Tuple (contenuto_file, path_locale)
        """
        uri = entry.get('URI', '')
        nome_file = entry.get('NomeFile', 'unknown.xml')
        
        if not uri:
            logger.warning(f"URI mancante per file {nome_file}")
            return None, None
        
        try:
            logger.debug(f"Download file: {nome_file} da {uri[:50]}...")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(uri)
                response.raise_for_status()
                
                # Salva il file localmente
                file_path = os.path.join(self.download_dir, nome_file)
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                # Ritorna sia il contenuto che il path
                content = response.text if nome_file.endswith('.xml') else response.content.decode('utf-8', errors='ignore')
                
                logger.debug(f"File scaricato: {file_path}")
                return content, file_path
                
        except httpx.HTTPError as e:
            logger.error(f"Errore HTTP nel download file {nome_file}: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Errore generico nel download file {nome_file}: {e}")
            return None, None
    
    def _prepare_invoice_data(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepara i dati per il salvataggio nel database
        
        Args:
            entry: Dati dell'entry dal feed
        
        Returns:
            Dizionario con dati formattati per PurchaseInvoiceSync
        """
        return {
            'identificativo_sdi': entry.get('IdentificativoSdI', ''),
            'nome_file': entry.get('NomeFile', ''),
            'direzione': entry.get('Direzione', ''),
            'tipo': entry.get('Tipo', ''),
            'blob_uri': entry.get('URI', ''),
            'xml_content': entry.get('xml_content'),  # Aggiunto dopo download
            'file_path': entry.get('file_path'),  # Aggiunto dopo download
            'partition_key': entry.get('PartitionKey', ''),
            'row_key': entry.get('RowKey', ''),
            'etag': entry.get('ETag', ''),
        }

