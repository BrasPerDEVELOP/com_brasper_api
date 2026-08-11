# Operación de JWT, auditoría y rutas canónicas

## Orden de despliegue

1. Hacer respaldo y ejecutar `alembic upgrade 065` antes de aceptar tráfico de la nueva versión.
2. Desplegar API con `AUTH_MODE=dual` y `AUTH_REQUIRED=true`.
3. Desplegar `com_brasper_backofice` y `com_brasper_www` configurados contra la misma API HTTPS.
4. Verificar login, refresh, logout, registro, calculadora pública, cupón automático, transacción y auditoría.
5. Observar uso de tokens opacos y aliases con `/` final durante la ventana acordada.
6. Cuando no queden clientes legacy, cambiar a `AUTH_MODE=jwt`. Retirar aliases en un cambio posterior.

No se debe activar el código antes de la migración: las mutaciones requieren que la fila base de auditoría pueda escribirse.

## Variables obligatorias en producción

- `ENVIRONMENT=production`
- `AUTH_REQUIRED=true`
- `AUTH_MODE=dual` durante transición; luego `jwt`
- `JWT_SECRET_KEY`: aleatorio, mínimo 32 caracteres y diferente de `SECRET_KEY`
- `JWT_ISSUER` y `JWT_AUDIENCE`: valores estables del entorno
- `JWT_ACCESS_TTL_MINUTES`: recomendado 15, permitido 1–60
- `REFRESH_TOKEN_TTL_DAYS`: recomendado 7, permitido 1–30
- `REFRESH_COOKIE_SECURE=true`
- `REFRESH_COOKIE_SAMESITE=lax` si los sitios comparten dominio registrable; `none` solo con HTTPS y después de validar el flujo cross-site
- `REFRESH_COOKIE_DOMAIN`: omitir salvo que exista una necesidad comprobada de compartirla
- `CORS_ALLOWED_ORIGINS`: lista exacta HTTPS de WWW y backoffice, nunca `*`
- `TRUSTED_PROXY_CIDRS`: todos y únicamente los proxies que realmente anteceden a la API
- `PUBLIC_URL`: URL HTTPS del API cuando se usa detrás de proxy

El access token vive solo en memoria. El refresh es opaco, rota en cada uso y solo se entrega mediante cookie HttpOnly bajo `/auth`.

## Rutas públicas

La allowlist compara método y path exactos. Son públicas las lecturas de health, blog publicado, banners/popups habilitados, monedas, tasas, comisiones y `/transactions/coupons/automatic`; además de login, refresh, reset, registro y envío del formulario de contacto.

Permanecen privadas, entre otras:

- `/transactions/coupons` y su detalle;
- usuarios, roles, transacciones e historial;
- cuentas bancarias del cliente (con control de dueño);
- formularios recibidos (`contact_forms.view`);
- auditoría (`audit.view`);
- integraciones y mutaciones administrativas.

Los callbacks OAuth no aceptan una URL de redirección para devolver credenciales:
ningún access token se incorpora a query params. Las rutas privadas de
`/brasper/ai/*` requieren tanto el JWT de servicio como
`X-Brasper-IA-Secret` en producción.

Los clientes de la WWW sin `transactions.view` solo pueden listar, crear o consultar sus propias transacciones. Un registro anónimo siempre se fuerza a rol `client`, sin `is_agent` ni `auth_id` elegibles.

## Media privada

Solo `profile_images`, `home_banner` y `home_popup` son prefijos públicos de `/media`.

`transaction_vouchers/*` siempre se devuelve mediante la API autenticada y se valida contra el dueño de la transacción o `transactions.view`; nunca se genera una URL directa de `R2_PUBLIC_URL`. El bucket/Worker de producción también debe denegar acceso público directo al prefijo `transaction_vouchers/`. Si el dominio R2 actual publica todo el bucket, aplicar esa regla antes del despliegue.

## Auditoría

- Se registran logins, refresh, logout, mutaciones y fallos relevantes con `request_id`, actor, origen e IP confiable.
- No se registran lecturas GET exitosas ordinarias.
- La lista de eventos omite snapshots y user-agent; el detalle los entrega únicamente con `audit.view`.
- El redactor elimina contraseñas, tokens, códigos, cookies y rutas de archivos; enmascara cuentas y documentos.
- No existen endpoints para modificar o borrar auditoría. En infraestructura, el rol SQL de la aplicación debe carecer de `UPDATE`/`DELETE` sobre el esquema `audit` cuando la separación de roles esté disponible.

Los rate limits locales son una segunda barrera. En despliegues con varios workers o réplicas debe existir además un límite distribuido en Cloudflare, gateway o proxy para login, registro, reset y contacto.

## URLs canónicas

OpenAPI solo publica paths sin `/` final, salvo `/`. La variante legacy con una sola barra final es un alias oculto directo: no responde 307/308 y añade `Deprecation: true`.

Gates:

```bash
alembic heads
pytest -q -m 'not integration'
```

En backoffice:

```bash
npm run check
npm run build
```

En WWW:

```bash
npm run check:api-paths
npx vue-tsc --noEmit
npm run build
```
