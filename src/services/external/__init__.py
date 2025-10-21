"""
External Services

This module contains services for external data sources and APIs.
"""

from .province_service import ProvinceService
from .fatturapa_service import FatturaPAService

__all__ = [
    "ProvinceService",
    "FatturaPAService",
]
