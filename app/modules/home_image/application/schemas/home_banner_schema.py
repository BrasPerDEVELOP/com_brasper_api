from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HomeBannerCreateCmd(BaseModel):
    banner_es: Optional[str] = Field(default=None, max_length=500)
    banner_pr: Optional[str] = Field(default=None, max_length=500)
    banner_en: Optional[str] = Field(default=None, max_length=500)
    enable: bool = Field(default=True)


class HomeBannerUpdateCmd(BaseModel):
    id: UUID
    banner_es: Optional[str] = Field(default=None, max_length=500)
    banner_pr: Optional[str] = Field(default=None, max_length=500)
    banner_en: Optional[str] = Field(default=None, max_length=500)
    enable: Optional[bool] = None


class HomeBannerReadDTO(BaseModel):
    id: UUID
    banner_es: Optional[str] = None
    banner_pr: Optional[str] = None
    banner_en: Optional[str] = None
    enable: bool
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
