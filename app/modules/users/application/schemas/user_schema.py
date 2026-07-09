from datetime import datetime
from fastapi import File, Form, UploadFile
from pydantic import BaseModel, EmailStr, ConfigDict, Field, model_validator, field_validator, field_serializer
from uuid import UUID
from typing import Optional

from app.modules.auth.application.schemas.auth_schema import AuthCreateCmd
from app.modules.auth.domain.permissions import default_permissions_for_role
from app.modules.users.domain.enums import UserRole, DocumentType, PhoneCode
from app.shared.media import to_media_url

# Máximo 15 dígitos para teléfono
phone_max_digits = 999_999_999_999_999


def _phone_empty_to_none(v):
    """Convierte '' o None a None; permite int o str numérico."""
    if v is None or v == "":
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class UserCreateCmd(BaseModel):
    """Campos para crear usuario. Todos opcionales."""
    names: Optional[str] = None
    lastnames: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    profile_image: Optional[str] = None
    document_number: Optional[str] = None
    document_type: Optional[DocumentType] = None
    is_agent: Optional[bool] = None
    role: Optional[UserRole] = None
    auth_id: Optional[UUID] = None
    phone: Optional[int] = Field(None, le=phone_max_digits, description="Hasta 15 dígitos")
    code_phone: Optional[PhoneCode] = None

    @field_validator("phone", mode="before")
    @classmethod
    def phone_empty_to_none(cls, v):
        return _phone_empty_to_none(v)

    def to_auth_cmd(self) -> Optional[AuthCreateCmd]:
        if self.email and self.password:
            return AuthCreateCmd(username=self.email, password=self.password)
        return None

    @classmethod
    def from_form(
        cls,
        names: Optional[str] = Form(None),
        lastnames: Optional[str] = Form(None),
        email: Optional[EmailStr] = Form(None),
        password: Optional[str] = Form(None),
        profile_image: Optional[UploadFile] = File(None),
        document_number: Optional[str] = Form(None),
        document_type: Optional[DocumentType] = Form(None),
        is_agent: Optional[bool] = Form(None),
        role: Optional[UserRole] = Form(None),
        phone: Optional[int] = Form(None),
        code_phone: Optional[PhoneCode] = Form(None),
    ) -> tuple["UserCreateCmd", Optional[UploadFile]]:
        cmd = cls(
            names=names,
            lastnames=lastnames,
            email=email,
            password=password,
            document_number=document_number,
            document_type=document_type,
            is_agent=is_agent,
            role=role,
            phone=phone,
            code_phone=code_phone,
        )
        return cmd, profile_image


class UserUpdateCmd(BaseModel):
    id: UUID
    names: Optional[str] = None
    lastnames: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None
    document_number: Optional[str] = None
    document_type: Optional[DocumentType] = None
    is_agent: Optional[bool] = None
    role: Optional[UserRole] = None
    phone: Optional[int] = Field(None, le=phone_max_digits, description="Hasta 15 dígitos")
    code_phone: Optional[PhoneCode] = None

    @field_validator("phone", mode="before")
    @classmethod
    def phone_empty_to_none(cls, v):
        return _phone_empty_to_none(v)

    @classmethod
    def from_form(
        cls,
        id: str = Form(..., description="UUID del usuario"),
        names: Optional[str] = Form(None),
        lastnames: Optional[str] = Form(None),
        email: Optional[EmailStr] = Form(None),
        profile_image: Optional[UploadFile] = File(None),
        document_number: Optional[str] = Form(None),
        document_type: Optional[DocumentType] = Form(None),
        is_agent: Optional[bool] = Form(None),
        role: Optional[UserRole] = Form(None),
        phone: Optional[int] = Form(None),
        code_phone: Optional[PhoneCode] = Form(None),
    ) -> tuple["UserUpdateCmd", Optional[UploadFile]]:
        cmd = cls(
            id=UUID(id),
            names=names,
            lastnames=lastnames,
            email=email,
            document_number=document_number,
            document_type=document_type,
            is_agent=is_agent,
            role=role,
            phone=phone,
            code_phone=code_phone,
        )
        return cmd, profile_image


class UpdateCurrentUserCmd(BaseModel):
    """Campos actualizables para PUT /auth/me (usuario autenticado)."""
    names: Optional[str] = None
    lastnames: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None
    document_number: Optional[str] = None
    document_type: Optional[DocumentType] = None
    is_agent: Optional[bool] = None
    role: Optional[UserRole] = None
    phone: Optional[int] = Field(None, le=phone_max_digits, description="Hasta 15 dígitos")
    code_phone: Optional[PhoneCode] = None

    @field_validator("phone", mode="before")
    @classmethod
    def phone_empty_to_none(cls, v):
        return _phone_empty_to_none(v)


# Valores por defecto cuando el campo es null en BD
DEFAULT_PROFILE_IMAGE = "profile_images/placeholder.svg"
DEFAULT_DOCUMENT_TYPE = "dni"
DEFAULT_CODE_PHONE = "pe"


class UserReadDTO(BaseModel):
    id: UUID
    names: Optional[str] = None
    lastnames: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None
    document_number: Optional[str] = None
    document_type: Optional[DocumentType] = None
    is_agent: Optional[bool] = None
    role: Optional[UserRole] = None
    phone: Optional[int] = None
    code_phone: Optional[PhoneCode] = None
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime
    permissions: list[str] = []
    must_change_password: bool = False

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("profile_image")
    def _serialize_profile_media(self, value, _info):
        return to_media_url(value)

    @model_validator(mode="after")
    def set_defaults_when_null(self):
        if self.profile_image is None:
            object.__setattr__(self, "profile_image", DEFAULT_PROFILE_IMAGE)
        if self.document_type is None:
            object.__setattr__(self, "document_type", DocumentType[DEFAULT_DOCUMENT_TYPE])
        if self.code_phone is None:
            object.__setattr__(self, "code_phone", PhoneCode[DEFAULT_CODE_PHONE])
        if not self.permissions:
            object.__setattr__(
                self,
                "permissions",
                default_permissions_for_role(self.role.value if self.role else None),
            )
        return self


class UserReadGeneralDTO(BaseModel):
    """DTO con todos los campos del modelo User (excepto auth_id)."""
    id: UUID
    names: Optional[str] = None
    lastnames: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None
    document_number: Optional[str] = None
    document_type: Optional[DocumentType] = None
    is_agent: Optional[bool] = None
    role: Optional[UserRole] = None
    phone: Optional[int] = None
    code_phone: Optional[PhoneCode] = None
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime
    permissions: list[str] = []
    must_change_password: bool = False

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("profile_image")
    def _serialize_profile_media(self, value, _info):
        return to_media_url(value)

    @model_validator(mode="after")
    def set_defaults_when_null(self):
        if self.profile_image is None:
            object.__setattr__(self, "profile_image", DEFAULT_PROFILE_IMAGE)
        if self.document_type is None:
            object.__setattr__(self, "document_type", DocumentType[DEFAULT_DOCUMENT_TYPE])
        if self.code_phone is None:
            object.__setattr__(self, "code_phone", PhoneCode[DEFAULT_CODE_PHONE])
        if not self.permissions:
            object.__setattr__(
                self,
                "permissions",
                default_permissions_for_role(self.role.value if self.role else None),
            )
        return self


class UserNameDTO(BaseModel):
    """DTO mínimo para listar usuarios (id, nombres, apellidos)."""
    id: UUID
    names: Optional[str] = None
    lastnames: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
