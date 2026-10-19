from pydantic import BaseModel, EmailStr, Field, field_validator


class CampaignInput(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=100000)
    emails: list[EmailStr] = Field(min_length=1, max_length=10000)
    consent_confirmed: bool

    @field_validator("name", "subject", "body")
    @classmethod
    def clean_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("El campo no puede estar vacío")
        return value

    @field_validator("subject")
    @classmethod
    def no_headers(cls, value):
        if "\r" in value or "\n" in value:
            raise ValueError("Asunto inválido")
        return value


class TestInput(BaseModel):
    email: EmailStr
