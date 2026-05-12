from pydantic import BaseModel, EmailStr, ConfigDict, model_validator
from uuid import UUID
from typing import Optional

from app.modules.auth.domain.permissions import default_permissions_for_role


class AuthCreateCmd(BaseModel):
    username: str
    password: str


class AuthReadDTO(BaseModel):
    id: UUID


DEFAULT_PROFILE_IMAGE = "profile_images/placeholder.svg"


class UserInfoDTO(BaseModel):
    id: UUID
    names: Optional[str] = None
    lastnames: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None
    document_number: Optional[str] = None
    role: Optional[str] = None
    permissions: list[str] = []
    must_change_password: bool = False

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def set_default_profile_image(self):
        if self.profile_image is None:
            object.__setattr__(self, "profile_image", DEFAULT_PROFILE_IMAGE)
        if not self.permissions:
            object.__setattr__(self, "permissions", default_permissions_for_role(self.role))
        return self


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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AdminResetPasswordRequest(BaseModel):
    new_password: str
