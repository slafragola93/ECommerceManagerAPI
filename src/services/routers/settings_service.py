"""Facade /api/v1/settings/ — legge/scrive su app_configurations (categoria vies)."""
from src.core.cache import invalidate_init_data_cache
from src.core.exceptions import NotFoundException
from src.repository.interfaces.app_configuration_repository_interface import (
    IAppConfigurationRepository,
)
from src.repository.interfaces.tax_repository_interface import ITaxRepository
from src.schemas.settings_schema import SettingsResponseSchema, SettingsUpdateSchema
from src.services.interfaces.settings_service_interface import ISettingsService
from src.vies.vies_app_configuration import (
    get_reverse_charge_id_tax,
    set_reverse_charge_id_tax,
)


class SettingsService(ISettingsService):
    def __init__(
        self,
        app_configuration_repository: IAppConfigurationRepository,
        tax_repository: ITaxRepository,
    ):
        self._app_configuration_repository = app_configuration_repository
        self._tax_repository = tax_repository

    @property
    def _session(self):
        return self._app_configuration_repository._session

    async def get_settings(self) -> SettingsResponseSchema:
        id_tax = get_reverse_charge_id_tax(self._session)
        if id_tax is not None and not self._tax_repository.get_tax_by_id(id_tax):
            id_tax = None
        return SettingsResponseSchema(reverse_charge_id_tax=id_tax)

    async def update_settings(self, data: SettingsUpdateSchema) -> SettingsResponseSchema:
        payload = data.model_dump(exclude_unset=True)
        if "reverse_charge_id_tax" not in payload:
            return await self.get_settings()

        id_tax = payload["reverse_charge_id_tax"]
        if id_tax is not None:
            tax = self._tax_repository.get_tax_by_id(id_tax)
            if not tax:
                raise NotFoundException("Tax", id_tax)

        set_reverse_charge_id_tax(self._session, id_tax)
        await invalidate_init_data_cache()
        return SettingsResponseSchema(reverse_charge_id_tax=id_tax)
