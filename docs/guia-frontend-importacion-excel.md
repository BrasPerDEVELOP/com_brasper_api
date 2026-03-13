# Guía: Importación de transacciones desde Excel

Guía para el equipo frontend: cómo parsear el Excel de transacciones y enviarlo al endpoint de importación.

---

## 1. Estructura del Excel

El archivo tiene **25 columnas** (fila 1 = encabezados):

| # | Columna Excel | Descripción | Ejemplo |
|---|---------------|-------------|---------|
| 1 | Fecha del envío | Fecha de envío (ISO o datetime) | `2026-02-01 00:00:00` |
| 2 | Hora | Hora (puede estar vacío) | |
| 3 | N° de envío | Número de envío | `4`, `10` |
| 4 | Nombre | Nombre completo del **receptor** (Brasil) | `Gustavo Martin Bravo Tantalean` |
| 5 | Cliente | Tipo de cliente | `HABITUAL` |
| 6 | Documento | Tipo documento (DNI, CE, etc.) | `DNI` |
| 7 | DNI/CE | Número documento o CPF (Brasil) | `9443212`, `OOO972676` |
| 8 | Correo | Email del **receptor** | `Gmbt01@gmail.com` |
| 9 | TC | Tipo de cambio | `1.6` |
| 10 | ENVÍA (PEN) | Monto origen en soles | `18000` |
| 11 | Tipo de cambio | TC aplicado | `1.566` |
| 12 | Tasa | Tasa | `0.028` |
| 13 | Factor | Factor | `0.972` |
| 14 | Comisión (CLIENTE) | Comisión (formato `S/ 331.11`) | `S/  331.11` |
| 15 | Impuesto Interno | Impuesto | `S/  50.51` |
| 16 | Total Enviar | Total a enviar (formato `S/ 11,494.25`) | `S/  11,494.25` |
| 17 | RECIBE (BRL) | Monto destino en reales | `11825.36` |
| 18 | Descuento Fijo (F) | | |
| 19 | Descuento variable | | |
| 20 | RECIBE CON DESC. FIJO (BRL) | | |
| 21 | RECIBE FIJO (BRL) | | |
| 22 | COMPROBANTE SOLES | | |
| 23 | Banco | Empresa/canal | `Ingenitech`, `Brasper` |
| 24 | Cuenta | Banco Perú (origen) | `BCP`, `Interbank` |
| 25 | ESTADO | Estado de la transacción | `Enviado` |

---

## 2. Mapeo Excel → API

Cada **fila** del Excel (desde la 2) = **1 item** de importación.

### Flujo de datos (Perú → Brasil)

- **Origen (Perú)**: Quien envía. Cuenta en BCP/Interbank.
- **Destino (Brasil)**: Quien recibe. Datos: Nombre, Correo, DNI/CE (o CPF). PIX por email.

### Mapeo de columnas

