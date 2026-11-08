"""Manual NFS-e issuance. A durable attempt prevents duplicate orders/invoices."""
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlparse
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.modules.billing.infrastructure.repository import SQLAlchemyBillingRepository
from app.modules.omie.domain.models import OmieInvoice
from app.modules.omie.infrastructure.client import OmieClient, OmieError, OmieUncertainResult
from app.modules.transactions.domain.enums import TransactionStatus
from app.modules.transactions.domain.models import Transaction
from app.modules.users.domain.models import User


def digits(value):
    return re.sub(r"\D", "", str(value or ""))


def omie_route(rate):
    def code(value):
        return str(getattr(value, "value", value)).lower()
    return rate is not None and code(rate.coin_a) == "brl" and code(rate.coin_b) in ("pen", "usd")


def customer_document(user):
    candidates = [(getattr(user, "document_type", ""), getattr(user, "document_number", ""))]
    candidates += [(i.document_type, i.document_number) for i in getattr(user, "identifications", []) if not i.deleted]
    for kind, value in candidates:
        kind = str(getattr(kind, "value", kind)).lower()
        doc = digits(value)
        if (kind == "cpf" and len(doc) == 11) or (kind == "cnpj" and len(doc) == 14):
            return doc
    raise ValueError("Registra el CPF o CNPJ del cliente antes de emitir con Omie")


def build_order(tx_id, code, customer_id, service_id, account_id, category, total):
    return {
        "Cabecalho": {"cCodIntOS": f"brasper-{tx_id}", "cCodParc": "999", "cEtapa": "10",
                      "dDtPrevisao": datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y"),
                      "nCodCli": customer_id, "nQtdeParc": 1},
        "Email": {"cEnvBoleto": "N", "cEnvLink": "N", "cEnviarPara": ""},
        "InformacoesAdicionais": {"cCidPrestServ": "SAO PAULO (SP)", "cCodCateg": category,
                                  "nCodCC": account_id, "cDadosAdicNF": f"Operacao Brasper {code}"},
        "ServicosPrestados": [{"nCodServico": service_id, "nQtde": 1, "nValUnit": float(total),
                               "cDadosAdicItem": f"Remessa internacional - operacao {code}"}],
    }


def public_record(row):
    if row is None:
        return None
    return {"status": row.status, "total": str(row.total), "os_id": row.os_id,
            "nfse_number": row.nfse_number, "error": row.error}


