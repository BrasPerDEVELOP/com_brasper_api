"""Read-only document lookup. Never persists users or treats a name as KYC approval."""
import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.modules.users.application.schemas.document_lookup import (
    DocumentLookupRequest, DocumentLookupResult,
)


class DocumentLookupError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(url: str, token: str | None, body: dict | None) -> tuple[int, dict]:
    # urllib does not log request URLs. CPF.CNPJ embeds its credential in the
    # path: never use exception text, raw responses, or URL logging here.
    headers = {"Accept": "application/json", "User-Agent": "Brasper/1.0"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers)
    try:
        try:
            response = build_opener(_NoRedirect()).open(request, timeout=15)
        except HTTPError as exc:
            response = exc
        with response:
            status = response.code
            raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("Oversized response")
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            payload = {}
        return status, payload if isinstance(payload, dict) else {}
    except (URLError, TimeoutError, OSError, ValueError):
        raise DocumentLookupError(503, "No se pudo consultar el documento. Intenta nuevamente o completa los datos manualmente.") from None


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


async def lookup_document(request: DocumentLookupRequest, settings) -> DocumentLookupResult:
    kind, number = request.document_type, request.document_number
    peru = kind in {"dni", "ruc"}
    token = settings.APIPERU_TOKEN if peru else settings.CPFCNPJ_TOKEN
    base = (settings.APIPERU_BASE_URL if peru else settings.CPFCNPJ_BASE_URL).rstrip("/")
    allowed = {"apiperu.dev", "api.apiperu.dev"} if peru else {"api.cpfcnpj.com.br"}
    parsed = urlparse(base)
    if not token or parsed.scheme != "https" or parsed.hostname not in allowed or parsed.username or parsed.query or parsed.fragment:
        raise DocumentLookupError(503, "La consulta de este documento no está configurada. Contacta al administrador.")
    # Basic name-only packages, not contact enrichment or credit checks.
    url = f"{base}/{kind}" if peru else f"{base}/{token}/{1 if kind == 'cpf' else 4}/{number}"
    status, payload = await asyncio.to_thread(_fetch, url, token if peru else None, {kind: number} if peru else None)
    code = str(payload.get("erroCodigo", payload.get("code", "")))
    if status == 429 or code == "1007":
        raise DocumentLookupError(429, "El proveedor alcanzó su límite de consultas. Espera un momento antes de reintentar.")
    if status in {401, 402, 403} or code in {"1000", "1001", "1002", "1003", "1004", "1010", "1011"}:
        raise DocumentLookupError(503, "El proveedor no autorizó la consulta. Revisa las credenciales, saldo y permisos de la cuenta.")
    if status == 404 or code in {"102", "202", "document_not_found"}:
        raise DocumentLookupError(404, "No se encontraron datos para este documento. Puedes completarlos manualmente.")
    if status == 400 or code in {"100", "101", "200", "201", "invalid_input"}:
        raise DocumentLookupError(422, "El proveedor indica que el documento es inválido. Revisa su número.")
    success = payload.get("success") is True if peru else str(payload.get("status")) == "1"
    if status != 200 or not success:
        raise DocumentLookupError(503, "El proveedor no pudo completar la consulta. Intenta nuevamente o ingresa los datos manualmente.")
    data = payload.get("data", {}) if peru else payload
    if not isinstance(data, dict):
        data = {}
    returned_number = data.get("numero", data.get("ruc")) if peru else data.get(kind)
    if returned_number:
        try:
            returned = DocumentLookupRequest(document_type=kind, document_number=str(returned_number))
        except ValueError:
            raise DocumentLookupError(502, "El proveedor devolvió un documento diferente. No se aplicaron datos.") from None
        if returned.document_number != number:
            raise DocumentLookupError(502, "El proveedor devolvió un documento diferente. No se aplicaron datos.")
    if kind == "dni":
        names = _text(data.get("nombres"))
        lastnames = " ".join(filter(None, [_text(data.get("apellido_paterno")), _text(data.get("apellido_materno"))]))
    else:
        names = _text(data.get({"ruc": "nombre_o_razon_social", "cpf": "nome", "cnpj": "razao"}[kind]))
        # CPF only supplies a full name. Do not invent a surname split.
        lastnames = ""
    if not names:
        raise DocumentLookupError(502, "El proveedor no devolvió un nombre utilizable. Completa los datos manualmente.")
    return DocumentLookupResult(document_type=kind, document_number=number, names=names, lastnames=lastnames, source="apiperu" if peru else "cpfcnpj")
