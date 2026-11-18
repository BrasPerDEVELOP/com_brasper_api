# Consulta de documentos al crear usuarios

`POST /user/document-lookup` recibe `document_type` (`dni`, `ruc`, `cpf`, `cnpj`)
y `document_number`. Requiere una sesión y permiso `users.create` o `users.update`,
incluso cuando el registro público está habilitado. No escribe en la base de datos.

Devuelve exclusivamente tipo, número normalizado, `names`, `lastnames` y `source`.
DNI separa nombres/apellidos; CPF devuelve el nombre completo en `names`; RUC/CNPJ
devuelven la razón social. No implica aprobación KYC ni identidad verificada.

Variables exclusivas del backend (en `.env`, nunca Git ni `VITE_*`):

- `APIPERU_TOKEN`, `APIPERU_BASE_URL` (predeterminado `https://apiperu.dev/api`).
- `CPFCNPJ_TOKEN`, `CPFCNPJ_BASE_URL` (predeterminado `https://api.cpfcnpj.com.br`).

Docker Compose transmite estas variables al servicio `api`. No requiere migración.
APIPERU usa POST DNI/RUC y Bearer. CPF.CNPJ usa GET con token en ruta, paquete
1 para CPF y 4 para CNPJ (solo nombre). El transporte no registra URLs ni sigue
redirecciones; errores externos se traducen sin exponer credenciales o respuesta cruda.
No reintenta consultas automáticamente ni realiza consultas al escribir cada carácter.

El backoffice solicita la consulta con «Consultar datos», ignora respuestas atrasadas
y solo autocompleta nombres vacíos. «Usar estos datos» permite reemplazar manualmente
un nombre existente. Los documentos sin servicio disponible pueden ingresarse manualmente.

Referencias oficiales consultadas:
- https://docs.apiperu.dev/referencia/consultar-dni/
- https://docs.apiperu.dev/referencia/consultar-ruc/
- https://api.cpfcnpj.com.br/doc/openapi.json

Validación automatizada: `pytest tests/test_document_lookup.py` (proveedores simulados).
Las pruebas no consumen créditos ni consultan personas reales. La disponibilidad real
depende de credenciales, saldo y restricciones de IP del proveedor.
