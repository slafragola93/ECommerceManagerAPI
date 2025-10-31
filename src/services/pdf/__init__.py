"""
Package per servizi PDF
Segue principi SOLID con classe base astratta e servizi specifici per tipo documento
"""
from src.services.pdf.base_pdf_service import BasePDFService
from src.services.pdf.preventivo_pdf_service import PreventivoPDFService
from src.services.pdf.ddt_pdf_service import DDTPDFService
from src.services.pdf.fiscal_document_pdf_service import FiscalDocumentPDFService

__all__ = [
    'BasePDFService',
    'PreventivoPDFService',
    'DDTPDFService',
    'FiscalDocumentPDFService'
]
