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

| Valor      | Descripción                          |
|-----------|--------------------------------------|
| `pending` | Pendiente                            |
| `completed` | Completada                         |
| `failed`  | Fallida                              |
| `checked` | Verificada (checklist marcado)       |

**Nota:** El estado `checked` se asigna automáticamente cuando `checked: true` en POST o PUT.

---

### GET /transactions/

**Lista transacciones** con filtros opcionales.

**Query params:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `status` | string | `pending`, `completed`, `failed`, `checked` |
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
  "user_id": "uuid",
  "tax_rate_id": "uuid",
  "commission_id": "uuid",
  "status": "pending",
  "origin_amount": 1000,
  "destination_amount": 950,
  "code": "TXN-ABC123",
  "commission_result": 50,
  "total_to_send": 1000,
  "checked": false
}
```

**Lógica `checked`:**
- Si `checked: true` → el backend asigna `status: "checked"` automáticamente.
- Si `checked: false` → se usa el `status` enviado.

---

### PUT /transactions/

**Actualiza transacción.** Todos los campos opcionales (solo los enviados se actualizan).

**Request (JSON):**
```json
{
  "id": "uuid-transaccion",
  "status": "completed",
  "checked": true
}
```

**Lógica `checked`:**
- Si `checked: true` → el backend asigna `status: "checked"` automáticamente.

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

Ver `docs/guia-frontend-importacion-excel.md` para mapeo Excel → JSON.

---

## DTOs principales

### TransactionReadDTO

```typescript
interface TransactionReadDTO {
  id: string;
  bank_account_origin_id: string;
  bank_account_destination_id: string;
  user_id: string;
  tax_rate_id: string;
  commission_id: string;
  status: "pending" | "completed" | "failed" | "checked";
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

### Checklist y status

- `checked`: boolean del checklist (UI).
- `status`: estado de la transacción.
- Cuando el usuario marca el checklist (`checked: true`), el backend asigna `status: "checked"`.
- En listados y detalle, usar ambos campos para mostrar estado y checkbox.

---

## Referencias

- **Importación Excel:** `docs/guia-frontend-importacion-excel.md`
- **Perfil de usuario:** `docs/USER_PROFILE_API.md`
- **OpenAPI/Swagger:** `{base}/docs`
