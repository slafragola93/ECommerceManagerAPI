"""Fixture condivise integration API v1."""
import pytest
from sqlalchemy import func

from src.repository.corrispettivo_repository import CorrispettivoRepository


@pytest.fixture(autouse=True)
def sqlite_corrispettivi_local_day(monkeypatch):
    """SQLite in-memory non ha convert_tz: allinea repository corrispettivi ai test unit."""
    monkeypatch.setattr(
        CorrispettivoRepository,
        "_local_day_expr",
        lambda self, column: func.date(column),
    )
