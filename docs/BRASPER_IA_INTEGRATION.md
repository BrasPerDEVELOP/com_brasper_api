# Integración privada con el bot Brasper

Los endpoints bajo `/brasper/ai` son de mínimo privilegio y no permiten crear
transacciones. Todos exigen el header `X-Brasper-IA-Secret`, comparado con la
variable de entorno `BRASPER_IA_SHARED_SECRET`. Si la variable está vacía, la
integración falla cerrada con HTTP 503.

## Contratos

- `GET /brasper/ai/clients/lookup`: busca puntualmente por teléfono o nombre. No
  lista clientes ni devuelve el número de documento.
- `POST /brasper/ai/clients/upsert`: crea o actualiza de forma idempotente,
  priorizando documento y luego teléfono. Rechaza identidades cruzadas.
- `GET /brasper/ai/deposit-accounts?currency=PEN`: devuelve exclusivamente las
  cuentas oficiales activas de la moneda solicitada.

Las respuestas de cliente incluyen `is_first_transfer`, calculado con las
transacciones reales, y `document_verified`, sin exponer el documento completo.

## Despliegue

Configurar el mismo valor secreto en la API y en el entorno de `com_brasper_ia`:

```env
BRASPER_IA_SHARED_SECRET=valor-aleatorio-largo
```

Rotar el secreto implica actualizar ambos servicios y reiniciarlos en una ventana
coordinada. Nunca guardar el valor en Git ni imprimirlo en logs.
