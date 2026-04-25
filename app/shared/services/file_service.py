"""Servicio escalable para manejo de archivos (imágenes, documentos, etc.)."""
from enum import Enum
from pathlib import Path
from typing import Optional
import uuid

from fastapi import UploadFile


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


# Extensiones permitidas para imágenes
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".odt"}
ALLOWED_TRANSACTION_ATTACHMENT_EXTENSIONS = (
    ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS
)


class FileService:
    """Servicio escalable para archivos - preparado para aiofiles."""

    def __init__(self, base_dir: str = "media", use_async_io: bool = False):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.use_async_io = use_async_io

    async def save_file(
        self,
        file_content: bytes,
        original_filename: str,
        file_type: FileType,
        custom_prefix: Optional[str] = None,
        allowed_extensions: Optional[set] = None,
    ) -> str:
        """Guarda archivo y retorna la ruta relativa."""
        type_dir = self.base_dir / file_type.value
        type_dir.mkdir(parents=True, exist_ok=True)

        file_extension = Path(original_filename).suffix.lower()
        if allowed_extensions and file_extension not in allowed_extensions:
            raise ValueError(
                f"Extensión '{file_extension}' no permitida. "
                f"Permitidas: {', '.join(allowed_extensions)}"
            )

        unique_id = uuid.uuid4().hex[:8]
        filename = f"{custom_prefix}_{unique_id}{file_extension}" if custom_prefix else f"{unique_id}{file_extension}"
        file_path = type_dir / filename

        await self._write_file(file_path, file_content)
        # Retorna ruta relativa a media/ para URL: /media/{result}
        relative = str(file_path.relative_to(self.base_dir)).replace("\\", "/")
        return relative

    async def _write_file(self, file_path: Path, content: bytes) -> None:
        """Método interno para escribir - fácil cambiar a aiofiles."""
        with open(file_path, "wb") as f:
            f.write(content)

    async def delete_file(self, relative_path: str) -> bool:
        """Elimina archivo por ruta relativa a media/ (ej: home_banner/xxx.jpg)."""
        try:
            full_path = self.base_dir / relative_path
            if full_path.exists() and full_path.is_file():
                full_path.unlink()
                return True
            return False
        except Exception:
            return False


file_service = FileService(base_dir="media", use_async_io=False)


# ======================
# Funciones para Home Banner
# ======================

async def save_home_banner_image(
    banner_file: Optional[UploadFile],
    lang: str,
) -> Optional[str]:
    """Guarda imagen de banner home (es/pr/en)."""
    if not banner_file:
        return None

    file_content = await banner_file.read()
    if not file_content:
        return None

    ext = Path(banner_file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"Extensión '{ext}' no permitida para banner. "
            f"Permitidas: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    safe_lang = "".join(c for c in lang if c.isalnum() or c in "._-")[:5]
    return await file_service.save_file(
        file_content=file_content,
        original_filename=banner_file.filename or "banner",
        file_type=FileType.HOME_BANNER,
        custom_prefix=f"banner_{safe_lang}",
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
    )


async def delete_home_banner_image(image_path: Optional[str]) -> bool:
    """Elimina imagen de banner home."""
    if not image_path:
        return False
    return await file_service.delete_file(image_path)


# ======================
# Funciones para Home Popup
# ======================

async def save_home_popup_image(
    popup_file: Optional[UploadFile],
    lang: str,
) -> Optional[str]:
    """Guarda imagen de popup home (es/pr/en)."""
    if not popup_file:
        return None

    file_content = await popup_file.read()
    if not file_content:
        return None

    ext = Path(popup_file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"Extensión '{ext}' no permitida para popup. "
            f"Permitidas: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    safe_lang = "".join(c for c in lang if c.isalnum() or c in "._-")[:5]
    return await file_service.save_file(
        file_content=file_content,
        original_filename=popup_file.filename or "popup",
        file_type=FileType.HOME_POPUP,
        custom_prefix=f"popup_{safe_lang}",
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
    )


async def delete_home_popup_image(image_path: Optional[str]) -> bool:
    """Elimina imagen de popup home."""
    if not image_path:
        return False
    return await file_service.delete_file(image_path)


# ======================
# Funciones para Profile Image (usuario)
# ======================

async def save_profile_image(profile_file: Optional[UploadFile]) -> Optional[str]:
    """Guarda imagen de perfil de usuario. Retorna ruta relativa (ej: profile_images/profile_xxx.jpg)."""
    if not profile_file:
        return None

    file_content = await profile_file.read()
    if not file_content:
        return None

    ext = Path(profile_file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"Extensión '{ext}' no permitida para imagen de perfil. "
            f"Permitidas: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    return await file_service.save_file(
        file_content=file_content,
        original_filename=profile_file.filename or "profile",
        file_type=FileType.PROFILE_IMAGE,
        custom_prefix="profile",
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
    )


async def delete_profile_image(image_path: Optional[str]) -> bool:
    """Elimina imagen de perfil de usuario."""
    if not image_path:
        return False
    return await file_service.delete_file(image_path)


# ======================
# Funciones para Transaction Voucher
# ======================

async def save_transaction_voucher(
    voucher_file: Optional[UploadFile],
    prefix: str = "voucher",
) -> Optional[str]:
    """Guarda adjunto de transacción (voucher/checklist). Retorna ruta relativa."""
    if not voucher_file or not voucher_file.filename:
        return None

    file_content = await voucher_file.read()
    if not file_content:
        return None

    ext = Path(voucher_file.filename).suffix.lower()
    if ext not in ALLOWED_TRANSACTION_ATTACHMENT_EXTENSIONS:
        raise ValueError(
            f"Extensión '{ext}' no permitida para adjuntos de transacción. "
            f"Permitidas: {', '.join(sorted(ALLOWED_TRANSACTION_ATTACHMENT_EXTENSIONS))}"
        )

    return await file_service.save_file(
        file_content=file_content,
        original_filename=voucher_file.filename,
        file_type=FileType.TRANSACTION_VOUCHER,
        custom_prefix=prefix,
        allowed_extensions=ALLOWED_TRANSACTION_ATTACHMENT_EXTENSIONS,
    )
