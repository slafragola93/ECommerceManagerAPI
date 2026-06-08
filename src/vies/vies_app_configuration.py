"""
Configurazioni VIES su `app_configurations` (unico store impostazioni app).

Chiavi:
  category = vies
  name     = reverse_charge_id_tax  → value = id_tax (stringa) o vuoto
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.models.app_configuration import AppConfiguration
from src.repository.app_configuration_repository import AppConfigurationRepository

VIES_CONFIG_CATEGORY = "vies"
REVERSE_CHARGE_CONFIG_NAME = "reverse_charge_id_tax"
REVERSE_CHARGE_DESCRIPTION = "ID Tax aliquota 0% reverse charge VIES (eligible)"


def parse_reverse_charge_id_tax(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        return None
    try:
        parsed = int(stripped)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError):
        return None


def get_reverse_charge_id_tax(session: Session) -> Optional[int]:
    repo = AppConfigurationRepository(session)
    row = repo.get_by_name_and_category(
        REVERSE_CHARGE_CONFIG_NAME, VIES_CONFIG_CATEGORY
    )
    return parse_reverse_charge_id_tax(row.value if row else None)


def set_reverse_charge_id_tax(
    session: Session, id_tax: Optional[int]
) -> Optional[int]:
    repo = AppConfigurationRepository(session)
    row = repo.get_by_name_and_category(
        REVERSE_CHARGE_CONFIG_NAME, VIES_CONFIG_CATEGORY
    )
    value_str = str(id_tax) if id_tax is not None else None

    if row:
        row.value = value_str
        repo.update(row)
    else:
        repo.create(
            AppConfiguration(
                id_lang=0,
                category=VIES_CONFIG_CATEGORY,
                name=REVERSE_CHARGE_CONFIG_NAME,
                value=value_str,
                description=REVERSE_CHARGE_DESCRIPTION,
                is_encrypted=False,
            )
        )
    return id_tax
