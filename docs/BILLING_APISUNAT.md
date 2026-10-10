# Facturación electrónica con APISUNAT

Boletas (03) y facturas (01) por la comisión cobrada en cada operación `completed`.
Módulo `app/modules/billing`, rutas `/billing/*`. Este documento describe cómo
funciona, cómo probarlo y los cambios hechos tras la revisión del commit
`faf3f83` ("facturación electrónica de comisiones vía APISUNAT").

Contrato de APISUNAT verificado contra <https://docs.apisunat.com> el 2026-10-10.

## Empresas en APISUNAT

En el portal hay dos empresas en **DESARROLLO**:

| Empresa | RUC | Uso |
|---|---|---|
| BRASPER 21 S.A.C. ("brasper transferencias") | 20608550454 | Emisora por defecto |
| INGENITECH S.A.C. ("brasper transferencias") | 20611936428 | Se elige al emitir |

Cada `personaToken` vale para **una empresa y un ambiente**. El token se crea en
apisunat.com → la empresa → *Configuración de Empresa*.

### Varias empresas emisoras

Al emitir se elige la empresa. Cada una usa **su token** de APISUNAT y **su propia
numeración**: la B001-00000001 de BRASPER 21 y la de INGENITECH son comprobantes
distintos (migración **087**: `issuer_ruc` en `billing.series` y `billing.invoices`).
Consultar, reintentar, anular y descargar el PDF usan siempre el token de la empresa
del comprobante.

Se configuran en una sola variable JSON (en una línea, entre comillas simples):

```env
BILLING_ISSUERS='[{"ruc":"20608550454","name":"BRASPER 21 S.A.C.","trade_name":"brasper transferencias","address":"AV. AREQUIPA NRO. 2447 INT. 409","ubigeo":"150116","district":"LINCE","province":"LIMA","department":"LIMA","persona_id":"…","persona_token":"…"},{"ruc":"20611936428","name":"INGENITECH S.A.C.","trade_name":"brasper transferencias","address":"PJ. LOS LAURELES MZ. M LT. 13 A.H. SECTOR B","ubigeo":"150132","district":"SAN JUAN DE LURIGANCHO","province":"LIMA","department":"LIMA","persona_id":"…","persona_token":"…"}]'
BILLING_DEFAULT_ISSUER_RUC=20608550454
```

- Si `BILLING_ISSUERS` está vacío, se usa una sola empresa con `BILLING_ISSUER_*` +
  `APISUNAT_PERSONA_ID/TOKEN` (configuración anterior, sigue funcionando).
- Con `BILLING_ENABLED=true`, **cada** empresa necesita `persona_id` y
  `persona_token`; si falta alguno la API no arranca y el mensaje dice cuál.
- Los tokens de una misma lista deben ser todos del mismo ambiente
  (`APISUNAT_ENVIRONMENT`).
- Probar el token de una empresa: `python scripts/apisunat_smoke.py --issuer 20611936428`.

## Configuración

```env
BILLING_ENABLED=true
BILLING_AUTO_ISSUE=false             # true: emite sola al completar la operación
BILLING_COMMISSION_INCLUDES_IGV=true # la comisión ya incluye IGV (base = total / 1.18)
APISUNAT_ENVIRONMENT=development     # production solo con ENVIRONMENT != development
APISUNAT_PERSONA_ID=<personaId de BRASPER 21>
APISUNAT_PERSONA_TOKEN=<token de DESARROLLO de BRASPER 21>
APISUNAT_TIMEOUT_SECONDS=30
BILLING_SERIES_BOLETA=B001
BILLING_SERIES_FACTURA=F001
BILLING_POLL_INTERVAL_SECONDS=30
BILLING_START_DATE=                  # YYYY-MM-DD: operaciones anteriores no se facturan
```

Después: `alembic upgrade head` (migraciones 085, 086 y 087).

### En el servidor (Docker)

`docker-compose.yml` pasa al contenedor una lista **explícita** de variables y
`.dockerignore` excluye `.env*`: una variable que no esté en esa lista no llega a la
API aunque esté en el `.env` del servidor. Las `BILLING_*` y `APISUNAT_*` ya están en
la lista, con los mismos valores por defecto que `Settings` (módulo apagado).

- Sin tocar nada: la facturación queda **apagada** y la API arranca normal.
- **Nunca** pongas `BILLING_ENABLED=true` sin `APISUNAT_PERSONA_ID` y
  `APISUNAT_PERSONA_TOKEN`: la validación de arranque falla y el contenedor no levanta.
- `APISUNAT_ENVIRONMENT=production` exige `ENVIRONMENT` distinto de `development`.
- Tras cambiar el `.env`: `docker compose up -d api` (recrea el contenedor con las
  variables nuevas; un simple `restart` no las relee).

## Probar que funciona

```bash
python scripts/apisunat_smoke.py           # solo lectura: valida credenciales con lastDocument
python scripts/apisunat_smoke.py --emit    # emite una boleta de S/ 1.18 en serie B999 y espera a SUNAT
```

