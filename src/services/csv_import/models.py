"""
Data models for CSV Import System.

Immutable dataclasses for representing import/validation results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass(frozen=True)
class ValidationError:
    """
    Rappresenta un errore di validazione su una specifica riga CSV.
    
    Attributes:
        row_number: Numero riga CSV (1-based, esclude header)
        field_name: Nome campo con errore
        error_type: Tipo errore (missing, type_error, fk_violation, unique_violation, business_rule)
        message: Messaggio descrittivo
        value: Valore che ha causato l'errore (opzionale)
    """
    row_number: int
    field_name: str
    error_type: str
    message: str
    value: Optional[Any] = None


@dataclass(frozen=True)
class ImportError:
    """
    Errore generico durante import (non legato a riga specifica).
    
    Attributes:
        error_type: Tipo errore (dependency_missing, parse_error, db_error)
        message: Messaggio descrittivo
        details: Dettagli aggiuntivi
    """
    error_type: str
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ValidationResult:
    """
    Risultato validazione pre-import.
    
    Attributes:
        is_valid: Se validazione è passata
        total_rows: Numero totale righe CSV (escluso header)
        valid_rows: Numero righe valide
        errors: Lista errori di validazione
        missing_dependencies: Lista dipendenze mancanti
        duplicate_origins: Lista id_origin duplicati
        invalid_foreign_keys: Dizionario {field: [valori_invalidi]}
        validation_time: Tempo validazione in secondi
    """
    is_valid: bool
    total_rows: int
    valid_rows: int
    errors: List[ValidationError] = field(default_factory=list)
    missing_dependencies: List[str] = field(default_factory=list)
    duplicate_origins: List[int] = field(default_factory=list)
    invalid_foreign_keys: Dict[str, List[int]] = field(default_factory=dict)
    validation_time: float = 0.0


@dataclass(frozen=True)
class ImportResult:
    """
    Risultato completo operazione import.
    
    Attributes:
        entity_type: Tipo entità importata
        id_platform: ID platform usato
        total_rows: Numero totale righe CSV
        validated_rows: Numero righe validate con successo
        inserted_rows: Numero righe effettivamente inserite
        skipped_rows: Numero righe saltate (duplicati)
        errors: Lista errori import/validazione
        validation_time: Tempo validazione in secondi
        import_time: Tempo import in secondi
        started_at: Timestamp inizio operazione
        completed_at: Timestamp fine operazione
    """
    entity_type: str
    id_platform: int
    total_rows: int
    validated_rows: int
    inserted_rows: int
    skipped_rows: int
    errors: List[ValidationError] = field(default_factory=list)
    validation_time: float = 0.0
    import_time: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calcola percentuale successo"""
        if self.total_rows == 0:
            return 0.0
        return (self.inserted_rows / self.total_rows) * 100
    
    @property
    def total_time(self) -> float:
        """Tempo totale operazione"""
        return self.validation_time + self.import_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per risposta API"""
        return {
            "entity_type": self.entity_type,
            "id_platform": self.id_platform,
            "total_rows": self.total_rows,
            "validated_rows": self.validated_rows,
            "inserted_rows": self.inserted_rows,
            "skipped_rows": self.skipped_rows,
            "success_rate": round(self.success_rate, 2),
            "errors_count": len(self.errors),
            "errors": [
                {
                    "row": err.row_number,
                    "field": err.field_name,
                    "type": err.error_type,
                    "message": err.message,
                    "value": err.value
                }
                for err in self.errors[:100]  # Limita a 100 per response size
            ] if self.errors else [],
            "validation_time": round(self.validation_time, 2),
            "import_time": round(self.import_time, 2),
            "total_time": round(self.total_time, 2),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

