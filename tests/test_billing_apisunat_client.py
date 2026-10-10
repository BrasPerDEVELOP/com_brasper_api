"""Cliente HTTP de APISUNAT: formato de getAll y token fuera de los logs."""
import logging

import httpx
import pytest

from app.modules.billing.infrastructure.apisunat_client import (
    ApisunatHttpClient,
    install_log_redaction,
    redact_persona_token,
)


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
