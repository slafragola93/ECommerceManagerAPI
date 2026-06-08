"""Unit test — reverse_charge_id_tax su app_configurations (categoria vies)."""
import pytest

from src.core.exceptions import NotFoundException
from src.models.app_configuration import AppConfiguration
from src.models.tax import Tax
from src.repository.app_configuration_repository import AppConfigurationRepository
from src.repository.tax_repository import TaxRepository
from src.schemas.settings_schema import SettingsUpdateSchema
from src.services.routers.settings_service import SettingsService
from src.vies.vies_app_configuration import (
    REVERSE_CHARGE_CONFIG_NAME,
    VIES_CONFIG_CATEGORY,
    get_reverse_charge_id_tax,
)


@pytest.fixture
def settings_service(db_session):
    return SettingsService(
        AppConfigurationRepository(db_session), TaxRepository(db_session)
    )


@pytest.mark.asyncio
class TestSettingsReverseCharge:
    async def test_get_defaults_null_without_row(self, settings_service):
        data = await settings_service.get_settings()
        assert data.reverse_charge_id_tax is None

    async def test_update_reverse_charge_id_tax(self, settings_service, db_session):
        tax = Tax(name="IVA 0% VIES", percentage=0, code="V0", is_default=0)
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        data = await settings_service.update_settings(
            SettingsUpdateSchema(reverse_charge_id_tax=tax.id_tax)
        )
        assert data.reverse_charge_id_tax == tax.id_tax

        row = (
            db_session.query(AppConfiguration)
            .filter(
                AppConfiguration.category == VIES_CONFIG_CATEGORY,
                AppConfiguration.name == REVERSE_CHARGE_CONFIG_NAME,
            )
            .first()
        )
        assert row is not None
        assert row.value == str(tax.id_tax)
        assert get_reverse_charge_id_tax(db_session) == tax.id_tax

    async def test_update_invalid_tax_raises(self, settings_service):
        with pytest.raises(NotFoundException):
            await settings_service.update_settings(
                SettingsUpdateSchema(reverse_charge_id_tax=999999)
            )

    async def test_update_reverse_charge_invalidates_init_cache(
        self, settings_service, db_session, monkeypatch
    ):
        calls = []

        async def fake_invalidate():
            calls.append(True)

        monkeypatch.setattr(
            "src.services.routers.settings_service.invalidate_init_data_cache",
            fake_invalidate,
        )

        tax = Tax(name="IVA 0% RC", percentage=0, code="RC", is_default=0)
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        await settings_service.update_settings(
            SettingsUpdateSchema(reverse_charge_id_tax=tax.id_tax)
        )

        assert calls == [True]
