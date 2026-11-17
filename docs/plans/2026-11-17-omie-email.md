# PDF de Omie por correo

Se replica el envío explícito de Perú después de emitir: el operador selecciona
los correos del cliente o agrega direcciones sin modificar su ficha. La acción
no emite ni anula una nota fiscal.

- GET `/omie/transactions/{id}/email`: contactos actuales y estado persistido;
  requiere `billing.view` y no consulta Omie.
- POST a la misma ruta: `{ "recipients": ["cliente@example.com"] }`;
  requiere `billing.issue`, valida hasta 20 correos y responde 202.
- Solo se encolan notas `issued` con identificador y número confirmados.
- El poller de comprobantes procesa la cola aunque SUNAT esté deshabilitado.
  Obtiene el PDF oficial con `ObterNFSe`, verifica número, URL, tamaño y firma PDF,
  y envía un adjunto por correo mediante SMTP con TLS.
- Cada destinatario entregado se guarda antes de continuar. Un reintento omite
  esas direcciones; las solicitudes concurrentes no reemplazan un envío activo.
- Si SMTP termina pero falla el registro en la base, se conserva `sending`
  para revisión operativa. No se libera automáticamente para evitar duplicados.
- Ante un fallo parcial, la pantalla permite reintentar solo los pendientes.

## Despliegue

Aplicar `alembic upgrade head` (migración aditiva 099) antes de reiniciar el API
con este modelo. Desplegar después el frontend. Reutiliza la configuración SMTP
de comprobantes y `OMIE_ENABLED`/credenciales existentes; no requiere nuevas keys.
No modifica notas, correlativos ni datos de clientes existentes.

## Interfaz

`OmieEmailPanel` recibe `transactionId` y es responsable de contactos, solicitud
y seguimiento del correo. Se usa en `OmieInvoiceCell` y `OmieInvoicesView`.
Consulta únicamente el endpoint de correo cada cinco segundos mientras haya
un envío activo. Al cerrar el detalle se cancela el seguimiento en pantalla;
la cola del backend continúa.
