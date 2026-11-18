import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DocumentLookupRequest(BaseModel):
    document_type: Literal["dni", "ruc", "cpf", "cnpj"]
    document_number: str = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def normalize_document(self):
        number = re.sub(r"[\s./-]", "", self.document_number).upper()
        pattern = {
            "dni": r"[0-9]{8}", "ruc": r"[0-9]{11}",
            "cpf": r"[0-9]{11}", "cnpj": r"[A-Z0-9]{12}[0-9]{2}",
        }[self.document_type]
        if not re.fullmatch(pattern, number):
            raise ValueError("El número no tiene el formato del tipo de documento seleccionado")
        self.document_number = number
        return self


class DocumentLookupResult(BaseModel):
    document_type: str
    document_number: str
    names: str
    lastnames: str = ""
    source: Literal["apiperu", "cpfcnpj"]