class OmieBillingService:
    def __init__(self, db, settings, client=None):
        self.db, self.settings = db, settings
        self.client = client or OmieClient(settings.OMIE_APP_KEY, settings.OMIE_APP_SECRET)
        self.billing = SQLAlchemyBillingRepository(db)

    async def preview(self, tx_id):
        if not self.settings.OMIE_ENABLED:
            raise ValueError("La emisión con Omie está deshabilitada")
        tx = (await self.db.execute(select(Transaction).options(
            selectinload(Transaction.user).selectinload(User.identifications)
        ).where(Transaction.id == tx_id, Transaction.deleted.is_(False)).execution_options(populate_existing=True))).scalar_one_or_none()
        if tx is None:
            raise LookupError("Operación no encontrada")
        if tx.status != TransactionStatus.completed:
            raise ValueError("La operación debe estar completada")
        rate = await self.billing.get_tax_rate(tx.tax_rate_id)
        if not omie_route(rate):
            raise ValueError("Omie solo está habilitado para reales a soles o dólares")
        if await self.billing.get_open_invoice(tx_id):
            raise ValueError("Esta operación ya tiene un comprobante SUNAT; revisa su estado antes de emitir")
        row = await self.db.get(OmieInvoice, tx_id)
        if row:
            return {"can_issue": False, "record": public_record(row), "total": str(row.total),
                    "currency": "BRL", "customer": row.snapshot.get("customer", ""),
                    "document": row.snapshot.get("document", ""), "issuer": row.snapshot.get("issuer", ""),
                    "service": row.snapshot.get("service", ""), "account": row.snapshot.get("account", "")}
        total = await self.billing.get_final_sale_for_billing(tx)
        if total is None or total <= 0:
            raise ValueError("La operación no tiene una venta final positiva calculable")
        document = customer_document(tx.user)
        companies = await self.client.call("ListarEmpresas", {"pagina": 1, "registros_por_pagina": 50})
        companies = [c for c in companies.get("empresas_cadastro", []) if digits(c.get("cnpj")) == self.settings.OMIE_ISSUER_CNPJ and c.get("inativa") != "S"]
        if len(companies) != 1 or companies[0].get("gera_nfse") != "S":
            raise ValueError("La empresa emisora de Omie no coincide o no tiene NFS-e habilitada")
        accounts = await self.client.call("ListarContasCorrentes", {"pagina": 1, "registros_por_pagina": 100})
        accounts = [a for a in accounts.get("ListarContasCorrentes", []) if a.get("nCodCC") == self.settings.OMIE_ACCOUNT_ID and a.get("inativo") != "S"]
        if len(accounts) != 1:
            raise ValueError("La cuenta de facturación configurada en Omie no está activa")
        srv = await self.client.call("ConsultarCadastroServico", {"nCodServ": self.settings.OMIE_SERVICE_ID})
        if srv.get("info", {}).get("inativo") == "S":
            raise ValueError("El servicio de Omie está inactivo")
        header = srv.get("cabecalho", {})
        if not header.get("cCodCateg"):
            raise ValueError("Falta la categoría del servicio en Omie")
        try:
            clients = await self.client.call("ListarClientes", {"pagina": 1, "registros_por_pagina": 50,
                "clientesFiltro": {"cnpj_cpf": document}})
        except OmieError as exc:
            raise ValueError("No se pudo localizar el cliente en Omie. Verifica su CPF/CNPJ y su registro en Omie") from exc
        clients = [c for c in clients.get("clientes_cadastro", []) if digits(c.get("cnpj_cpf")) == document and c.get("inativo") != "S"]
        if len(clients) != 1:
            raise ValueError("Registra o corrige el cliente en Omie con este CPF/CNPJ antes de emitir")
        customer = clients[0]
        if customer.get("bloquear_faturamento") == "S":
            raise ValueError("El cliente tiene la facturación bloqueada en Omie")
        order = build_order(tx.id, tx.code, customer["codigo_cliente_omie"], self.settings.OMIE_SERVICE_ID,
                            self.settings.OMIE_ACCOUNT_ID, header["cCodCateg"], total)
        return {"can_issue": True, "record": None, "total": str(total), "currency": "BRL",
                "customer": customer["razao_social"], "document": document,
                "issuer": companies[0]["razao_social"], "service": header.get("cDescricao", ""),
                "account": accounts[0].get("descricao", ""), "_order": order}

    async def issue(self, tx_id, expected_total, expected_document):
        preview = await self.preview(tx_id)
        if not preview["can_issue"]:
            raise ValueError("Ya existe un intento para esta operación. Consulta su estado en Omie")
        if Decimal(preview["total"]) != expected_total or preview["document"] != expected_document:
            raise ValueError("Los datos cambiaron. Abre nuevamente la vista previa antes de emitir")
        order = preview.pop("_order")
        row = OmieInvoice(transaction_id=tx_id, status="creating", total=expected_total,
                          snapshot={**preview, "order": order})
        self.db.add(row)
        try:
            await self.db.commit()  # durable unique claim BEFORE any remote mutation
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("Otra solicitud ya inició la emisión de esta operación") from None
        try:
            created = await self.client.call("IncluirOS", order)
            if not created.get("nCodOS"):
                raise OmieUncertainResult("Omie no confirmó el código de la orden; consulta el estado")
            row.os_id, row.status = int(created["nCodOS"]), "validating"
            await self.db.commit()
            await self.client.call("ValidarOS", {"nCodOS": row.os_id})
            row.status = "billing"
            await self.db.commit()
            await self.client.call("FaturarOS", {"nCodOS": row.os_id})
            row.status = "pending"
            await self.db.commit()
        except OmieError as exc:
            row.error, row.status = str(exc), "review_required"
            await self.db.commit()
        return public_record(row)

    async def refresh(self, tx_id):
        row = await self.db.get(OmieInvoice, tx_id)
        if row is None:
            raise LookupError("No hay una emisión de Omie para esta operación")
        # Recover an order after a lost response without creating another one.
        if not row.os_id:
            order = await self.client.call("ConsultarOS", {"cCodIntOS": f"brasper-{tx_id}"})
            row.os_id = order.get("Cabecalho", {}).get("nCodOS")
            if not row.os_id:
                raise ValueError("Omie aún no confirma la orden; revisa el intento en Omie")
        try:
            data = await self.client.call("ListarNFSEs", {"nPagina": 1, "nRegPorPagina": 50, "nCodigoOS": row.os_id})
        except OmieError as exc:
            message = unicodedata.normalize("NFKD", str(exc)).encode("ascii", "ignore").decode().lower()
            if "nao existem registros" in message or "nenhum registro" in message:
                await self.db.commit()
                return public_record(row)
            raise
        notes = [n for n in data.get("nfseEncontradas", []) if n.get("OrdemServico", {}).get("nCodigoOS") == row.os_id]
        if len(notes) > 1:
            raise ValueError("Hay más de una nota para la orden. Revisa el caso en Omie")
        if notes:
            header = notes[0]["Cabecalho"]
            if digits(header.get("cCNPJEmissor")) != self.settings.OMIE_ISSUER_CNPJ:
                raise ValueError("El emisor de la nota no coincide con Brasper")
            if header.get("cAmbienteNFSe") != "P":
                raise ValueError("La nota de Omie no pertenece al ambiente de producción")
            recipient = digits(header.get("cCPFDestinatario") or header.get("cCNPJDestinatario"))
            if recipient != row.snapshot.get("document"):
                raise ValueError("El cliente de la nota de Omie no coincide con el comprobante solicitado")
            if Decimal(str(header["nValorNFSe"])).quantize(Decimal("0.01")) != row.total:
                raise ValueError("El total de la nota de Omie no coincide con la venta final reservada")
            row.nfse_id, row.nfse_number = header.get("nCodNF"), str(header.get("nNumeroNFSe") or "")
            row.status = {"F": "issued", "C": "cancelled"}.get(header.get("cStatusNFSe"), "pending")
            row.error = None
        await self.db.commit()
        return public_record(row)

    async def pdf(self, tx_id):
        row = await self.db.get(OmieInvoice, tx_id)
        if not row or not row.nfse_id or row.status not in ("issued", "cancelled"):
            raise ValueError("Consulta el estado de la nota emitida antes de abrir su PDF")
        docs = await self.client.call("ObterNFSe", {"nIdNf": row.nfse_id})
        if str(docs.get("cNumNFSe", "")).lstrip("0") != str(row.nfse_number).lstrip("0"):
            raise ValueError("El PDF devuelto por Omie no corresponde a la nota")
        url = docs.get("cPdfNFSe", "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ("click.omie.com", "app.omie.com.br"):
            raise ValueError("Omie no devolvió un enlace de PDF válido")
        return {"url": url}