El script usa la misma plantilla UBL y el mismo cliente HTTP que la API, no toca la
base de datos y se niega a emitir fuera de `development`. La serie B999 evita mover
el correlativo B001 que usa Brasper.

Prueba completa desde la API (con la base de desarrollo):

1. Completar una operación de prueba con comisión > 0.
2. `POST /billing/transactions/{id}/issue` → `sent`.
3. Esperar un ciclo del poller (o `POST /billing/invoices/{id}/refresh`) → `accepted`, con XML, CDR y PDF en R2 (`invoices/AAAA/...pdf`).

## Uso desde el backoffice

| Dónde | Qué se hace |
|---|---|
| **Contabilidad** → columna «Comprobante SUNAT» | Botón **Emitir** en cada operación finalizada sin comprobante. Si ya tiene uno, muestra número y estado; al hacer clic abre el detalle. |
| Diálogo **Emitir** | Selector de **empresa emisora** (si hay más de una) y selector **Boleta / Factura** (arranca en el que corresponde al documento del cliente: RUC → factura). Factura pide RUC de 11 dígitos y razón social si la ficha no los tiene; boleta se admite también a un cliente con RUC. Vista previa sin reservar número: serie, cliente, valor de venta, IGV y total, con el ambiente (Desarrollo/Producción) bien visible. Si no se puede emitir, dice por qué. |
| Panel de **detalle** | Estado y explicación, errores y observaciones de SUNAT, PDF/XML/CDR, historial y acciones: *Consultar SUNAT*, *Reintentar* / *Emitir de nuevo* y *Anular* (con motivo). Mientras espera a SUNAT se actualiza solo cada 10 s. |
| **Facturación** (menú lateral) | Listado de comprobantes con filtros por estado, tipo y fecha de emisión (hora de Lima), y la configuración vigente: ambiente, emisor y último número de cada serie. |

Permisos: `billing.view` (ver), `billing.issue` (emitir y reintentar) y `billing.void`
(anular). Contabilidad tiene ver y emitir; anular queda para admin.

Rutas que usa el backoffice además de las ya descritas:

- `GET /billing/invoices/by-transactions?transaction_ids=…` (hasta 100): último
  comprobante de cada operación, para pintar una página de Contabilidad en una petición.
- `GET /billing/transactions/{id}/preview`: lo que saldría al emitir, sin reservar
  número ni llamar a APISUNAT. Acepta los mismos datos del cliente que `issue` como
  parámetros de consulta y responde `can_issue` + `reason`.
- `issue` y `preview` aceptan `document_type` (`01` factura, `03` boleta). Sin él, el
  tipo es automático según el documento del cliente.

## Ciclo de vida

```
reserved ──sendBill PENDIENTE──▶ sent ──getById──▶ accepted ──voidBill──▶ voided
   │                               ├──────────────▶ rejected  (número consumido; retry emite otro número)
   │                               └──────────────▶ exception (número libre; retry reenvía el mismo)
   └──ERROR / timeout sin rastro──▶ error (retry verifica en APISUNAT y reenvía el mismo número)
```

- `reserved`, `sent` y `accepted` cuentan como comprobante vivo: un índice único
  parcial impide dos por operación.
- El número se reserva con `FOR UPDATE` y se hace commit **antes** de llamar a
  APISUNAT, porque `sendBill` no es idempotente.

## Cambios tras la revisión (2026-10-10)

### 1. El poller ya no deja el bloqueo pegado a una conexión del pool

**Problema.** El poller tomaba `pg_try_advisory_lock` (bloqueo de sesión de Postgres)
en la sesión ORM de trabajo. Esa sesión hace `commit` por cada comprobante y, con
cada commit, SQLAlchemy devuelve la conexión al pool. El `pg_advisory_unlock` final
corría en otra conexión y no liberaba nada: el bloqueo quedaba pegado a una
conexión del pool, los ciclos siguientes se saltaban al azar y, con varias
réplicas, las demás no volvían a consultar. Resultado: comprobantes en `sent` sin
avanzar a `accepted`.

**Cambio.** `InvoicePoller.tick()` toma y libera el bloqueo en una conexión
dedicada (`engine.connect()`), separada de la sesión de trabajo.
Archivo: `app/modules/billing/infrastructure/poller.py`.

### 2. Rescate de comprobantes atascados en `reserved`

**Problema.** Si el proceso se caía entre el commit de la reserva y la respuesta de
`sendBill` (deploy, reinicio, falta de memoria), el comprobante quedaba en
`reserved` para siempre: contaba como vivo (bloqueaba emitir otro), no era
reintentable y el poller lo ignoraba.

**Cambio.**
- Nueva columna `billing.invoices.reserved_at` (migración **086**), fijada por
  Python en UTC al reservar y al reintentar. No se usa `created_at`/`updated_at`
  porque su `server_default` (`now() AT TIME ZONE 'America/Lima'` sobre
  `timestamptz`) queda desplazado 5 horas con la sesión de Postgres en UTC: un
  comprobante recién reservado parecería viejo.
