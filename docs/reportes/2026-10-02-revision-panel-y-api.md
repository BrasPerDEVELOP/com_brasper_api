# Revisión del backoffice y del API — 2026-10-02

Alcance: `com_brasper_api` (FastAPI + SQLAlchemy async + Alembic) y `com_brasper_backofice`
(Vue 3 + TS + Pinia + Vite). No se modificó ningún archivo. Se revisaron los commits
recientes de ambos repos (707fe70, 68a1436, 92800f6 / dd67420, 4328fbb, 220cc0f, 16c0325).

## Estado de las suites

| Repo | Comprobación | Resultado |
|---|---|---|
| API | `pytest -q -x` | 305 passed, 1 error (`aiosqlite` no instalado en el venv; está en `requirements-test.txt`). Sin ese archivo: 304 passed, 0 fallos |
| API | Alembic | 1 solo head (`080`), cadena lineal 001→080, coherente con los modelos. `alembic/` en la raíz es una copia obsoleta (`alembic.ini` apunta a `app/db/migrations`) |
| Backoffice | `vue-tsc -b` | 0 errores (ojo: `use_calculator_store_controller.ts` tiene `@ts-nocheck`, 815 líneas de cálculo de dinero sin tipar) |
| Backoffice | `pnpm lint` | 0 errores, 15 warnings |
| Backoffice | `vitest` | 59 archivos, 441 tests, todos en verde |
| Contrato | `check-api-paths.mjs`, `api_contract.test.ts`, inventario de 129 rutas | OK; `api_routes.json` idéntico al regenerado |

---

## CRÍTICO

### C1. Cualquier usuario con `users.update`/`users.create` puede hacerse admin (API)
- `app/modules/users/adapters/router/user_routes.py:89-149`, `application/use_cases/user_use_cases.py:246-247`.
- El campo `role` no se valida. Ventas y contabilidad tienen `users.update` por defecto (`auth/domain/permissions.py:155-176`).
- Escenario: un usuario de ventas hace `PUT /user {id: <su id>, role: "admin"}`.
- Segundo camino: `POST /transactions/import` (solo `transactions.create`) crea usuarios con `user: Any` (`transaction_schema.py:1072`, `transaction_use_cases.py:1232-1245`) → admin con contraseña conocida y `permissions_granted` arbitrarios.
- Arreglo: solo admin (o permiso `users.assign_role`) puede asignar roles ≠ `client`; nadie cambia su propio rol; en import forzar `role=client` y vaciar permisos.

### C2. El cliente controla el monto destino y la tasa de su transacción (API)
- `transaction_use_cases.py:842-863` (calculadora ESPECIAL) y `:946-961` (`destinations`).
- (a) Cualquier cliente que mande `coupon_discount_code="ESPECIAL"` fija `coupon_discount_commission` (sin límite inferior → comisión negativa) y `tax_amount` manual.
- (b) `_sync_single_destination_amount` reparte el `destination_amount` del cliente y luego `entity_data["destination_amount"] = distributed_total` sobrescribe el valor calculado en el servidor.
- Escenario: `origin_amount=100, destination_amount=10000, destinations=[...]` → queda registrado 10 000 por recibir.
- Arreglo: ESPECIAL solo con `transactions.create`/permiso dedicado y descuento acotado a `[0, comisión]`; validar la distribución contra el monto calculado en servidor.

### C3. Credenciales de desarrollo dentro del bundle de producción (Backoffice)
- `src/interface/config/env.ts:7-9`: `import.meta.env[key]` con clave dinámica hace que Vite incruste **todo** `import.meta.env` en el JS. El guard `DEV` solo afecta al getter.
- Verificado con un `vite build` local: el bundle contiene `VITE_USERNAME` y `VITE_PASSWORD` reales.
- Arreglo: accesos estáticos (`import.meta.env.VITE_X`); sacar usuario/contraseña del `.env` (usar `.env.development.local`); rotar la contraseña; grep del bundle en CI.

---

## ALTO

### A1. Credenciales versionadas en el repo (API)
- `scripts/seed_accounting_users.py:40-42`: 3 usuarios de contabilidad con contraseña en claro y sin `must_change_password`.
- `.env.bak-20260817-123241` versionado desde 19657d5 (está en `.gitignore` pero ya en el índice). `test_transactions.xlsx` también.
- Arreglo: rotar secretos, `git rm --cached`, valorar limpiar historial, seeds por variables de entorno.

