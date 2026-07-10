# API Com Brasper – Documentación para Frontend

Documentación de endpoints y contratos para integración con el frontend.

---

## Base URL

```
https://apibras.finzeler.com
```

O en desarrollo: `http://localhost:8000`

---

## Autenticación

Las rutas protegidas requieren header:

```
Authorization: Bearer <access_token>
```

### POST /auth/login/

**Login** – Acepta JSON o form-urlencoded.

**Request (JSON):**
```json
{
  "username": "email@ejemplo.com",
  "password": "MiClave123!"
}
```

**Response (200):**
```json
{
  "token": "opaque-token-string",
  "user": {
    "id": "uuid",
    "names": "Juan",
    "lastnames": "Pérez",
    "email": "juan@ejemplo.com",
    "profile_image": "profile_images/xxx.jpg",
    "document_number": "12345678",
    "role": "sales"
  }
}
```

**Response (form-urlencoded):**
```json
{
  "access_token": "opaque-token-string",
  "token_type": "bearer",
  "user": { ... }
}
```

### GET /auth/me/

**Perfil del usuario autenticado** – Requiere token.

**Response (200):** `UserReadDTO` (perfil completo).

---

## Usuarios

### GET /user/sales-ids/

**IDs de usuarios con rol sales** – Útil para filtros y dropdowns.

**Response (200):**
```json
["uuid-1", "uuid-2", "uuid-3"]
```

### GET /user/?role=sales

**Lista usuarios** filtrados por rol.

---

## Transacciones

Prefijo: `/transactions`

### Estados (TransactionStatus)

| Valor | Significado en UI (sugerido) | Cuándo lo pone el backend |
|-------|------------------------------|---------------------------|
| `verification` | En verificación | Alta nueva: checklist desmarcado (`checked: false`). Es el estado por defecto al crear. |
| `verified` | Verificado (checklist OK, datos incompletos) | `checked: true` pero aún faltan campos para cerrar la operación (ver tabla de completitud abajo). |
| `completed` | Finalizada / completada | `checked: true` **y** todos los campos de cierre están presentes (misma tabla). |
| `failed` | Fallida | Error o flujo marcado como fallido; **no** se recalcula automáticamente con el checklist. |
| `pending` | (Legado) | Puede aparecer en datos antiguos; las **nuevas** altas usan `verification`. |
| `checked` | (Legado) | Valor antiguo equivalente a “verificado”; en datos migrados puede haberse normalizado a `verified`. |

**Migración de API:** conviene mostrar `verification` / `verified` / `completed` / `failed` en filtros y badges. Mantener compatibilidad leyendo `pending` / `checked` si hace falta en histórico.

---

### Flujo checklist ↔ `status` (obligatorio para el front)

1. **Crear transacción (POST)**  
   - El backend **fuerza** `checked: false` y `status: "verification"` aunque el cliente envíe otro valor.  
   - El usuario **no** puede dejar el checklist activo en el alta; se completa después con PUT.
   - **`send_date`:** se guarda **automáticamente** con la fecha y hora UTC del momento de creación (el cliente no necesita enviarla; si la envía, el servidor la sobrescribe en el alta).

2. **Actualizar (PUT)**  
   - Tras guardar, el backend **recalcula** `status` según `checked` y los demás campos (salvo que `status` sea `failed`).  
   - No confiar en un `status` enviado manualmente para simular el flujo: el servidor puede sobrescribirlo según la regla siguiente.

3. **Regla de derivación** (resumen):

   - `checked === false` → `status = "verification"`  
   - `checked === true` y **falta** algún campo de la lista de completitud → `status = "verified"`  
   - `checked === true` y **todos** los campos de completitud están presentes → `status = "completed"`  
   - `status === "failed"` → no se altera por el checklist

4. **Campos que deben estar completos para pasar a `completed`** (todos a la vez, con checklist en `true`):

   - `commission_result` (no `null`)
   - `total_to_send` (no `null`)
   - `send_date` (no `null`; en la práctica ya viene del alta automática)
   - `send_voucher` (string no vacío; típicamente path/URL tras subir archivo)
   - `payment_voucher` (string no vacío)

5. **`payment_date`:** el backend la asigna **solo** cuando la transacción pasa a `status: "completed"` (primera vez que queda finalizada): fecha y hora **UTC** de ese momento. No hace falta enviarla para cumplir la regla de completitud.

El front puede usar `status` para badges y `checked` para el control del checklist; si muestran “progreso hacia completada”, basta con comprobar los campos anteriores (sin contar `payment_date` hasta que el estado sea `completed`).

---

### GET /transactions/

**Lista transacciones** con filtros opcionales.

**Query params:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `status` | string | Ej.: `verification`, `verified`, `completed`, `failed`, `pending`, `checked` (según enum actual) |
| `user_id` | UUID | Filtro por usuario |
| `bank_account_origin_id` | UUID | Cuenta origen |
| `bank_account_destination_id` | UUID | Cuenta destino |
| `created_at_from` | datetime ISO | Desde fecha |
| `created_at_to` | datetime ISO | Hasta fecha |

**Response (200):** `List[TransactionReadDTO]`

---

### GET /transactions/{transaction_id}

**Obtiene una transacción por ID.**

**Response (200):** `TransactionReadDTO`

---

### POST /transactions/