| API (campo) | Columna Excel | Notas |
|-------------|---------------|-------|
| **user_origin** | | Usuario emisor (Perú). Puede ser fijo o configurable. |
| user_origin.user.names | (configurable) | Ej: "Ingenitech" o datos del operador |
| user_origin.user.lastnames | (configurable) | |
| user_origin.user.email | (configurable) | Email del emisor |
| user_origin.user.password | (configurable) | Contraseña por defecto para importación |
| user_origin.bank_account.bank_id | **Cuenta** (col 24) | Resolver "BCP" → UUID vía `GET /transactions/banks/` |
| user_origin.bank_account.account_flow | fijo | `"origin"` |
| user_origin.bank_account.account_holder_type | fijo | `"naturalPerson"` o `"legalEntity"` |
| user_origin.bank_account.bank_country | fijo | `"pe"` |
| **user_destination** | | Receptor en Brasil |
| user_destination.user.names | **Nombre** (col 4) | Partir por espacio: primer nombre |
| user_destination.user.lastnames | **Nombre** (col 4) | Resto del nombre |
| user_destination.user.email | **Correo** (col 8) | |
| user_destination.user.password | (generar) | Ej: `Import${random}!` |
| user_destination.bank_account.bank_id | (obtener BR) | UUID de un banco Brasil vía API |
| user_destination.bank_account.account_flow | fijo | `"destination"` |
| user_destination.bank_account.account_holder_type | fijo | `"naturalPerson"` |
| user_destination.bank_account.bank_country | fijo | `"br"` |
| user_destination.bank_account.pix_key | **Correo** (col 8) | Usar email como clave PIX |
| user_destination.bank_account.pix_key_type | fijo | `"email"` |
| user_destination.bank_account.holder_names | **Nombre** (col 4) | |
| user_destination.bank_account.holder_surnames | **Nombre** (col 4) | Apellidos |
| user_destination.bank_account.document_number | **DNI/CE** (col 7) | Parsear a número (quitar puntos) |
| **transaction** | | |
| transaction.tax_rate_id | (obtener API) | `GET /coin/tax-rate/` → primer id |
| transaction.commission_id | (obtener API) | `GET /coin/commission/` → primer id |
| transaction.status | **ESTADO** (col 25) | Mapear: `Enviado` → `"completed"` |
| transaction.origin_amount | **ENVÍA (PEN)** (col 10) | Número |
| transaction.destination_amount | **RECIBE (BRL)** (col 17) | Número |
| transaction.commission_result | **Comisión** (col 14) | Parsear `S/ 331.11` → `331.11` |
| transaction.total_to_send | **Total Enviar** (col 16) | Parsear `S/ 11,494.25` → `11494.25` |
| transaction.send_date | **Fecha del envío** (col 1) | `YYYY-MM-DD` |
| transaction.payment_date | **Fecha del envío** (col 1) | Mismo valor o calcular |

---

## 3. APIs necesarias antes de importar

El frontend debe obtener estos IDs (una vez al cargar la pantalla o al subir el archivo):

```http
GET /transactions/banks/
GET /transactions/banks/names
GET /coin/tax-rate/
GET /coin/commission/
```

### Resolver banco por nombre

```javascript
// Ejemplo: resolver "BCP" (Perú) a UUID
const banks = await api.get('/transactions/banks/', { params: { currency: 'PEN' } });
const bankBCP = banks.data.find(b => 
  b.bank?.toLowerCase().includes('bcp') || 
  b.company?.toLowerCase().includes('bcp')
);
const bankIdOrigin = bankBCP?.id;

// Banco destino Brasil (cualquiera con BRL)
const bankBR = banks.data.find(b => b.country === 'br' && b.currency === 'BRL');
const bankIdDestination = bankBR?.id;
```

### Tax rate y commission

```javascript
const taxRates = await api.get('/coin/tax-rate/');
const commissions = await api.get('/coin/commission/');
const taxRateId = taxRates.data[0]?.id;
const commissionId = commissions.data[0]?.id;
```

---

## 4. Parseo de valores

### Montos con formato `S/ 1,234.56`

```javascript
function parseAmount(str) {
  if (str == null || str === '') return null;
  const cleaned = String(str).replace(/S\/\s*|R\$\s*|,/g, '').trim();
  return parseFloat(cleaned) || null;
}
```

### Fecha

```javascript
function parseDate(val) {
  if (!val) return null;
  const d = new Date(val);
  return isNaN(d.getTime()) ? null : d.toISOString().slice(0, 10); // YYYY-MM-DD
}
```

### Dividir nombre en names + lastnames

```javascript
function splitName(fullName) {
  const parts = String(fullName || '').trim().split(/\s+/);
  if (parts.length <= 1) return { names: fullName || '', lastnames: '' };
  return {
    names: parts[0],
    lastnames: parts.slice(1).join(' ')
  };
}
```

### Mapear ESTADO → status

```javascript
const statusMap = {
  'Enviado': 'completed',
  'Pendiente': 'pending',
  'Fallido': 'failed'
};
const status = statusMap[row[24]] || 'pending';
```