### A2. Asignación masiva en `POST /transactions` (API)
- `transaction_schema.py:216-337`, `transaction_routes.py:484-498`. El cliente puede enviar `payment_voucher(s)`, `checked_image(s)`, `send_vouchers` con keys de R2 arbitrarias, `payment_date`, `billing_date`, `operation_number`, `agent_id`, `mentioned_user_ids`.
- `main.py:198-216` autoriza `/media/transaction_vouchers/...` con `.limit(1)` sin `ORDER BY`: si dos transacciones comparten key, el dueño es arbitrario → un cliente puede ver comprobantes de otro.
- Arreglo: esquema de alta específico para clientes (lista blanca); en `/media`, autorizar si el usuario es dueño de **alguna** transacción que referencie el archivo.

### A3. "Sin límite" en rangos de comisión no se guarda al editar (contrato)
- Front manda `max_amount: null` (`use_comisiones_store_controller.ts:99-118`); back hace `if cmd.max_amount is not None` (`commission_use_cases.py:72-73`, `commission_accounting_use_cases.py:82-83`) → el null se ignora, 200 OK, pero el máximo anterior se queda.
- Arreglo: `if "max_amount" in cmd.model_fields_set` (y lo mismo para `min_amount`).

### A4. `tags.view` para contabilidad: el front lo garantiza, el back no (contrato)
- Front `permissions.ts:235,280` (dd67420). Back `permissions.py:118-120,177-199` no lo incluye, y `GET /transactions/tags` lo exige (`tag_routes.py:34`).
- Efecto: contabilidad ve menú/ruta de etiquetas y el filtro de Contabilidad, pero recibe 403.
- Arreglo: añadir `tags.view` a los defaults de accounting en el back + migración de `role_permissions`; o quitarlo de `withGuaranteedRolePermissions`.

### A5. Tramo de comisión incorrecto en huecos decimales (Backoffice)
- `commission_ranges.ts:65-75`: con escalera 100–299, 300–999, … un monto 299.50 cae al último tramo (10000+). El test `commission_ranges.test.ts:70-71` lo da por bueno.
- Además hay **4 implementaciones** distintas de "elegir tramo" (`contabilidad_view.vue:598-633` y `:658-688`, `transaction_domain.ts:385-396`, `findRangeForAmount`) que no coinciden en bordes. El commit 4328fbb prometía unificarlas.
- Arreglo: intervalos semiabiertos `[min, siguiente.min)` y un único helper de dominio.

### A6. Aviso HTML se guarda sin sanitizar (Backoffice)
- `NoticeHtmlEditor.vue:45-46`, `NoticeForm.vue:32`: el modo "Código HTML" envía el body crudo; `safeNoticeHtml` solo se aplica al pintar. El back sí sanitiza (`html_content.py`) → el riesgo es para otros consumidores. Sanitizar también antes de enviar.

### A7. Panel de permisos puede cargar los de otro usuario (Backoffice)
- `user_access_api_adapter.ts:5-12`: `GET /user?user_id=` toma `data[0]` sin verificar `id === userId`; y `parseEffectivePermissions` descarta claves desconocidas → al guardar se pierden.

---

## MEDIO

