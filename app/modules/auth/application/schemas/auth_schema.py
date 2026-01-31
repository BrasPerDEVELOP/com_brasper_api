from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from typing import Optional


class AuthCreateCmd(BaseModel):
    username: str
    password: str


class AuthReadDTO(BaseModel):
    id: UUID


class UserInfoDTO(BaseModel):
    id: UUID
    names: Optional[str] = None
    lastnames: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None
    document_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TokenInfoDTO(BaseModel):
    token: str
    user: UserInfoDTO


# Request bodies para endpoints HTTP (reset password, etc.)
class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    username: str
    recovery_code: str
    new_password: str
