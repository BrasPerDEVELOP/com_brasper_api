from fastapi import File, Form, UploadFile
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from uuid import UUID
from typing import Optional

from app.modules.auth.application.schemas.auth_schema import AuthCreateCmd
from app.modules.users.domain.enums import UserRole, DocumentType, PhoneCode

# Máximo 15 dígitos para teléfono
phone_max_digits = 999_999_999_999_999


class UserCreateCmd(BaseModel):
    names: Optional[str] = None
    lastnames: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    profile_image: Optional[str] = None
    document_number: Optional[str] = None
    document_type: Optional[DocumentType] = None
    role: Optional[UserRole] = None
    auth_id: Optional[UUID] = None
    phone: Optional[int] = Field(None, le=phone_max_digits, description="Hasta 15 dígitos")
    code_phone: Optional[PhoneCode] = None

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
    role: Optional[UserRole] = None
    phone: Optional[int] = Field(None, le=phone_max_digits, description="Hasta 15 dígitos")
    code_phone: Optional[PhoneCode] = None


class UserReadDTO(BaseModel):
    id: UUID
    names: Optional[str] = None
    lastnames: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None
    document_number: Optional[str] = None
    document_type: Optional[DocumentType] = None
    role: Optional[UserRole] = None
    phone: Optional[int] = None
    code_phone: Optional[PhoneCode] = None

    model_config = ConfigDict(from_attributes=True)


class UserReadGeneralDTO(BaseModel):
    id: UUID
    names: Optional[str] = None
    lastnames: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserNameDTO(BaseModel):
    id: UUID
    names: Optional[str] = None
    lastnames: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
