# Marketing: correos masivos

La API usa Gmail SMTP con STARTTLS, un correo individual por destinatario y una cola persistente en PostgreSQL. El backoffice está en `/app/marketing`.

## Activación

1. Aplicar `python -m alembic upgrade head` (migración 088, agrega tres tablas sin modificar datos existentes).
2. Configurar en el `.env` privado del backend: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_TLS=true`, `PUBLIC_URL` (base HTTPS pública de esta API, incluyendo el prefijo del proxy si corresponde), `MARKETING_ENABLED=true`.
3. Reiniciar la API. El worker arranca con el lifespan de FastAPI.
4. Dar `marketing.view`, `marketing.create`, `marketing.send` al equipo. El rol Marketing los incluye por defecto; si hay una matriz de permisos personalizada guardada, actualizarla en Roles y permisos. Admin tiene acceso automáticamente.
5. Completar el formulario, enviar una prueba sin guardar y confirmar el envío masivo directamente.

Nunca incluir la contraseña en variables VITE, documentación, commits o respuestas HTTP. La configuración pública solo devuelve remitente y disponibilidad.

## Cola y límites

`MARKETING_INTERVAL_SECONDS=10` controla la pausa mínima global. `MARKETING_DAILY_LIMIT=400` limita los intentos masivos en una ventana móvil de 24 horas; la cola espera automáticamente al alcanzar el límite. Estos límites internos no sustituyen los del proveedor y no cuentan otros correos enviados por la cuenta ni las pruebas manuales.

Un bloqueo transaccional PostgreSQL impide que varios workers envíen simultáneamente. Antes de contactar SMTP se guarda `processing`; después, `sent` o `failed`. Un reinicio retoma los pendientes y no reintenta entregas ambiguas, evitando duplicados. Un registro `processing` que persiste tras un reinicio requiere revisión manual del proveedor. No reenviar automáticamente: el servidor pudo haber aceptado el mensaje.

`sent` significa aceptado por SMTP, no confirma llegada a bandeja ni lectura. No hay seguimiento de aperturas o rebotes del proveedor. Los fallos guardan un mensaje genérico, nunca la excepción SMTP.

Cada correo incluye una URL de baja firmada sin caducidad. GET muestra confirmación y POST registra una exclusión global, que el worker consulta antes de cada entrega. Abrir el enlace desde un escáner no registra una baja. Solo se incluyen contactos con autorización confirmada en el formulario. Excel/CSV se procesa localmente, solo se envían a la API las direcciones seleccionadas; máximo 10 000 por campaña y archivo de 5 MB.

## Verificación

Backend: `python -m pytest tests/test_marketing.py tests/test_role_permissions.py -q`.
Frontend: `pnpm run check` y compilación Vite. Las pruebas SMTP usan un cliente simulado y no envían correos reales.

## Plantilla BrasPer Brasil → Perú (pt-BR)

Las nuevas campañas seleccionan por defecto `brasper_peru_pt_v1`, basado en el HTML y las doce imágenes entregadas. Se puede elegir «Mensaje sencillo». El asunto y el mensaje son editables; el mensaje aparece debajo del banner principal y siempre se escapa como texto. El diseño utiliza tablas, estilos en línea, enlaces HTTPS y ajustes para móvil. El cuerpo HTML pesa menos de 25 KB; las imágenes viajan como partes MIME `inline` referidas por CID, una sola copia por imagen. Se conserva una alternativa de texto.

La migración 089 agrega `template_key` a campañas. Los registros anteriores mantienen `NULL` y conservan el formato original. Un diseño ya usado no debe modificarse: publicar otra versión con una nueva clave y mantener la anterior, para que las pruebas y los envíos pendientes usen la misma plantilla elegida al crear la campaña.

`GET /marketing/templates` devuelve los diseños y textos iniciales. `POST /marketing/preview` genera la vista previa con el mismo renderer del correo y requiere `marketing.view`; se registra como vista previa en auditoría. La vista previa usa imágenes HTTPS de un catálogo público de archivos fijos y se muestra en un iframe aislado. Los correos usan las mismas imágenes HTTPS públicas y una URL de baja firmada exclusiva para el destinatario; el enlace de la vista previa es un marcador sin efectos.

Revisar mediante «Enviar prueba» en los clientes de correo usados antes de una campaña real: la vista del navegador no garantiza compatibilidad exacta en Gmail/Outlook. Ninguna prueba automatizada envía correos.

Dos públicos: Brasil (portugués, brasper_peru_pt_v1) y Perú (español, brasper_brasil_es_v1). Cada campaña conserva su plantilla; el selector no filtra destinatarios por país.


## Entregabilidad
El remitente incluye nombre, Date, Message-ID y cabeceras de baja HTTPS con un clic (POST firmado en /marketing/unsubscribe). El proveedor SMTP debe firmar también las cabeceras List-Unsubscribe y List-Unsubscribe-Post con DKIM para cumplir RFC 8058.
La cuenta SMTP no configura el DNS: verificar SPF, DKIM y DMARC con el original recibido. Gmail puede bloquear imágenes en mensajes sospechosos; no se puede garantizar la bandeja principal desde la aplicación. Las imágenes se cargan mediante HTTPS desde la API pública, sin adjuntos ni referencias CID. Gmail puede bloquearlas si clasifica el correo como sospechoso.


## Envío directo
POST /marketing/test recibe asunto, mensaje, plantilla y email de prueba; respeta las bajas y no crea campañas.
POST /marketing/dispatch requiere marketing.create y marketing.send, consentimiento y MARKETING_ENABLED. Recibe request_id UUID; crea campaña queued y destinatarios en una sola transacción. Un bloqueo transaccional por request_id evita duplicar campañas ante reintentos concurrentes. Reutilizar la clave con datos distintos devuelve 409. La interfaz conserva la clave hasta editar el formulario.
Las rutas antiguas se mantienen para pestañas previas al despliegue y campañas pendientes históricas. La interfaz nueva no crea borradores. No se convierten ni se envían automáticamente campañas anteriores.