- Nuevo `RecoverStaleReservedUseCase`, que corre en cada ciclo del poller. Toma los
  `reserved` con más de `2 × APISUNAT_TIMEOUT_SECONDS + 60 s` (2 min con la
  configuración por defecto) y busca el documento en APISUNAT por serie-número:
  - existe → pasa a `sent` y el poller resuelve su estado;
  - no existe → pasa a `error` (número no consumido, reintentable con el mismo);
  - APISUNAT no responde → se deja igual y se intenta en el siguiente ciclo.

Archivos: `application/use_cases.py`, `infrastructure/repository.py`
(`list_stale_reserved`), `interfaces/repository.py`, `domain/models.py`.

### 3. El reintento de un `error` verifica antes de reenviar el mismo número

**Problema.** Tras un timeout de `sendBill`, si la búsqueda posterior todavía no
encontraba el documento, el comprobante quedaba en `error`. Al reintentar se
reenviaba el mismo número aunque quizá sí había llegado, con riesgo de duplicado.
Además, la búsqueda enviaba `number` como entero (`1`) y APISUNAT lo espera como
texto de 8 dígitos (`"00000001"`), así que la recuperación nunca encontraba el
documento.

**Cambio.**
- `RetryInvoiceUseCase`: para `error`, primero busca en APISUNAT. Si el documento
  existe lo adopta (`sent`) sin reenviar; si no existe, reenvía; si no se puede
  verificar, responde 502 y **no** reenvía. `exception` sigue reenviando directo
  (SUNAT libera el número) y `rejected` sigue emitiendo un número nuevo.
- `ApisunatHttpClient.find_by_file_name` envía `number` con 8 dígitos.

### 4. El token de APISUNAT ya no aparece en los logs

**Problema.** `GET /documents/getAll` exige `personaToken` en la query string (así
lo define APISUNAT) y httpx registra la URL completa a nivel INFO.

**Cambio.** Filtro de logging en los loggers `httpx` y `httpcore` que reemplaza el
valor por `personaToken=***`. Se instala al importar el cliente.
Archivo: `infrastructure/apisunat_client.py`.

### Tests

- `tests/test_billing_use_cases.py`: 8 nuevos (reintento de `error` con y sin
  documento remoto y sin poder verificar, `exception` sin búsqueda, rescate de
  reservados, `reserved_at`).
- `tests/test_billing_apisunat_client.py`: número de 8 dígitos y redacción del token.
- `tests/test_billing_poller.py`: lock y unlock en la misma conexión.
- Facturación: 49 → 62 tests, todos pasan.

### Script

- `scripts/apisunat_smoke.py`: prueba de humo contra APISUNAT (ver arriba).

## Pendiente (no incluido en estos cambios)

Decisiones fiscales a confirmar con el contador antes de producción:

1. **Base imponible.** Facturación emite por `commission_result` con el IGV
   incluido. El módulo de Contabilidad calcula otra venta: `(Q / 1.18) × (1 − V)`.
   El IGV declarado no cuadrará con el reporte contable hasta unificarlos.
2. **Moneda.** El comprobante sale en la moneda de origen: una operación BRL→PEN
   genera una boleta en BRL.
3. **Clientes no domiciliados (Brasil).** Puede tratarse de exportación de servicios
   (afectación 40), no de una operación gravada (10, fija en la plantilla).
4. **Boletas de más de S/ 700** sin documento del cliente: SUNAT exige identificarlo.

Técnico:

- La anulación (`voidBill`) marca `voided` al recibir `PENDIENTE` y no consulta
  después si SUNAT aceptó la baja; no controla el plazo legal ni usa nota de crédito.
- Una operación completada sigue editable aunque ya tenga comprobante aceptado.
- `IntegrityError` por emisión simultánea (manual + automática) responde 500 en vez de 409.
- `POST /billing/invoices/{id}/refresh` escribe estado con el permiso `billing.view`.
- Con datos reales, la boleta (comisión cobrada con IGV incluido) y la «Venta final» de
  Contabilidad no coinciden: p. ej. una operación de S/ 290 sale como boleta de S/ 16.32
  y en Contabilidad figura con S/ 8.70. Es el punto 1 de las decisiones fiscales.

## Pase a producción

1. Resolver los puntos fiscales de arriba.
2. En APISUNAT: certificado digital (CDT) y usuario secundario SOL
   (guía "Pase a Producción" de docs.apisunat.com), y token de PRODUCCIÓN.
3. `APISUNAT_ENVIRONMENT=production`, `ENVIRONMENT=production`.
4. `POST /billing/series/align` para alinear B001/F001 con `lastDocument`.
5. Emitir manualmente unas cuantas boletas (`BILLING_AUTO_ISSUE=false`) antes de
   activar la emisión automática.
