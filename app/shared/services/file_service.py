"""Servicio de archivos en Cloudflare R2 (S3-compatible)."""
import asyncio
import mimetypes
from enum import Enum
from pathlib import Path
from typing import Optional
import uuid

import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.settings import get_settings


class FileType(Enum):
    """Tipos de archivos por contexto."""
    PROFILE_IMAGE = "profile_images"
    REPOSITORY_IMAGE = "repository_images"
    UNITY_IMAGE = "unity_images"
    UNITY_DRAWING = "unity_drawings"
    IMAGE_LOT = "image_lot"
    PROJECT_IMAGE = "project_images"
    COMMERCIAL_IMAGE = "commercial_images"
    DOCUMENT = "documents"
    GENERAL = "general"
    SANITATION_FILE = "sanitation_file"
    LEVEL_DRAWING = "level_drawing"
    APPROVAL_LETTER = "approval_letter"
    ORGANISATION_LOGO = "organisation_logo"
    TEMPLATE_DOCUMENT = "template_documents"
    SCORE_FILE = "score_files"
    HOME_BANNER = "home_banner"
    HOME_POPUP = "home_popup"
    TRANSACTION_VOUCHER = "transaction_vouchers"
    DATA_IMPORT = "data_import"


ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".odt"}
ALLOWED_TRANSACTION_ATTACHMENT_EXTENSIONS = (
    ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS
)


