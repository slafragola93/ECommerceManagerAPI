"""
Interfaccia per Carrier Price Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional
from src.core.interfaces import IRepository
from src.models.carrier_price import CarrierPrice

class ICarrierPriceRepository(IRepository[CarrierPrice, int]):
    """Interface per la repository dei prezzi carrier"""
    pass

