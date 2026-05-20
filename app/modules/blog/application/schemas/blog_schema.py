# app/modules/blog/application/schemas/blog_schema.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BlogCreateCmd(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255)
    excerpt: Optional[str] = None
    content: str = Field(..., min_length=1)
    category: Optional[str] = Field(default=None, max_length=100)
    public_id: Optional[str] = Field(default=None, max_length=100)
    read_time: Optional[int] = Field(default=None, ge=0)
    date: Optional[datetime] = None
    language: str = Field(..., min_length=2, max_length=10)
    enable: bool = Field(default=True)


class BlogUpdateCmd(BaseModel):
    id: UUID
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=255)
    excerpt: Optional[str] = None
    content: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = Field(default=None, max_length=100)
    public_id: Optional[str] = Field(default=None, max_length=100)
    read_time: Optional[int] = Field(default=None, ge=0)
    date: Optional[datetime] = None
    language: Optional[str] = Field(default=None, min_length=2, max_length=10)
    enable: Optional[bool] = None


class BlogReadDTO(BaseModel):
    id: UUID
    title: str
    slug: str
    excerpt: Optional[str] = None
    content: str
    category: Optional[str] = None
    public_id: Optional[str] = None
    read_time: Optional[int] = None
    date: Optional[datetime] = None
    language: str
    enable: bool
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BlogListPage(BaseModel):
    items: list[BlogReadDTO]
    total: int
    skip: int
    limit: int
    has_next: bool
    has_previous: bool