| # | Repo | Hallazgo | Ubicación |
|---|---|---|---|
| M1 | API | IDOR de cuentas bancarias: sin `destinations`, no se verifica que `bank_account_destination`/`origin` sean del usuario → `GET /transactions/{id}` devuelve titular, documento, CCI, PIX, CPF ajenos | `transaction_use_cases.py:270-293, 962-969` |
| M2 | API | WebSocket calcula permisos por su cuenta: ignora overrides, atajo admin, sesión activa y `enable` | `transactions_websocket.py:272-292` |
| M3 | API | `created_at` desplazado ~5 h: `server_default=(now() AT TIME ZONE 'America/Lima')` sobre `timestamptz` sin fijar zona de sesión. Afecta filtros por fecha y a **todas las métricas por mes** | `app/db/configuration_hour.py:13` |
| M4 | API | Dinero con `float`+`round()` (bancario) conviviendo con `Decimal ROUND_HALF_UP`; `round(250.5/100,2)=2.5` | `transaction_use_cases.py:806-864`, `accounting_settings_calc.py:27` |
| M5 | API | El listado contable recalcula `accounting_*` con la configuración vigente → meses cerrados cambian retroactivamente | `transaction_use_cases.py:555-573` |
| M6 | API | Etiquetas borradas siguen visibles/filtrables en el listado (no filtra `Tag.deleted`); métricas sí lo hacen → no cuadran. `tag_ids_by_transaction` es código muerto | `transactions/infrastructure/repository.py` (`_tag_ids_condition`), `domain/models.py:195-201` |
| M7 | API | Login social deja `role=NULL` → se trata como rol interno `user` → recibe `notifications.view`, lista staff, ve avisos de "todo el equipo". Vincula por email sin `verified_email` | `oauth_use_cases.py:165-227`, `dependencies.py:117-122` |
| M8 | API | Reset de contraseña: el código nunca se envía (no hay SMTP), se guarda en claro, no caduca, no revoca sesiones | `auth_service.py:95-131` |
| M9 | API | Defaults abiertos: `ENVIRONMENT="development"`, `AUTH_REQUIRED=False` → `require_permission` deja pasar todo | `core/settings.py:44,46`, `dependencies.py:162-163` |
| M10 | API | Import no atómico (commit por ítem) y sin `max_length` | `transaction_use_cases.py:1230-1272`, `transaction_schema.py:1089` |
| M11 | API | Subidas sin límite de tamaño, en memoria; nombres con 32 bits aleatorios; huérfanos en R2 si falla el alta | `file_service.py:95,170` |
| M12 | Contrato | Contabilidad carga comisiones/settings que exigen `commissions.view` pero la ruta solo pide `accounting.view` → 403 y valores de respaldo | `router/index.ts:74`, `commission_accounting_routes.py:33,43` |
| M13 | Front | Export Excel contable no espera catálogos (`onMounted` sin await) → columnas vacías sin aviso; se trunca a 20 000 filas en silencio; fechas como texto | `use_accounting_export.ts:19-25`, `use_transactions_store_controller.ts:249-257` |
| M14 | Front | Filtros por día dependen de la zona horaria del navegador (Perú vs Brasil ven días distintos) | `transaction_domain.ts:108-140`, `accounting_datetime.ts:20-26` |
| M15 | Front | `Math.round(n*100)/100` sin EPSILON (`1.005 → 1.00`) | `transaction_domain.ts:103-106` |
| M16 | Front | `must_change_password` no se impone (sin guard de ruta); permisos de sesión nunca se refrescan | `router/index.ts:189-228`, `use_auth_store_controller.ts:190` |
| M17 | Front | Cloudinary: `upload_preset` y cloud name hardcodeados, subida sin firmar | `blog_view.vue:59,252-268` |

## BAJO (resumen)
- API: `PUT /transactions/accounting/billing-date` muta con permiso de solo lectura (`accounting.view`); `billing_date` es `timestamptz` usándose como fecha. Rate limit solo por IP y en memoria; `/auth/google|facebook|refresh` sin límite. Clientes pueden mencionar staff (spam + enumeración de UUIDs). `GET /user`, `/user/detail`, `/bank-accounts` sin paginar. `next_sequential_transaction_code` hace MAX con regex sobre toda la tabla. Handler global de `ValueError` devuelve `str(exc)`. Código muerto: `FileType` con tipos de otro proyecto, Redis en `core/security.py`, `set_transaction_tags`.
- Contrato: `reverse` llega como `"0E-8"` (Decimal→string) y el front hace `Boolean()`; historial de comisiones/tasas da 404 siempre (ruta no existe); `api_contract.test.ts` no cubre `notifications_api_adapter.ts`; calculadora demo traga 403 de `rates.view`/`commissions.view`.
- Front: token en query del WS; `suggestNextRange` propone otro tramo abierto; `refresh()` de notificaciones se salta si hay carga en curso; reabrir la misma transacción desde la campanita no funciona; `transacciones_view.vue` tiene 6 475 líneas (objetivo < 500); `CLAUDE.md` dice que el token va en localStorage (ya no).

## Lo que está bien
- Sin inyección SQL (SQL crudo parametrizado). CORS rechaza `*` con credenciales. Lista blanca de rutas públicas exacta. `_verify_jwt` valida sesión, `client_app` y usuario. Cupones con `FOR UPDATE`.
- Front: token solo en memoria, refresh por cookie HttpOnly con promesa compartida, OAuth con `state`, visor de comprobantes excluye SVG, sanitizador de avisos sólido, guards de ruta coherentes, `.env` nunca commiteado.
- Contrato: filtros `tag_ids` repetidos coinciden; `counts_as_new_client`, avisos por audiencia, overrides de permisos, `billing_date` y export paginado a 100 coinciden en ambos lados.

## Orden sugerido de corrección
1. C1, C2, C3 (hoy).
2. A1 (rotar secretos), A2, M1, M7, M9.
3. A3, A4, A5, M12 (contrato y comisiones — afectan dinero visible).
4. M3 (zona horaria) **antes** de construir los nuevos gráficos mensuales.
5. El resto por módulos.
