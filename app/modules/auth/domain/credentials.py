# com_build_api/app/auth/domain/credentials.py
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator
import re

class Credentials(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    username: str
    password: str
    recovery_code: Optional[str] = None
    token: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator('username')
    @classmethod
    def username_must_be_valid(cls, v):
        email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        username_pattern = r'^[a-zA-Z0-9_]{3,255}$'
        
        if re.match(email_pattern, v) or re.match(username_pattern, v):
            return v
        
        raise ValueError('Username must be alphanumeric or a valid email address')

    class Config:
        from_attributes = True
