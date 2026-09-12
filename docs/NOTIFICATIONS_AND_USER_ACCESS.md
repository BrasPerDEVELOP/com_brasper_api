# Avisos internos, observaciones y acceso por usuario

Implementación del plan del 2026-09-07. Migraciones: `079` y `080`.

## Contrato

- `GET /notifications?page=1&page_size=20`: `items`, `total`, `unread_count`, `page`, `page_size`. Solo destinatario autenticado; requiere `notifications.view`.
- `POST /notifications/{id}/read`, `POST /notifications/read-all`: lectura propia; la primera devuelve 404 para avisos ajenos.
- `POST /notifications/avisos`: `{title, body, recipient_user_ids}`; requiere `notifications.create`. Los destinatarios deben ser staff activo. Máximo 200 destinatarios; duplicados se notifican una sola vez.
- `GET /notifications/staff`: id, nombre y rol del equipo interno; sin email ni teléfono. Disponible para consultar/publicar avisos o crear/editar transacciones.
- POST/PUT de transacciones: `observaciones` y `mentioned_user_ids`; en multipart los IDs se codifican como array JSON. Las notificaciones se agregan a la misma sesión de la transacción antes del commit.
- POST/PUT de usuarios: `permissions_granted` y `permissions_revoked` como arrays JSON en multipart. Requieren `users.update` y `roles.permissions.update`; no se permite modificar los propios deltas. Roles admin/client no admiten deltas no vacíos. Cambiar de rol limpia ambos deltas.
- Login, OAuth y `/auth/me` devuelven permisos efectivos y deltas. `permissions_customized` se calcula, no se persiste.

Los permisos efectivos son `(rol ∪ granted) − revoked ∪ garantizados`; admin conserva todos. Una matriz vacía se respeta. Contabilidad garantiza `accounting.view`.

## Pruebas locales

Instalar `requirements-test.txt` en un entorno virtual y ejecutar:

```powershell
.venv/Scripts/python.exe scripts/test_local.py -q -m "not integration"
```

El runner usa credenciales ficticias y puertos locales sin servicios. Las pruebas R2 reales se excluyen explícitamente. Las migraciones tienen pruebas de operaciones y compilación PostgreSQL, sin ejecutar cambios en producción.

## Publicación

Aplicar `alembic upgrade head` con la configuración real del entorno antes de iniciar la API actualizada. Publicar después el backoffice. Las migraciones no se aplicaron a ninguna base real durante el desarrollo de esta tarea.
