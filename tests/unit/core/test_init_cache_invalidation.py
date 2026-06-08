"""Unit test — invalidazione cache init_data (BE-ALIQ-03)."""
import pytest

from src.core.cache import INIT_DATA_CACHE_KEYS, invalidate_init_data_cache


@pytest.mark.asyncio
async def test_invalidate_init_data_cache_deletes_both_keys(monkeypatch):
    deleted = []

    class FakeCacheManager:
        async def delete(self, key: str) -> None:
            deleted.append(key)

    async def fake_get_cache_manager():
        return FakeCacheManager()

    monkeypatch.setattr(
        "src.core.cache.get_cache_manager", fake_get_cache_manager
    )

    await invalidate_init_data_cache()

    assert deleted == list(INIT_DATA_CACHE_KEYS)