class FileService:
    """Almacenamiento de archivos en Cloudflare R2."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._s3_client = None

    def _get_s3_client(self):
        if self._s3_client is None:
            settings = self._settings
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=settings.R2_ENDPOINT_URL,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",
            )
        return self._s3_client

    def _guess_content_type(self, key: str) -> str:
        content_type, _ = mimetypes.guess_type(key)
        return content_type or "application/octet-stream"

    async def verify_connection(self) -> None:
        """Comprueba acceso al bucket R2 al iniciar la aplicación."""
        client = self._get_s3_client()
        bucket = self._settings.R2_BUCKET_NAME

        def _head_bucket() -> None:
            client.head_bucket(Bucket=bucket)

        await asyncio.to_thread(_head_bucket)

    async def save_file(
        self,
        file_content: bytes,
        original_filename: str,
        file_type: FileType,
        custom_prefix: Optional[str] = None,
        allowed_extensions: Optional[set] = None,
    ) -> str:
        """Guarda archivo en R2 y retorna la key relativa (ej: profile_images/profile_xxx.jpg)."""
        file_extension = Path(original_filename).suffix.lower()
        if allowed_extensions and file_extension not in allowed_extensions:
            raise ValueError(
                f"Extensión '{file_extension}' no permitida. "
                f"Permitidas: {', '.join(allowed_extensions)}"
            )

        unique_id = uuid.uuid4().hex[:8]
        filename = (
            f"{custom_prefix}_{unique_id}{file_extension}"
            if custom_prefix
            else f"{unique_id}{file_extension}"
        )
        key = f"{file_type.value}/{filename}"
        await self._write_r2(key, file_content)
        return key

    async def _write_r2(self, key: str, content: bytes) -> None:
        client = self._get_s3_client()
        bucket = self._settings.R2_BUCKET_NAME

        def _put_object() -> None:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=content,
                ContentType=self._guess_content_type(key),
            )

        await asyncio.to_thread(_put_object)

    async def read_file(self, relative_path: str) -> Optional[tuple[bytes, str]]:
        """Lee archivo por key relativa. Retorna (contenido, content_type) o None."""
        client = self._get_s3_client()
        bucket = self._settings.R2_BUCKET_NAME

        def _get_object() -> Optional[tuple[bytes, str]]:
            try:
                response = client.get_object(Bucket=bucket, Key=relative_path)
                body = response["Body"].read()
                content_type = response.get("ContentType") or self._guess_content_type(relative_path)
                return body, content_type
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                    return None
                raise

        return await asyncio.to_thread(_get_object)

    async def delete_file(self, relative_path: str) -> bool:
        """Elimina archivo por key relativa (ej: home_banner/xxx.jpg)."""
        client = self._get_s3_client()
        bucket = self._settings.R2_BUCKET_NAME

        def _delete_object() -> bool:
            try:
                client.delete_object(Bucket=bucket, Key=relative_path)
                return True
            except ClientError:
                return False

        return await asyncio.to_thread(_delete_object)

    async def upload_local_file(self, local_path: Path, key: str) -> None:
        """Sube un archivo del disco local a R2 (útil para migraciones)."""
        content = await asyncio.to_thread(local_path.read_bytes)
        await self._write_r2(key, content)


file_service = FileService()


async def save_upload_file(
    upload_file: Optional[UploadFile],
    file_type: FileType,
    custom_prefix: Optional[str] = None,
    allowed_extensions: Optional[set] = None,
) -> Optional[str]:
    """Guarda un UploadFile genérico en R2."""
    if not upload_file:
        return None

    file_content = await upload_file.read()
    if not file_content:
        return None

    return await file_service.save_file(
        file_content=file_content,
        original_filename=upload_file.filename or "file",
        file_type=file_type,
        custom_prefix=custom_prefix,
        allowed_extensions=allowed_extensions,
    )


async def save_home_banner_image(
    banner_file: Optional[UploadFile],
    lang: str,
) -> Optional[str]:
    """Guarda imagen de banner home (es/pr/en)."""
    ext = Path(banner_file.filename or "").suffix.lower() if banner_file else ""
    if banner_file and ext and ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"Extensión '{ext}' no permitida para banner. "
            f"Permitidas: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    safe_lang = "".join(c for c in lang if c.isalnum() or c in "._-")[:5]
    return await save_upload_file(
        banner_file,
        file_type=FileType.HOME_BANNER,
        custom_prefix=f"banner_{safe_lang}",
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
    )


async def delete_home_banner_image(image_path: Optional[str]) -> bool:
    """Elimina imagen de banner home."""
    if not image_path:
        return False
    return await file_service.delete_file(image_path)


async def save_home_popup_image(
    popup_file: Optional[UploadFile],
    lang: str,
) -> Optional[str]:
    """Guarda imagen de popup home (es/pr/en)."""
    ext = Path(popup_file.filename or "").suffix.lower() if popup_file else ""
    if popup_file and ext and ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"Extensión '{ext}' no permitida para popup. "
            f"Permitidas: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    safe_lang = "".join(c for c in lang if c.isalnum() or c in "._-")[:5]
    return await save_upload_file(
        popup_file,
        file_type=FileType.HOME_POPUP,
        custom_prefix=f"popup_{safe_lang}",
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
    )


async def delete_home_popup_image(image_path: Optional[str]) -> bool:
    """Elimina imagen de popup home."""
    if not image_path:
        return False
    return await file_service.delete_file(image_path)


async def save_profile_image(profile_file: Optional[UploadFile]) -> Optional[str]:
    """Guarda imagen de perfil de usuario. Retorna key relativa (ej: profile_images/profile_xxx.jpg)."""
    ext = Path(profile_file.filename or "").suffix.lower() if profile_file else ""
    if profile_file and ext and ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"Extensión '{ext}' no permitida para imagen de perfil. "
            f"Permitidas: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    return await save_upload_file(
        profile_file,
        file_type=FileType.PROFILE_IMAGE,
        custom_prefix="profile",
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
    )


async def delete_profile_image(image_path: Optional[str]) -> bool:
    """Elimina imagen de perfil de usuario."""
    if not image_path:
        return False
    return await file_service.delete_file(image_path)


async def save_transaction_voucher(
    voucher_file: Optional[UploadFile],
    prefix: str = "voucher",
) -> Optional[str]:
    """Guarda adjunto de transacción (voucher/checklist). Retorna key relativa."""
    if not voucher_file or not voucher_file.filename:
        return None

    ext = Path(voucher_file.filename).suffix.lower()
    if ext not in ALLOWED_TRANSACTION_ATTACHMENT_EXTENSIONS:
        raise ValueError(
            f"Extensión '{ext}' no permitida para adjuntos de transacción. "
            f"Permitidas: {', '.join(sorted(ALLOWED_TRANSACTION_ATTACHMENT_EXTENSIONS))}"
        )

    return await save_upload_file(
        voucher_file,
        file_type=FileType.TRANSACTION_VOUCHER,
        custom_prefix=prefix,
        allowed_extensions=ALLOWED_TRANSACTION_ATTACHMENT_EXTENSIONS,
    )
