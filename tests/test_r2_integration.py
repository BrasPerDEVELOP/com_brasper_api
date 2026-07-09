"""Prueba de integración contra Cloudflare R2 real (requiere .env configurado)."""
import pytest

from app.shared.services.file_service import FileType, file_service


@pytest.mark.integration
@pytest.mark.asyncio
async def test_r2_live_save_read_delete_cycle():
    key = await file_service.save_file(
        b"integration-test",
        "probe.jpg",
        FileType.GENERAL,
        custom_prefix="integration",
        allowed_extensions={".jpg"},
    )

    try:
        assert key.startswith("general/integration_")
        data = await file_service.read_file(key)
        assert data is not None
        assert data[0] == b"integration-test"
        assert data[1] == "image/jpeg"
    finally:
        await file_service.delete_file(key)

    assert await file_service.read_file(key) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_r2_live_verify_connection():
    await file_service.verify_connection()
