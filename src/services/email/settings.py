from typing import Dict, Optional

from sqlalchemy.orm import Session

from src.models.app_configuration import AppConfiguration

EMAIL_SETTINGS_CATEGORY = "email_settings"


def load_email_settings(session: Session) -> Dict[str, str]:
    rows = (
        session.query(AppConfiguration)
        .filter(AppConfiguration.category == EMAIL_SETTINGS_CATEGORY)
        .all()
    )
    return {row.name: (row.value or "").strip() for row in rows}


def is_email_enabled(settings: Dict[str, str]) -> bool:
    return settings.get("enabled", "").lower() in {"1", "true", "yes", "on"}


def smtp_ready(settings: Dict[str, str]) -> bool:
    return bool(settings.get("smtp_server") and settings.get("sender_email"))


def default_locale(settings: Dict[str, str], fallback: str = "en") -> str:
    locale = (settings.get("default_locale") or fallback).strip().lower()
    return locale or fallback


def get_setting(settings: Dict[str, str], name: str, default: Optional[str] = None) -> Optional[str]:
    value = settings.get(name)
    if value is None or value == "":
        return default
    return value
