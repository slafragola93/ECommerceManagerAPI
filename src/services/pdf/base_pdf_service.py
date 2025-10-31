"""
Classe base astratta per la generazione di PDF
Segue i principi SOLID per permettere estensioni future con strutture completamente diverse
"""
from abc import ABC, abstractmethod


class BasePDFService(ABC):
    """
    Classe base astratta per servizi di generazione PDF
    
    Ogni classe che estende BasePDFService deve implementare il metodo generate_pdf()
    che contiene la logica specifica per la generazione del documento PDF.
    """
    
    @abstractmethod
    def generate_pdf(self, *args, **kwargs) -> bytes:
        """
        Genera il PDF del documento
        
        Questo metodo deve essere implementato da ogni classe figlia con la
        signature appropriata per il tipo di documento specifico.
        
        Returns:
            bytes: Contenuto del PDF generato
            
        Raises:
            ValueError: Se i dati richiesti non sono disponibili
            Exception: Per altri errori durante la generazione
        """
        pass