---

## 5. Estructura JSON a enviar

```json
{
  "items": [
    {
      "user_origin": {
        "user": {
          "names": "Ingenitech",
          "lastnames": "Operaciones",
          "email": "ops@empresa.com",
          "password": "Import123!"
        },
        "bank_account": {
          "bank_id": "uuid-del-banco-bcp",
          "account_flow": "origin",
          "account_holder_type": "naturalPerson",
          "bank_country": "pe"
        }
      },
      "user_destination": {
        "user": {
          "names": "Gustavo",
          "lastnames": "Martin Bravo Tantalean",
          "email": "Gmbt01@gmail.com",
          "password": "Import123!"
        },
        "bank_account": {
          "bank_id": "uuid-del-banco-brasil",
          "account_flow": "destination",
          "account_holder_type": "naturalPerson",
          "bank_country": "br",
          "holder_names": "Gustavo",
          "holder_surnames": "Martin Bravo Tantalean",
          "pix_key": "Gmbt01@gmail.com",
          "pix_key_type": "email"
        }
      },
      "transaction": {
        "tax_rate_id": "uuid-tax-rate",
        "commission_id": "uuid-commission",
        "status": "completed",
        "origin_amount": 18000,
        "destination_amount": 11825.36,
        "commission_result": 331.11,
        "total_to_send": 11494.25,
        "send_date": "2026-02-01",
        "payment_date": "2026-02-01"
      }
    }
  ]
}
```

---

## 6. Endpoint

```http
POST /transactions/import/
Content-Type: application/json
Authorization: Bearer <token>

{ "items": [...] }
```

**Respuesta exitosa (201):**

```json
{
  "created_transactions": 148,
  "created_users": 120,
  "created_bank_accounts": 120,
  "message": "Importación completada"
}
```

---

## 7. Librerías recomendadas (frontend)

- **React/Vue**: `xlsx` (SheetJS) o `exceljs` para leer el archivo
- **Ejemplo con xlsx**:

```javascript
import * as XLSX from 'xlsx';

const file = event.target.files[0];
const data = await file.arrayBuffer();
const workbook = XLSX.read(data, { type: 'array' });
const sheet = workbook.Sheets[workbook.SheetNames[0]];
const rows = XLSX.utils.sheet_to_json(sheet, { header: 1 });

// rows[0] = headers, rows[1..] = datos
const items = rows.slice(1).map(row => mapRowToItem(row, banks, taxRateId, commissionId));
await api.post('/transactions/import/', { items });
```

---

## 8. Índices de columnas (0-based para código)

| Índice | Columna |
|--------|---------|
| 0 | Fecha del envío |
| 1 | Hora |
| 2 | N° de envío |
| 3 | Nombre |
| 4 | Cliente |
| 5 | Documento |
| 6 | DNI/CE |
| 7 | Correo |
| 8 | TC |
| 9 | ENVÍA (PEN) |
| 10 | Tipo de cambio |
| 11 | Tasa |
| 12 | Factor |
| 13 | Comisión (CLIENTE) |
| 14 | Impuesto Interno |
| 15 | Total Enviar |
| 16 | RECIBE (BRL) |
| 17-21 | Descuentos / RECIBE... |
| 22 | COMPROBANTE SOLES |
| 23 | Banco |
| 24 | Cuenta |
| 25 | ESTADO |

---

## 9. Consideraciones

1. **user_origin fijo**: Si todas las transacciones vienen del mismo emisor (ej. Ingenitech), usar un usuario/cuenta fija para `user_origin`.
2. **Duplicados**: Si el mismo email (destino) aparece en varias filas, el backend puede crear usuarios duplicados. Valorar lógica de "crear o buscar por email".
3. **Validación**: Validar filas vacías, emails inválidos y montos antes de enviar.
4. **Lotes**: Si hay muchas filas (>100), considerar enviar en lotes para evitar timeouts.
