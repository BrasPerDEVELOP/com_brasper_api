"""Cliente HTTP de APISUNAT: formato de getAll y token fuera de los logs."""
import logging

import httpx
import pytest

from app.modules.billing.infrastructure.apisunat_client import (
    ApisunatHttpClient,
    install_log_redaction,
    redact_persona_token,
)
from app.modules.billing.interfaces.apisunat_client import ApisunatError


@pytest.mark.asyncio
async def test_pdf_follows_provider_redirect_without_credentials():
    requests = []
    pdf = b'%PDF-1.7\nexample'
    def handler(request):
        requests.append(request)
        if request.url.host == 'back.apisunat.com':
            return httpx.Response(301, headers={'location': 'https://cdn.example.com/document.pdf'})
        return httpx.Response(200, content=pdf, headers={'content-type': 'application/pdf'})
    client = ApisunatHttpClient(base_url='https://back.apisunat.com', persona_id='p',
                               persona_token='secret', transport=httpx.MockTransport(handler))
    assert await client.get_pdf('doc', pdf_format='A4', file_name='20611936428-03-BB02-00000001') == pdf
    assert len(requests) == 2
    assert 'secret' not in str(requests[1].url)
    assert 'authorization' not in requests[1].headers


@pytest.mark.asyncio
async def test_pdf_rejects_html_even_when_http_success():
    client = ApisunatHttpClient(base_url='https://back.apisunat.com', persona_id='p', persona_token='t',
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'<html>Error</html>')))
    with pytest.raises(ApisunatError, match='PDF válido'):
        await client.get_pdf('doc', pdf_format='A4', file_name='x')


@pytest.mark.asyncio
async def test_find_by_file_name_envia_el_numero_con_8_digitos():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(
            200,
            json=[{"_id": "doc-9", "status": "PENDIENTE", "fileName": "20608550454-03-B001-00000009"}],
        )

    client = ApisunatHttpClient(
        base_url="https://back.apisunat.com",
        persona_id="p",
        persona_token="t",
        transport=httpx.MockTransport(handler),
    )
    info = await client.find_by_file_name("20608550454-03-B001-00000009")

    assert seen["number"] == "00000009"
    assert (seen["type"], seen["serie"]) == ("03", "B001")
    assert info is not None and info.document_id == "doc-9"


def test_redacta_persona_token():
    url = "https://back.apisunat.com/documents/getAll?personaId=abc&personaToken=SECRETO&type=03"
    assert redact_persona_token(url) == (
        "https://back.apisunat.com/documents/getAll?personaId=abc&personaToken=***&type=03"
    )


def test_log_de_httpx_no_muestra_el_token(caplog):
    install_log_redaction()
    url = httpx.URL("https://back.apisunat.com/documents/getAll?personaId=abc&personaToken=SECRETO")
    with caplog.at_level(logging.INFO, logger="httpx"):
        logging.getLogger("httpx").info('HTTP Request: %s %s "%s %d %s"', "GET", url, "HTTP/1.1", 200, "OK")
    assert "SECRETO" not in caplog.text
    assert "personaToken=***" in caplog.text
