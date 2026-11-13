"""Omie JSON API. Credentials remain in the backend; mutations are never retried."""
from __future__ import annotations

import httpx


class OmieError(RuntimeError):
    pass


class OmieUncertainResult(OmieError):
    """A request may have reached Omie: reconcile before sending it again."""


class OmieClient:
    BASE_URL = "https://app.omie.com.br/api/v1/"
    METHODS = {
        "ListarEmpresas": "geral/empresas/",
        "ListarContasCorrentes": "geral/contacorrente/",
        "ListarClientes": "geral/clientes/",
        "IncluirCliente": "geral/clientes/",
        "ConsultarCadastroServico": "servicos/servico/",
        "ListarCadastroServico": "servicos/servico/",
        "ConsultarOS": "servicos/os/",
        "IncluirOS": "servicos/os/",
        "StatusOS": "servicos/os/",
        "ValidarOS": "servicos/osp/",
        "FaturarOS": "servicos/osp/",
        "ListarNFSEs": "servicos/nfse/",
        "ObterNFSe": "servicos/osdocs/",
    }

    def __init__(self, app_key: str, app_secret: str, *, transport=None):
        if not app_key or not app_secret:
            raise OmieError("Faltan las credenciales de Omie en el servidor")
        self._key = app_key
        self._secret = app_secret
        self._transport = transport

    def _redact(self, message: str) -> str:
        return message.replace(self._key, "***").replace(self._secret, "***")[:600]

    async def call(self, method: str, params: dict) -> dict:
        if method not in self.METHODS:
            raise ValueError("Método de Omie no permitido")
        try:
            async with httpx.AsyncClient(timeout=40, transport=self._transport, follow_redirects=False) as client:
                response = await client.post(self.BASE_URL + self.METHODS[method], json={
                    "call": method, "app_key": self._key, "app_secret": self._secret,
                    "param": [params],
                })
        except httpx.RequestError:
            raise OmieUncertainResult("No se confirmó la respuesta de Omie; consulta el estado antes de reintentar") from None
        try:
            body = response.json()
        except ValueError:
            raise OmieUncertainResult("Omie devolvió una respuesta no válida; consulta el estado") from None
        if not isinstance(body, dict):
            raise OmieUncertainResult("Respuesta inesperada de Omie")
        if body.get("faultcode") == "SOAP-ENV:Server-API_ADDON_REQUIRED":
            raise OmieError("El acceso API de Omie requiere activar el complemento contratado")
        if response.status_code >= 500 and not body.get("faultstring"):
            raise OmieUncertainResult("Omie no confirmó el resultado; consulta el estado antes de reintentar")
        if body.get("faultstring") or not response.is_success:
            raise OmieError(self._redact(str(body.get("faultstring") or "Omie rechazó la solicitud")))
        code = body.get("cCodStatus", body.get("codigo_status"))
        if code is not None and str(code) != "0":
            raise OmieError(self._redact(str(body.get("cDescStatus") or body.get("descricao_status") or "Error de Omie")))
        return body
