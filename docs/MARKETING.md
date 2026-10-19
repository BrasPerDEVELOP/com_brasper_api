# Marketing: correos masivos

La API usa Gmail SMTP con STARTTLS, un correo individual por destinatario y una cola persistente en PostgreSQL. El backoffice está en `/app/marketing`.

## Activación

1. Aplicar `python -m alembic upgrade head` (migración 088, agrega tres tablas sin modificar datos existentes).
2. Configurar en el `.env` privado del backend: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_TLS=true`, `PUBLIC_URL` (base HTTPS pública de esta API, incluyendo el prefijo del proxy si corresponde), `MARKETING_ENABLED=true`.
3. Reiniciar la API. El worker arranca con el lifespan de FastAPI.
4. Dar `marketing.view`, `marketing.create`, `marketing.send` al equipo. El rol Marketing los incluye por defecto; si hay una matriz de permisos personalizada guardada, actualizarla en Roles y permisos. Admin tiene acceso automáticamente.
5. Crear borrador, revisar destinatarios, enviar una prueba y confirmar el envío masivo desde la interfaz.

Nunca incluir la contraseña en variables VITE, documentación, commits o respuestas HTTP. La configuración pública solo devuelve remitente y disponibilidad.

## Cola y límites

`MARKETING_INTERVAL_SECONDS=10` controla la pausa mínima global. `MARKETING_DAILY_LIMIT=400` limita los intentos masivos en una ventana móvil de 24 horas; la cola espera automáticamente al alcanzar el límite. Estos límites internos no sustituyen los del proveedor y no cuentan otros correos enviados por la cuenta ni las pruebas manuales.

Un bloqueo transaccional PostgreSQL impide que varios workers envíen simultáneamente. Antes de contactar SMTP se guarda `processing`; después, `sent` o `failed`. Un reinicio retoma los pendientes y no reintenta entregas ambiguas, evitando duplicados. Un registro `processing` que persiste tras un reinicio requiere revisión manual del proveedor. No reenviar automáticamente: el servidor pudo haber aceptado el mensaje.

`sent` significa aceptado por SMTP, no confirma llegada a bandeja ni lectura. No hay seguimiento de aperturas o rebotes del proveedor. Los fallos guardan un mensaje genérico, nunca la excepción SMTP.

Cada correo incluye una URL de baja firmada sin caducidad. GET muestra confirmación y POST registra una exclusión global, que el worker consulta antes de cada entrega. Abrir el enlace desde un escáner no registra una baja. Solo se incluyen contactos con autorización confirmada en el formulario. Excel/CSV se procesa localmente, solo se envían a la API las direcciones seleccionadas; máximo 10 000 por campaña y archivo de 5 MB.

## Verificación

Backend: `python -m pytest tests/test_marketing.py tests/test_role_permissions.py -q`.
Frontend: `pnpm run check` y compilación Vite. Las pruebas SMTP usan un cliente simulado y no envían correos reales.
