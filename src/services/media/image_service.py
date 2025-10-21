"""
Servizio per la gestione delle immagini dei prodotti
"""

import asyncio
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any
from pathlib import Path
from urllib.parse import urlparse
import hashlib
from datetime import datetime
from PIL import Image
import io


class ImageService:
    """
    Servizio per la gestione delle immagini dei prodotti.
    Gestisce il download, il salvataggio e la generazione degli URL delle immagini.
    """
    
    def __init__(self, base_path: str = "media/product_images"):
        """
        Inizializza il servizio immagini.
        
        Args:
            base_path: Percorso base per il salvataggio delle immagini
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        
        # Configura session con connection pooling per performance
        self.session = requests.Session()
        
        # Configura retry strategy
        retry_strategy = Retry(
            total=2,  # Solo 2 retry per velocità
            backoff_factor=0.1,  # Backoff minimo
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        # Configura adapter con pool di connessioni
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,  # Pool di connessioni
            pool_maxsize=100,  # Max connessioni nel pool
            pool_block=False  # Non bloccare se pool pieno
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Parametri di performance configurabili
        self.image_quality = 15
        self.max_image_size = (400, 300)
    
    def download_and_save_image(
        self, 
        image_url: str, 
        product_id: int, 
        platform_id: int
    ) -> Optional[str]:
        """
        Scarica e salva un'immagine da un URL.
        
        Args:
            image_url: URL dell'immagine da scaricare
            product_id: ID del prodotto (ID locale del database)
            platform_id: ID della piattaforma
            
        Returns:
            Percorso relativo dell'immagine salvata o None se il download fallisce
        """
        try:
            # Crea la struttura delle cartelle
            platform_dir = self.base_path / str(platform_id)
            platform_dir.mkdir(exist_ok=True)
            
            # Genera il nome del file con formato fisso
            filename = f"product_{product_id}.jpg"
            file_path = platform_dir / filename
            
            # Controlla se il file esiste già (performance check)
            if file_path.exists():
                return f"/media/product_images/{platform_id}/{filename}"
            
            # Scarica l'immagine con session ottimizzata
            response = self.session.get(image_url, timeout=3, stream=True)
            if response.status_code == 200:
                # Legge tutto il contenuto in memoria
                content = response.content
                
                # Comprimi l'immagine per risparmiare memoria
                compressed_content = self._compress_image(content)
                        
                # Scrive il file
                self._write_file_sync(file_path, compressed_content)
                        
                # Restituisce il percorso relativo
                return f"/media/product_images/{platform_id}/{filename}"
            else:
                print(f"Warning: Failed to download image: HTTP {response.status_code}")
                return None
                        
        except Exception as e:
            print(f"Warning: Failed to download image from {image_url}: {str(e)}")
            return None
    
    def _compress_image(self, content: bytes) -> bytes:
        """
        Comprime un'immagine per risparmiare memoria.
        
        Args:
            content: Contenuto binario dell'immagine originale
            
        Returns:
            Contenuto binario dell'immagine compressa
        """
        try:
            # Apri l'immagine
            image = Image.open(io.BytesIO(content))
            
            # Converti in RGB se necessario (per JPEG)
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
            
            # Ridimensiona usando parametri configurabili
            max_width, max_height = self.max_image_size
            if image.width > max_width or image.height > max_height:
                image.thumbnail((max_width, max_height), Image.Resampling.NEAREST)  # Più veloce di LANCZOS
            
            # Comprimi usando qualità configurabile per velocità massima
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=self.image_quality, optimize=True)
            
            return output.getvalue()
            
        except Exception as e:
            # Se la compressione fallisce, restituisci l'originale
            print(f"Warning: Failed to compress image: {str(e)}")
            return content
    
    def _write_file_sync(self, file_path: Path, content: bytes):
        """Metodo helper sincrono per scrivere file"""
        with open(file_path, 'wb') as f:
            f.write(content)
    
    def generate_prestashop_image_url(
        self, 
        base_url: str, 
        image_id: int, 
        link_rewrite: str
    ) -> str:
        """
        Genera l'URL dell'immagine PrestaShop secondo il formato standard.
        
        Args:
            base_url: URL base del sito PrestaShop
            image_id: ID dell'immagine in PrestaShop
            link_rewrite: Link rewrite del prodotto
            
        Returns:
            URL completo dell'immagine
        """
        # Formato PrestaShop: https://{URL_ECOMMERCE}/{id_image}-small_default/{link_rewrite}.jpg
        return f"{base_url.rstrip('/')}/{image_id}-small_default/{link_rewrite}.jpg"
    
    def generate_local_image_path(
        self, 
        platform_id: int, 
        product_id: int
    ) -> str:
        """
        Genera il percorso locale dell'immagine del prodotto.
        
        Args:
            platform_id: ID della piattaforma
            product_id: ID del prodotto (ID locale del database)
            
        Returns:
            Percorso relativo dell'immagine locale
        """
        # Formato: /media/product_images/{platform_id}/product_{product_id}.jpg
        return f"/media/product_images/{platform_id}/product_{product_id}.jpg"
    
    def generate_complete_image_url(
        self, 
        platform_id: int, 
        product_id: int,
        base_url: str = None
    ) -> str:
        """
        Genera l'URL completo dell'immagine del prodotto.
        
        Args:
            platform_id: ID della piattaforma
            product_id: ID del prodotto (ID locale del database)
            base_url: URL base del server (opzionale)
            
        Returns:
            URL completo dell'immagine
        """
        relative_path = self.generate_local_image_path(platform_id, product_id)
        if base_url:
            # Rimuovi lo slash iniziale dal percorso relativo per evitare doppi slash
            clean_path = relative_path.lstrip('/')
            return f"{base_url.rstrip('/')}/{clean_path}"
        else:
            return relative_path
    
    def process_prestashop_product_image(
        self,
        product_data: Dict[str, Any],
        platform_id: int,
        base_url: str
    ) -> Optional[str]:
        """
        Processa l'immagine di un prodotto PrestaShop.
        
        Args:
            product_data: Dati del prodotto da PrestaShop
            platform_id: ID della piattaforma
            base_url: URL base del sito PrestaShop
            
        Returns:
            Percorso relativo dell'immagine salvata o None se non disponibile
        """
        try:
            image_id = product_data.get('id_default_image')
            if not image_id or image_id == 0:
                return None
            
            # Genera il link_rewrite dal nome del prodotto
            name = product_data.get('name', '')
            link_rewrite = self._generate_link_rewrite(name)
            # Genera l'URL dell'immagine
            image_url = self.generate_prestashop_image_url(base_url, image_id, link_rewrite)
            # Scarica e salva l'immagine
            product_id = product_data.get('id', 0)
            saved_path = self.download_and_save_image(
                image_url, 
                product_id, 
                platform_id, 
                image_id
            )
            
            return saved_path
            
        except Exception as e:
            print(f"Error processing PrestaShop image for product {product_data.get('id', 'unknown')}: {str(e)}")
            return None
    
    def _generate_link_rewrite(self, name: str) -> str:
        """
        Genera un link_rewrite dal nome del prodotto.
        
        Args:
            name: Nome del prodotto
            
        Returns:
            Link rewrite generato
        """
        # Rimuove caratteri speciali e converte in lowercase
        import re
        link_rewrite = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
        link_rewrite = re.sub(r'\s+', '-', link_rewrite.strip())
        return link_rewrite[:50]  # Limita la lunghezza
    
    async def save_uploaded_image(
        self, 
        file_content: bytes, 
        product_id: int, 
        platform_id: int,
        filename: str
    ) -> str:
        """
        Salva un'immagine caricata dall'utente.
        
        Args:
            file_content: Contenuto del file
            product_id: ID del prodotto
            platform_id: ID della piattaforma
            filename: Nome del file originale
            
        Returns:
            Percorso relativo dell'immagine salvata
        """
        # Crea la struttura delle cartelle
        platform_dir = self.base_path / str(platform_id)
        platform_dir.mkdir(exist_ok=True)
        
        # Determina l'estensione
        file_extension = os.path.splitext(filename)[1]
        if not file_extension:
            file_extension = '.jpg'
        
        # Genera il nome del file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_filename = f"product_{product_id}_{timestamp}{file_extension}"
        
        file_path = platform_dir / saved_filename
        
        # Salva il file usando asyncio.to_thread
        await asyncio.to_thread(self._write_file_sync, file_path, file_content)
        
        return f"product_images/{platform_id}/{saved_filename}"
    
    def get_image_url(self, relative_path: str, base_url: str = None) -> str:
        """
        Genera l'URL completo per accedere all'immagine.
        
        Args:
            relative_path: Percorso relativo dell'immagine
            base_url: URL base del server (opzionale)
            
        Returns:
            URL completo dell'immagine
        """
        if base_url:
            return f"{base_url.rstrip('/')}/{relative_path}"
        else:
            # Restituisce il percorso relativo se non è specificato un base_url
            return relative_path
    
    def delete_image(self, relative_path: str) -> bool:
        """
        Elimina un'immagine dal filesystem.
        
        Args:
            relative_path: Percorso relativo dell'immagine
            
        Returns:
            True se eliminata con successo, False altrimenti
        """
        try:
            # Costruisce il percorso completo partendo dalla directory base
            file_path = self.base_path / relative_path
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False
    
    def configure_performance(self, quality: int = 15, max_size: tuple = (400, 300)):
        """
        Configura i parametri di performance per il download delle immagini.
        
        Args:
            quality: Qualità JPEG (1-100, più basso = più veloce)
            max_size: Dimensioni massime (width, height)
        """
        self.image_quality = max(1, min(100, quality))  # Limita tra 1 e 100
        self.max_image_size = max_size
