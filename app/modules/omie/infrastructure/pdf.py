"""Download the official document, never forward API credentials to its URL."""
from urllib.parse import urljoin, urlparse

import httpx

from app.modules.omie.infrastructure.client import OmieError

MAX_PDF_BYTES = 15 * 1024 * 1024
PDF_HOSTS = {"click.omie.com", "app.omie.com.br", "cdn.omie.com.br"}


def validate_pdf_url(url: str) -> None:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in PDF_HOSTS
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Omie no devolvió un enlace de PDF válido")


async def download_pdf(url: str, *, transport=None) -> bytes:
    try:
        async with httpx.AsyncClient(timeout=40, follow_redirects=False, transport=transport) as client:
            for _ in range(4):
                validate_pdf_url(url)
                async with client.stream("GET", url) as response:
                    if response.is_redirect:
                        url = urljoin(url, response.headers.get("location", ""))
                        continue
                    response.raise_for_status()
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_PDF_BYTES:
                            raise ValueError("El PDF de Omie supera el tamaño permitido para correo")
                    if not content.startswith(b"%PDF-"):
                        raise ValueError("Omie no entregó un PDF válido para adjuntar")
                    return bytes(content)
    except httpx.HTTPError:
        raise OmieError("No se pudo descargar el PDF de Omie. Intenta más tarde") from None
    raise ValueError("Omie devolvió demasiadas redirecciones para el PDF")
