"""Tests del servicio de archivos Cloudflare R2."""
import io
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.settings import Settings
from app.shared.services.file_service import (
    ALLOWED_IMAGE_EXTENSIONS,
    FileService,
    FileType,
    delete_home_banner_image,
    save_home_banner_image,
    save_profile_image,
    save_transaction_voucher,
)


@pytest.fixture
def mock_s3():
    client = MagicMock()
    with patch("app.shared.services.file_service.boto3.client", return_value=client):
        yield client


@pytest.fixture
def service(mock_s3):
    return FileService()


def _upload_file(filename: str, content: bytes, content_type: str = "image/jpeg") -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(content), headers={"content-type": content_type})


@pytest.mark.asyncio
async def test_save_file_uploads_to_r2_with_correct_key(service, mock_s3):
    key = await service.save_file(
        b"image-bytes",
        "avatar.jpg",
        FileType.PROFILE_IMAGE,
        custom_prefix="profile",
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
    )

    assert key.startswith("profile_images/profile_")
    assert key.endswith(".jpg")
    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args.kwargs
    assert call_kwargs["Key"] == key
    assert call_kwargs["Body"] == b"image-bytes"
    assert call_kwargs["ContentType"] == "image/jpeg"


@pytest.mark.asyncio
async def test_save_file_rejects_invalid_extension(service, mock_s3):
    with pytest.raises(ValueError, match="Extensión '.exe' no permitida"):
        await service.save_file(
            b"bad",
            "virus.exe",
            FileType.GENERAL,
            allowed_extensions={".jpg"},
        )
    mock_s3.put_object.assert_not_called()


@pytest.mark.asyncio
async def test_read_file_returns_content(service, mock_s3):
    body = MagicMock()
    body.read.return_value = b"file-data"
    mock_s3.get_object.return_value = {"Body": body, "ContentType": "image/png"}

    result = await service.read_file("home_banner/banner_es_abc.png")

    assert result == (b"file-data", "image/png")
    mock_s3.get_object.assert_called_once()


@pytest.mark.asyncio
async def test_read_file_returns_none_when_missing(service, mock_s3):
    mock_s3.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
        "GetObject",
    )

    assert await service.read_file("missing/file.jpg") is None


@pytest.mark.asyncio
async def test_delete_file_calls_r2(service, mock_s3):
    assert await service.delete_file("home_popup/popup_es_xyz.webp") is True
    mock_s3.delete_object.assert_called_once()


@pytest.mark.asyncio
async def test_verify_connection_calls_head_bucket(service, mock_s3):
    await service.verify_connection()
    mock_s3.head_bucket.assert_called_once()


@pytest.mark.asyncio
async def test_save_profile_image_returns_key(mock_s3):
    upload = _upload_file("me.jpg", b"profile")

    key = await save_profile_image(upload)

    assert key.startswith("profile_images/profile_")
    assert key.endswith(".jpg")


@pytest.mark.asyncio
async def test_save_profile_image_rejects_invalid_extension(mock_s3):
    upload = _upload_file("me.gif", b"x", "image/gif")  # gif is allowed actually
    upload_bad = _upload_file("me.bmp", b"x", "image/bmp")

    with pytest.raises(ValueError, match="no permitida"):
        await save_profile_image(upload_bad)


@pytest.mark.asyncio
async def test_save_home_banner_image_sanitizes_lang(mock_s3):
    upload = _upload_file("banner.webp", b"banner")

    key = await save_home_banner_image(upload, "es<script>")

    assert key.startswith("home_banner/banner_es")
    assert key.endswith(".webp")


@pytest.mark.asyncio
async def test_save_transaction_voucher_accepts_pdf(mock_s3):
    upload = _upload_file("voucher.pdf", b"%PDF")

    key = await save_transaction_voucher(upload, prefix="payment")

    assert key.startswith("transaction_vouchers/payment_")
    assert key.endswith(".pdf")


@pytest.mark.asyncio
async def test_save_transaction_voucher_rejects_zip(mock_s3):
    upload = _upload_file("archive.zip", b"zip")

    with pytest.raises(ValueError, match="no permitida"):
        await save_transaction_voucher(upload)


@pytest.mark.asyncio
async def test_delete_home_banner_image_noop_on_empty(mock_s3):
    assert await delete_home_banner_image(None) is False
    mock_s3.delete_object.assert_not_called()


def test_settings_media_public_url_with_r2_public_url():
    settings = Settings(
        POSTGRES_DB="db",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        DEBUG=True,
        LOG_LEVEL="info",
        SECRET_KEY="x" * 32,
        R2_ENDPOINT_URL="https://example.r2.cloudflarestorage.com",
        R2_ACCESS_KEY_ID="key",
        R2_SECRET_ACCESS_KEY="secret",
        R2_BUCKET_NAME="bucket",
        R2_PUBLIC_URL="https://cdn.example.com",
        _env_file=None,
    )

    assert settings.media_public_url("profile_images/a.jpg") == (
        "https://cdn.example.com/profile_images/a.jpg"
    )


def test_settings_media_public_url_via_api():
    settings = Settings(
        POSTGRES_DB="db",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        DEBUG=True,
        LOG_LEVEL="info",
        SECRET_KEY="x" * 32,
        PUBLIC_URL="https://api.example.com",
        R2_ENDPOINT_URL="https://example.r2.cloudflarestorage.com",
        R2_ACCESS_KEY_ID="key",
        R2_SECRET_ACCESS_KEY="secret",
        R2_BUCKET_NAME="bucket",
        R2_PUBLIC_URL="",
        _env_file=None,
    )

    assert settings.media_public_url("home_banner/x.webp") == (
        "https://api.example.com/media/home_banner/x.webp"
    )


def test_settings_media_public_url_redirect_mode():
    settings = Settings(
        POSTGRES_DB="db",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        DEBUG=True,
        LOG_LEVEL="info",
        SECRET_KEY="x" * 32,
        R2_ENDPOINT_URL="https://example.r2.cloudflarestorage.com",
        R2_ACCESS_KEY_ID="key",
        R2_SECRET_ACCESS_KEY="secret",
        R2_BUCKET_NAME="web",
        R2_PUBLIC_URL="https://media.example.workers.dev/web",
        _env_file=None,
    )

    assert settings.media_public_url("home_banner/x.webp") == (
        "https://media.example.workers.dev/web/home_banner/x.webp"
    )