**Crea transacción.** Acepta JSON o form-data (multipart).

**Request (JSON):**
```json
{
  "bank_account_origin": "uuid",
  "bank_account_destination": "uuid",
  "social_reason_bank_id": "uuid-banco-razon-social",
  "user_id": "uuid",
  "tax_rate_id": "uuid",
  "commission_id": "uuid",
  "status": "verification",
  "origin_amount": 1000,
  "destination_amount": 950,
  "code": "",
  "commission_result": 50,
  "total_to_send": 1000,
  "checked": false
}
```

**Comportamiento en POST (importante):**

- El backend **ignora** `checked: true` en creación: siempre guarda `checked: false` y `status: "verification"`.
- El `status` enviado en el body también se normaliza a `verification` en el alta.
- **`send_date`** se fija en servidor al instante de creación (UTC).
- El checklist se marca solo en **actualizaciones** (PUT) cuando corresponda.
- **`code`:** generado en servidor (no usar `TRX-…` ni códigos locales); ver formato en la sección de importación.
- **`social_reason_bank_id`:** identifica la fila exacta del catálogo usada como razón social. Es independiente de `bank_id`, que continúa ligado al banco de la cuenta destino. El servidor deriva `company_name` desde esta selección.

---

### PUT /transactions/

**Actualiza transacción.** Todos los campos opcionales (solo los enviados se actualizan).

**Request (JSON) ejemplo (marcar checklist y completar datos):**
```json
{
  "id": "uuid-transaccion",
  "checked": true,
  "commission_result": 50,
  "total_to_send": 1000,
  "send_voucher": "vouchers/send/xxx.jpg",
  "payment_voucher": "vouchers/payment/yyy.jpg"
}
```

**Comportamiento en PUT:**

- Tras aplicar los cambios, el backend recalcula `status` (`verification` / `verified` / `completed`) según `checked` y la completitud de campos, **excepto** si la transacción está en `failed`.
- Al quedar `completed`, el servidor asigna **`payment_date`** (UTC) en ese momento.
- Enviar `status: "completed"` manualmente no garantiza que quede así: debe cumplirse la regla de completitud + `checked: true`.

---

### DELETE /transactions/{transaction_id}

**Elimina una transacción.** Response: 204 No Content.

---

### POST /transactions/import/

**Importación masiva.** Recibe JSON (el frontend parsea el Excel y envía los datos).

**Request:**
```json
{
  "items": [
    {
      "user_origin": {
        "user": { "names": "...", "lastnames": "...", "email": "...", "password": "..." },
        "bank_account": { "bank_id": "uuid", "account_flow": "origin", "account_holder_type": "naturalPerson", "bank_country": "pe" }
      },
      "user_destination": {
        "user": { ... },
        "bank_account": { "bank_id": "uuid", "account_flow": "destination", "bank_country": "br", "pix_key": "email@ejemplo.com", "pix_key_type": "email" }
      },
      "transaction": {
        "tax_rate_id": "uuid",
        "commission_id": "uuid",
        "origin_amount": 1000,
        "destination_amount": 950,
        "send_date": "2026-02-01",
        "payment_date": "2026-02-01"
      }
    }
  ]
}
```

**Response (201):**
```json
{
  "created_transactions": 10,
  "created_users": 20,
  "created_bank_accounts": 20,
  "message": "Importación completada"
}
```

Cada transacción creada por importación queda con `checked: false` y `status: "verification"` (mismo criterio que POST). El **`code`** lo genera el servidor: formato **`{1ª letra origen}x{1ª letra destino}-{10 dígitos}`** según la tasa (ej. PEN→BRL: `PxB-0000000001`, BRL→PEN: `BxP-0000000001`, USD→BRL: `UxB-…`, BRL→USD: `BxU-…`). El cliente puede omitir `code` en POST o enviarlo vacío; el valor enviado no se usa.

Ver `docs/guia-frontend-importacion-excel.md` para mapeo Excel → JSON.

---

## DTOs principales

### TransactionReadDTO

```typescript
type TransactionStatus =
  | "verification"
  | "verified"
  | "completed"
  | "failed"
  | "pending"   // legado
  | "checked";  // legado

interface TransactionReadDTO {
  id: string;
  bank_account_origin_id: string;
  bank_account_destination_id: string;
  social_reason_bank_id?: string;
  user_id: string;
  tax_rate_id: string;
  commission_id: string;
  status: TransactionStatus;
  origin_amount: number;
  destination_amount: number;
  code: string;
  commission_result?: number;
  total_to_send?: number;
  coupon_id?: string;
  send_date?: string;
  payment_date?: string;
  send_voucher?: string;
  payment_voucher?: string;
  checked: boolean;
  created_at: string;
  created_by?: string;
  updated_at: string;
}
```

### Checklist y `status`

- **`checked`:** control del checklist en UI; en **POST** el servidor siempre lo deja en `false`.
- **`status`:** derivado en servidor según el flujo descrito arriba (`verification` → `verified` → `completed`).
- Para **filtros y etiquetas**, usar `status`; para el **checkbox**, usar `checked` y reflejar en PUT los cambios del usuario.

---

## Referencias

- **Importación Excel:** `docs/guia-frontend-importacion-excel.md`
- **Perfil de usuario:** `docs/USER_PROFILE_API.md`
- **OpenAPI/Swagger:** `{base}/docs`
