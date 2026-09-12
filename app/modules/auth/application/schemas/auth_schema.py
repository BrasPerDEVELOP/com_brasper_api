from pydantic import BaseModel, EmailStr, ConfigDict, model_validator, computed_field
from uuid import UUID
from typing import Optional



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
    permissions_granted: list[str] = []
    permissions_revoked: list[str] = []
    permissions: list[str] = []
    must_change_password: bool = False

    @computed_field
    @property
    def permissions_customized(self) -> bool:
        return bool(self.permissions_granted or self.permissions_revoked)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def set_default_profile_image(self):
        if self.profile_image is None:
            object.__setattr__(self, "profile_image", DEFAULT_PROFILE_IMAGE)
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
