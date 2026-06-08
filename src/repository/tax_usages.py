"""Conteggi utilizzo Tax prima della delete (BE-ALIQ-02)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TaxUsages:
    order_count: int
    document_count: int
    is_reverse_charge: bool

    def has_any(self) -> bool:
        return (
            self.order_count > 0
            or self.document_count > 0
            or self.is_reverse_charge
        )
