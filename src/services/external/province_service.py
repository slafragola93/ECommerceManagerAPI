import json
import os
from typing import Dict, Optional
from pathlib import Path

class ProvinceService:
    """
    Servizio per gestire le abbreviazioni delle province italiane
    basato sui dati del repository comuni-json di GitHub
    """
    
    def __init__(self):
        self.province_mapping: Dict[str, str] = {}
        self.load_province_mapping()
    
    def load_province_mapping(self) -> None:
        """Carica il mapping province -> abbreviazione dal file JSON"""
        try:
            # Percorsi candidati: root/data/comuni.json (preferito) e src/data/comuni.json (fallback)
            base_root = Path(__file__).resolve().parents[3]  
            comuni_file = base_root  / "data" / "comuni.json"
            if not comuni_file:
                print("File comuni.json non trovato. Inizializzazione con mapping manuale...")
                self._init_manual_mapping()
                return
            
            with open(comuni_file, 'r', encoding='utf-8') as f:
                comuni_data = json.load(f)
            
            # Estrai mapping province -> sigla
            for comune in comuni_data:
                provincia = comune.get('provincia', {})
                provincia_nome = provincia.get('nome', '').strip()
                sigla = comune.get('sigla', '').strip()
                
                if provincia_nome and sigla:
                    # Normalizza il nome (tutto minuscolo, senza spazi extra)
                    provincia_normalized = provincia_nome.lower().strip()
                    self.province_mapping[provincia_normalized] = sigla.upper()
            
        except Exception as e:
            print(f"Errore nel caricamento comuni.json: {e}")
            print("Inizializzazione con mapping manuale...")
            self._init_manual_mapping()
    
    def _init_manual_mapping(self) -> None:
        """Inizializza con un mapping manuale delle province principali"""
        manual_mapping = {
            'agrigento': 'AG',
            'alessandria': 'AL',
            'ancona': 'AN',
            'aosta': 'AO',
            'arezzo': 'AR',
            'ascoli piceno': 'AP',
            'asti': 'AT',
            'avellino': 'AV',
            'bari': 'BA',
            'barletta-andria-trani': 'BT',
            'belluno': 'BL',
            'benevento': 'BN',
            'bergamo': 'BG',
            'biella': 'BI',
            'bologna': 'BO',
            'bolzano': 'BZ',
            'brescia': 'BS',
            'brindisi': 'BR',
            'cagliari': 'CA',
            'caltanissetta': 'CL',
            'campobasso': 'CB',
            'caserta': 'CE',
            'catania': 'CT',
            'catanzaro': 'CZ',
            'chieti': 'CH',
            'como': 'CO',
            'cosenza': 'CS',
            'cremona': 'CR',
            'crotone': 'KR',
            'cuneo': 'CN',
            'enna': 'EN',
            'fermo': 'FM',
            'ferrara': 'FE',
            'firenze': 'FI',
            'foggia': 'FG',
            'forlì-cesena': 'FC',
            'frosinone': 'FR',
            'genova': 'GE',
            'gorizia': 'GO',
            'grosseto': 'GR',
            'imperia': 'IM',
            'isernia': 'IS',
            'la spezia': 'SP',
            'l\'aquila': 'AQ',
            'latina': 'LT',
            'lecce': 'LE',
            'lecco': 'LC',
            'livorno': 'LI',
            'lodi': 'LO',
            'lucca': 'LU',
            'macerata': 'MC',
            'mantova': 'MN',
            'massa-carrara': 'MS',
            'matera': 'MT',
            'messina': 'ME',
            'milano': 'MI',
            'modena': 'MO',
            'monza e della brianza': 'MB',
            'napoli': 'NA',
            'novara': 'NO',
            'nuoro': 'NU',
            'oristano': 'OR',
            'padova': 'PD',
            'palermo': 'PA',
            'parma': 'PR',
            'pavia': 'PV',
            'perugia': 'PG',
            'pesaro e urbino': 'PU',
            'pescara': 'PE',
            'piacenza': 'PC',
            'pisa': 'PI',
            'pistoia': 'PT',
            'pordenone': 'PN',
            'potenza': 'PZ',
            'prato': 'PO',
            'ragusa': 'RG',
            'ravenna': 'RA',
            'reggio calabria': 'RC',
            'reggio emilia': 'RE',
            'rieti': 'RI',
            'rimini': 'RN',
            'roma': 'RM',
            'rovigo': 'RO',
            'salerno': 'SA',
            'sassari': 'SS',
            'savona': 'SV',
            'siena': 'SI',
            'siracusa': 'SR',
            'sondrio': 'SO',
            'sud sardegna': 'SU',
            'taranto': 'TA',
            'teramo': 'TE',
            'terni': 'TR',
            'torino': 'TO',
            'trapani': 'TP',
            'trento': 'TN',
            'treviso': 'TV',
            'trieste': 'TS',
            'udine': 'UD',
            'varese': 'VA',
            'venezia': 'VE',
            'verbania': 'VB',
            'vercelli': 'VC',
            'verona': 'VR',
            'vibo valentia': 'VV',
            'vicenza': 'VI',
            'viterbo': 'VT'
        }
        
        self.province_mapping = manual_mapping
        print(f"Inizializzato mapping manuale con {len(self.province_mapping)} province")
    
    def get_province_abbreviation(self, state_name: str) -> Optional[str]:
        """
        Restituisce l'abbreviazione della provincia per un dato nome
        
        Args:
            state_name: Nome della provincia (es. "Napoli", "Milano")
            
        Returns:
            Abbreviazione della provincia (es. "NA", "MI") o None se non trovata
        """
        if not state_name or not state_name.strip():
            return None
        
        # Normalizza il nome della provincia
        normalized_name = state_name.lower().strip()
        
        # Cerca corrispondenza esatta
        if normalized_name in self.province_mapping:
            return self.province_mapping[normalized_name]
        
        # Cerca corrispondenze parziali (per gestire variazioni)
        for provincia, abbreviazione in self.province_mapping.items():
            if normalized_name in provincia or provincia in normalized_name:
                return abbreviazione
        
        # Se non trova nulla, restituisce None
        print(f"Abbreviazione non trovata per provincia: '{state_name}'")
        return None
    
    def update_state_with_abbreviation(self, state_name: str) -> str:
        """
        Aggiorna il nome dello state con l'abbreviazione se disponibile
        
        Args:
            state_name: Nome originale della provincia
            
        Returns:
            Abbreviazione se trovata, altrimenti il nome originale
        """
        abbreviation = self.get_province_abbreviation(state_name)
        return abbreviation if abbreviation else state_name
    
    def get_all_abbreviations(self) -> Dict[str, str]:
        """Restituisce tutto il mapping province -> abbreviazioni"""
        return self.province_mapping.copy()

# Istanza singleton per ottimizzare le performance
province_service = ProvinceService()
