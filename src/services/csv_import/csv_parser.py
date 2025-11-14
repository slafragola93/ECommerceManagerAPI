"""
CSV Parser for Import System.

Handles CSV file parsing with auto-detection and validation.
Follows Single Responsibility Principle - only parsing logic.
"""
from __future__ import annotations

import csv
import io
from typing import List, Dict, Any, Optional, Tuple


class CSVParser:
    """
    Parser CSV con auto-detection delimiter e validazione headers.
    
    Stateless parser - tutti i metodi sono statici.
    """
    
    # Delimiters supportati in ordine di priorità
    SUPPORTED_DELIMITERS = [',', ';', '\t', '|']
    
    @staticmethod
    def parse_csv(
        file_content: bytes,
        entity_type: str,
        expected_headers: Optional[List[str]] = None
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Parse CSV file con auto-detection delimiter.
        
        Args:
            file_content: Contenuto file CSV in bytes
            entity_type: Tipo entità (per logging/error reporting)
            expected_headers: Headers attesi (opzionale, per validazione)
            
        Returns:
            Tuple (headers, rows) dove rows è lista di dizionari
            
        Raises:
            ValueError: Se CSV è malformato o headers non validi
        """
        try:
            # Decode bytes to string
            content = file_content.decode('utf-8-sig')  # utf-8-sig rimuove BOM
        except UnicodeDecodeError:
            try:
                content = file_content.decode('latin-1')
            except UnicodeDecodeError:
                raise ValueError("Unable to decode CSV file. Use UTF-8 or Latin-1 encoding.")
        
        if not content.strip():
            raise ValueError("CSV file is empty")
        
        # Auto-detect delimiter
        delimiter = CSVParser.detect_delimiter(content)
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        
        # Get headers
        if not reader.fieldnames:
            raise ValueError("CSV file has no headers")
        
        headers = [h.strip() for h in reader.fieldnames]
        
        # Validate headers se forniti expected_headers
        if expected_headers:
            missing_headers = set(expected_headers) - set(headers)
            if missing_headers:
                raise ValueError(
                    f"Missing required headers for {entity_type}: {', '.join(missing_headers)}"
                )
        
        # Parse righe
        rows = []
        for row_num, row in enumerate(reader, start=1):
            # Skip righe vuote
            if not any(row.values()):
                continue
            
            # Strip whitespace da valori
            cleaned_row = {
                key.strip(): value.strip() if isinstance(value, str) else value
                for key, value in row.items()
            }
            
            # Aggiungi row number per error reporting
            cleaned_row['_row_number'] = row_num
            rows.append(cleaned_row)
        
        if not rows:
            raise ValueError("CSV file has no data rows")
        
        return headers, rows
    
    @staticmethod
    def detect_delimiter(content: str) -> str:
        """
        Auto-detect CSV delimiter.
        
        Args:
            content: Contenuto CSV come stringa
            
        Returns:
            Delimiter character
        """
        # Prendi prime righe per analisi
        sample = '\n'.join(content.split('\n')[:5])
        
        # Prova Sniffer di csv
        try:
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            if delimiter in CSVParser.SUPPORTED_DELIMITERS:
                return delimiter
        except Exception:
            pass
        
        # Fallback: conta occorrenze delimiters
        delimiter_counts = {}
        for delim in CSVParser.SUPPORTED_DELIMITERS:
            delimiter_counts[delim] = sample.count(delim)
        
        # Usa quello con più occorrenze
        best_delimiter = max(delimiter_counts, key=delimiter_counts.get)
        
        # Se nessun delimiter trovato, usa virgola default
        if delimiter_counts[best_delimiter] == 0:
            return ','
        
        return best_delimiter
    
    @staticmethod
    def validate_headers(headers: List[str], required_fields: List[str]) -> Tuple[bool, List[str]]:
        """
        Valida che headers CSV contengano tutti i campi richiesti.
        
        Args:
            headers: Headers dal CSV
            required_fields: Campi richiesti
            
        Returns:
            Tuple (is_valid, missing_fields)
        """
        headers_set = set(h.lower() for h in headers)
        required_set = set(f.lower() for f in required_fields)
        
        missing = required_set - headers_set
        
        return len(missing) == 0, sorted(missing)
    
    @staticmethod
    def convert_value(value: str, target_type: type) -> Any:
        """
        Converte valore stringa CSV al tipo target.
        
        Args:
            value: Valore come stringa
            target_type: Tipo target (int, float, str, bool)
            
        Returns:
            Valore convertito
            
        Raises:
            ValueError: Se conversione fallisce
        """
        if value == '' or value is None:
            return None
        
        try:
            if target_type == int:
                return int(float(value))  # Handle "10.0" → 10
            elif target_type == float:
                return float(value)
            elif target_type == bool:
                return value.lower() in ('true', '1', 'yes', 'si', 'y')
            elif target_type == str:
                return str(value)
            else:
                return value
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Cannot convert '{value}' to {target_type.__name__}: {str(e)}")

