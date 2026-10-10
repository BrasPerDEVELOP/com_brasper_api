# app/modules/billing/infrastructure/apisunat_client.py
"""Cliente HTTP de APISUNAT sobre ``httpx``.

Contrato (docs.apisunat.com, consultado 2026-10-03):

- ``POST /personas/v1/sendBill``   body: personaId, personaToken, fileName, documentBody, customerEmail?
  → ``{"status": "PENDIENTE", "documentId": "..."}``; cualquier otro status es error.
- ``GET  /documents/{id}/getById`` → status, fileName, xml, cdr, faults, notes, production, ...
- ``GET  /documents/getAll?personaId&personaToken&serie&number&type&limit``
- ``GET  /documents/{id}/getPDF/{A4|A5|ticket58mm|ticket80mm}/{fileName}.pdf``
- ``POST /personas/v1/voidBill``   body: personaId, personaToken, documentId, reason (3–100)
- ``POST /personas/lastDocument``  body: personaId, personaToken, type (2 dígitos), serie (4)

``send_bill`` y ``void_bill`` NO se reintentan: no son idempotentes. Un timeout
se propaga como ``ApisunatTimeout`` para que el caso de uso verifique con
``find_by_file_name`` antes de volver a enviar.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx

from app.modules.billing.interfaces.apisunat_client import (
    ApisunatClientInterface,
    ApisunatError,
    ApisunatTimeout,
    DocumentInfo,
    SendBillResult,
)

logger = logging.getLogger(__name__)

_PERSONA_TOKEN_RE = re.compile(r"(personaToken=)[^&\s\"']+")


def redact_persona_token(text: str) -> str:
    return _PERSONA_TOKEN_RE.sub(lambda m: m.group(1) + "***", text)


class _RedactPersonaTokenFilter(logging.Filter):
    """Oculta ``personaToken`` en los logs de httpx.

    ``GET /documents/getAll`` exige el token en la query string (así lo define
    APISUNAT) y httpx registra la URL completa a nivel INFO
    (``HTTP Request: GET https://...&personaToken=...``).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str) and "personaToken=" in record.msg:
            record.msg = redact_persona_token(record.msg)
        if isinstance(record.args, tuple) and record.args:
            record.args = tuple(
                redact_persona_token(str(arg)) if "personaToken=" in str(arg) else arg
                for arg in record.args
            )
        return True


def install_log_redaction() -> None:
    for name in ("httpx", "httpcore"):
        target = logging.getLogger(name)
        if not any(isinstance(f, _RedactPersonaTokenFilter) for f in target.filters):
            target.addFilter(_RedactPersonaTokenFilter())


install_log_redaction()


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def document_info_from_payload(document_id: str, payload: dict[str, Any]) -> DocumentInfo:
    return DocumentInfo(
        document_id=str(payload.get("_id") or payload.get("documentId") or document_id),
        status=str(payload.get("status") or ""),
        file_name=payload.get("fileName"),
        xml_url=payload.get("xml"),
        cdr_url=payload.get("cdr"),
        faults=_as_list(payload.get("faults")),
        notes=_as_list(payload.get("notes")),
        production=payload.get("production"),
        raw=payload,
    )


class ApisunatHttpClient(ApisunatClientInterface):
    def __init__(
        self,
        *,
        base_url: str,
        persona_id: str,
        persona_token: str,
        timeout_seconds: float = 30.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._persona_id = persona_id
        self._persona_token = persona_token
        self._timeout = timeout_seconds
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
            headers={"Accept": "application/json"},
        )

    def _credentials(self) -> dict[str, str]:
        return {"personaId": self._persona_id, "personaToken": self._persona_token}

    @staticmethod
    def _json_or_error(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise ApisunatError(
                f"APISUNAT respondió {response.status_code} sin JSON: {response.text[:200]}"
            ) from exc
        if not isinstance(data, dict):
            raise ApisunatError(f"APISUNAT respondió un cuerpo inesperado: {str(data)[:200]}")
        return data

    async def _post(self, path: str, body: dict[str, Any], *, idempotent: bool) -> dict[str, Any]:
        try:
            async with self._client() as client:
                response = await client.post(path, json=body)
        except httpx.TimeoutException as exc:
            if idempotent:
                raise ApisunatError(f"Timeout en {path}") from exc
            raise ApisunatTimeout(f"Timeout en {path}: no se sabe si el documento llegó") from exc
        except httpx.HTTPError as exc:
            raise ApisunatError(f"Error de red en {path}: {exc}") from exc
        data = self._json_or_error(response)
        if response.status_code >= 500:
            raise ApisunatError(f"APISUNAT respondió {response.status_code} en {path}: {data}")
        return data

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> httpx.Response:
        try:
            async with self._client() as client:
                response = await client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise ApisunatError(f"Error de red en {path}: {exc}") from exc
        if response.status_code >= 500:
            raise ApisunatError(f"APISUNAT respondió {response.status_code} en {path}")
        return response

    # --- Emisión ------------------------------------------------------------
    async def send_bill(
        self,
        *,
        file_name: str,
        document_body: dict[str, Any],
        customer_email: Optional[str] = None,
        reference: Optional[str] = None,
    ) -> SendBillResult:
        body: dict[str, Any] = {
            **self._credentials(),
            "fileName": file_name,
            "documentBody": document_body,
        }
        if customer_email:
            body["customerEmail"] = customer_email
        if reference:
            body["reference"] = reference
        data = await self._post("/personas/v1/sendBill", body, idempotent=False)
        status = str(data.get("status") or "ERROR")
        return SendBillResult(
            status=status,
            document_id=data.get("documentId"),
            error=data.get("error") if status != "PENDIENTE" else None,
            raw=data,
        )

    async def void_bill(self, *, document_id: str, reason: str) -> SendBillResult:
        body = {**self._credentials(), "documentId": document_id, "reason": reason}
        data = await self._post("/personas/v1/voidBill", body, idempotent=False)
        status = str(data.get("status") or "ERROR")
        return SendBillResult(
            status=status,
            document_id=data.get("documentId"),
            error=data.get("error") if status != "PENDIENTE" else None,
            raw=data,
        )

    async def last_document(self, *, document_type: str, series: str) -> dict[str, Any]:
        body = {**self._credentials(), "type": document_type, "serie": series}
        return await self._post("/personas/lastDocument", body, idempotent=True)

    # --- Consulta -----------------------------------------------------------
    async def get_by_id(self, document_id: str) -> DocumentInfo:
        response = await self._get(f"/documents/{document_id}/getById")
        if response.status_code == 404:
            raise ApisunatError(f"Documento {document_id} no existe en APISUNAT")
        data = self._json_or_error(response)
        return document_info_from_payload(document_id, data)

    async def find_by_file_name(self, file_name: str) -> Optional[DocumentInfo]:
        parts = file_name.split("-")
        if len(parts) != 4:
            raise ValueError(f"fileName inválido: {file_name}")
        _ruc, document_type, series, number = parts
        params = {
            **self._credentials(),
            "type": document_type,
            "serie": series,
            # APISUNAT filtra por el número como texto de 8 dígitos ("00000001").
            "number": f"{int(number):08d}",
            "limit": 5,
        }
        response = await self._get("/documents/getAll", params=params)
        data = response.json() if response.content else []
        items = data if isinstance(data, list) else _as_list(data.get("documents") or data.get("data"))
        for item in items:
            if isinstance(item, dict) and item.get("fileName") == file_name:
                return document_info_from_payload(str(item.get("_id") or ""), item)
        return None

    async def get_pdf(self, document_id: str, *, pdf_format: str, file_name: str) -> bytes:
        response = await self._get(f"/documents/{document_id}/getPDF/{pdf_format}/{file_name}.pdf")
        if response.status_code != 200:
            raise ApisunatError(f"getPDF respondió {response.status_code} para {document_id}")
        return response.content
