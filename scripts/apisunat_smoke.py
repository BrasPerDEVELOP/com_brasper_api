"""Prueba de humo contra APISUNAT (ambiente de DESARROLLO).

Comprueba credenciales y, opcionalmente, emite una boleta de prueba de punta a
punta con la misma plantilla y el mismo cliente HTTP que usa la API. No toca la
base de datos.

Uso (lee APISUNAT_* y BILLING_ISSUER_* del .env):

    python scripts/apisunat_smoke.py                 # solo lectura: lastDocument de B001/F001
    python scripts/apisunat_smoke.py --emit          # además emite una boleta de S/ 1.18 y espera a SUNAT
    python scripts/apisunat_smoke.py --emit --series B999
    python scripts/apisunat_smoke.py --issuer 20611936428   # otra empresa de BILLING_ISSUERS

Se niega a emitir si APISUNAT_ENVIRONMENT no es ``development``: un comprobante
de producción tiene validez tributaria.

La boleta de prueba usa una serie aparte (B999 por defecto) para no mover el
correlativo de la serie real de desarrollo que usa Brasper (B001).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import get_settings  # noqa: E402
from app.modules.billing.adapters.dependencies import build_apisunat_client  # noqa: E402
from app.modules.billing.application.ubl_builder import (  # noqa: E402
    CustomerParty,
    InvoiceDraft,
    build_document_body,
    build_file_name,
    issue_moment,
)
from app.modules.billing.application.use_cases import issuer_from_settings  # noqa: E402
from app.modules.billing.domain.amounts import compute_invoice_amounts  # noqa: E402
from app.modules.billing.domain.enums import BillingDocumentType  # noqa: E402
from app.modules.billing.interfaces.apisunat_client import ApisunatError  # noqa: E402

FINAL_STATUSES = {"ACEPTADO", "RECHAZADO", "EXCEPCION"}


def _next_number(payload: dict) -> int:
    for key in ("suggestedNumber", "lastNumber"):
        if payload.get(key) not in (None, ""):
            value = int(payload[key])
            return value if key == "suggestedNumber" else value + 1
    return 1


async def main(emit: bool, series: str, wait_seconds: int, issuer_ruc: str | None) -> int:
    settings = get_settings()
    env = settings.APISUNAT_ENVIRONMENT.lower()
    issuer = settings.billing_issuer(issuer_ruc)
    if issuer is None:
        configured = ", ".join(f"{i.ruc} ({i.name})" for i in settings.billing_issuers)
        print(f"La empresa {issuer_ruc} no está configurada. Configuradas: {configured}")
        return 2
    if not issuer.persona_id or not issuer.persona_token:
        print(f"Faltan personaId / personaToken de {issuer.name} en el .env")
        return 2
    print(f"Empresa: {issuer.name} (RUC {issuer.ruc}) · ambiente {env}")
    client = build_apisunat_client(settings).for_issuer(issuer.ruc)

    # 1) Credenciales: lastDocument es de solo lectura.
    for doc_type, serie in (("03", settings.BILLING_SERIES_BOLETA), ("01", settings.BILLING_SERIES_FACTURA)):
        try:
            payload = await client.last_document(document_type=doc_type, series=serie)
        except ApisunatError as exc:
            print(f"  lastDocument {doc_type}-{serie}: FALLÓ → {exc}")
            return 1
        if "error" in payload:
            print(f"  lastDocument {doc_type}-{serie}: APISUNAT rechazó la consulta → {payload['error']}")
            return 1
        print(
            f"  lastDocument {doc_type}-{serie}: último={payload.get('lastNumber')} "
            f"siguiente={payload.get('suggestedNumber')} production={payload.get('production')}"
        )
        if payload.get("production") is True and env != "production":
            print("  ⚠ El token es de PRODUCCIÓN pero APISUNAT_ENVIRONMENT dice development. Revisa el .env.")
            return 1

    if not emit:
        print("Credenciales OK. Usa --emit para emitir una boleta de prueba.")
        return 0
    if env != "development":
        print("Me niego a emitir: APISUNAT_ENVIRONMENT no es development.")
        return 2

    # 2) Boleta de prueba: S/ 1.18 (base 1.00 + IGV 0.18) a un cliente sin documento.
    payload = await client.last_document(document_type="03", series=series)
    number = _next_number(payload)
    issue_date, issue_time = issue_moment()
    amounts = compute_invoice_amounts(Decimal("1.18"), igv_included=True)
    draft = InvoiceDraft(
        document_type=BillingDocumentType.boleta,
        series=series,
        number=number,
        issue_date=issue_date,
        issue_time=issue_time,
        currency="PEN",
        amounts=amounts,
        item_description="Prueba de integración Brasper (desarrollo)",
    )
    customer = CustomerParty(doc_type="0", doc_number="-", name="CLIENTE DE PRUEBA")
    body = build_document_body(draft, issuer_from_settings(settings, issuer.ruc), customer)
    file_name = build_file_name(issuer.ruc, BillingDocumentType.boleta, series, number)
    print(f"Enviando {file_name} ...")
    result = await client.send_bill(file_name=file_name, document_body=body, reference="smoke-test")
    if not result.accepted_for_processing:
        print(f"  sendBill no aceptó el documento: status={result.status} error={result.error or result.raw}")
        return 1
    print(f"  PENDIENTE · documentId={result.document_id}")

    # 3) Esperar la respuesta de SUNAT.
    info = None
    for _ in range(max(1, wait_seconds // 5)):
        await asyncio.sleep(5)
        info = await client.get_by_id(result.document_id)
        print(f"  getById → {info.status or '(sin estado)'}")
        if info.status in FINAL_STATUSES:
            break
    if info is None or info.status not in FINAL_STATUSES:
        print("SUNAT aún no responde; vuelve a consultar más tarde con el documentId de arriba.")
        return 1
    if info.faults:
        print(f"  faults: {info.faults}")
    if info.notes:
        print(f"  notes: {info.notes}")
    print(f"  xml: {info.xml_url}\n  cdr: {info.cdr_url}")
    return 0 if info.status == "ACEPTADO" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--emit", action="store_true", help="emite una boleta de prueba en desarrollo")
    parser.add_argument("--series", default="B999", help="serie de prueba (4 caracteres, empieza con B)")
    parser.add_argument("--wait", type=int, default=60, help="segundos máximos esperando a SUNAT")
    parser.add_argument("--issuer", default=None, help="RUC de la empresa emisora (por defecto, la principal)")
    args = parser.parse_args()
    if len(args.series) != 4 or not args.series.startswith("B"):
        parser.error("--series debe tener 4 caracteres y empezar con B")
    raise SystemExit(asyncio.run(main(args.emit, args.series.upper(), args.wait, args.issuer)))
