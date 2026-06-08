"""Interfaccia Settings service."""
from abc import ABC, abstractmethod

from src.schemas.settings_schema import SettingsResponseSchema, SettingsUpdateSchema


class ISettingsService(ABC):
    @abstractmethod
    async def get_settings(self) -> SettingsResponseSchema:
        pass

    @abstractmethod
    async def update_settings(self, data: SettingsUpdateSchema) -> SettingsResponseSchema:
        pass
