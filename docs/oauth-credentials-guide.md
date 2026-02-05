# Guía: Obtener credenciales OAuth (Google y Facebook)

Esta guía explica cómo obtener los **Client ID**, **Client Secret** y configurar las **redirect URIs** para el login con Google y Facebook en tu API.

---

## 1. Google OAuth

### 1.1 Crear proyecto en Google Cloud Console

1. Entra a **[Google Cloud Console](https://console.cloud.google.com/)**.
2. Inicia sesión con tu cuenta de Google.
3. En la barra superior, haz clic en el selector de proyectos → **"Nuevo proyecto"**.
4. Nombre del proyecto (ej. `Com Brasper API`) → **Crear**.

### 1.2 Activar la API de Google+ / OAuth

1. En el menú lateral: **APIs y servicios** → **Biblioteca**.
2. Busca **"Google+ API"** o **"Google Identity"** (las credenciales OAuth 2.0 funcionan con la pantalla de consentimiento de Google).
3. En la práctica, las credenciales OAuth 2.0 se usan con la **pantalla de consentimiento de OAuth**. Ve a **APIs y servicios** → **Pantalla de consentimiento de OAuth**.

### 1.3 Configurar la pantalla de consentimiento

1. **APIs y servicios** → **Pantalla de consentimiento de OAuth**.
2. Si te pide elegir tipo de usuario:
   - **Externo**: para que cualquier usuario con cuenta Google pueda iniciar sesión (recomendado para producción).
   - **Solo para pruebas**: solo cuentas que agregues como “probadores”.
3. Completa:
   - **Nombre de la aplicación**: ej. `Com Brasper API`.
   - **Correo de asistencia**: tu email.
   - **Dominios autorizados** (si usas dominio propio).
4. En **Alcances**, añade (si los necesitas):
   - `openid`
   - `email`
   - `profile`
5. Guarda.

### 1.4 Crear credenciales OAuth 2.0

1. **APIs y servicios** → **Credenciales**.
2. **+ Crear credenciales** → **ID de cliente de OAuth**.
3. Tipo de aplicación: **Aplicación web**.
4. **Nombre**: ej. `Com Brasper Web Client`.
5. **URIs de redirección autorizados** (importante):
   - Desarrollo local: `http://localhost:8000/integraciones/oauth/google/callback`
   - Producción: `https://tu-dominio.com/integraciones/oauth/google/callback`
   - Añade todas las URLs que uses (con/sin puerto, con/sin `www` si aplica).
6. **Crear**.
7. Se mostrará:
   - **ID de cliente** → es tu `client_id`.
   - **Secreto de cliente** → es tu `client_secret` (guárdalo en lugar seguro).

### 1.5 Guardar en la base de datos (Integration)

En la tabla `integrations.integration` crea o actualiza un registro:

- **name**: `Login con Google`
- **provider**: `google`
- **integration_type**: `oauth`
- **config** (JSON):

```json
{
  "client_id": "XXXXXXXX.apps.googleusercontent.com",
  "client_secret": "GOCSPX-xxxxxxxxxxxxxxxx",
  "redirect_uri": "https://tu-api.com/integraciones/oauth/google/callback"
}
```

- **enable**: `true`

`redirect_uri` debe coincidir **exactamente** con una de las URIs que configuraste en Google (incluyendo `http`/`https`, dominio y path).

---

## 2. Facebook (Meta) OAuth

### 2.1 Crear app en Meta for Developers

1. Entra a **[Meta for Developers](https://developers.facebook.com/)** (antes Facebook Developers).
2. Inicia sesión con tu cuenta de Facebook.
3. **Mis aplicaciones** → **Crear aplicación**.
4. Tipo: **Consumidor** (para login con Facebook en tu sitio/app).
5. Nombre de la aplicación: ej. `Com Brasper API`.
6. Correo de contacto y opciones que pida → **Crear aplicación**.

### 2.2 Añadir producto “Inicio de sesión con Facebook”

1. En el panel de tu app, en **Productos**, busca **Inicio de sesión con Facebook** (Facebook Login).
2. **Configurar**.
3. Elige **Web** como plataforma.
4. URL del sitio (ej. `https://tu-dominio.com` o `http://localhost:8000`) → **Guardar**.

### 2.3 Configurar URIs de redirección

1. En el menú lateral: **Inicio de sesión con Facebook** → **Configuración**.
2. En **URIs de redirección de OAuth válidos** añade:
   - Desarrollo: `http://localhost:8000/integraciones/oauth/facebook/callback`
   - Producción: `https://tu-dominio.com/integraciones/oauth/facebook/callback`
3. **Guardar cambios**.

### 2.4 Obtener App ID y App Secret

1. En el panel de la app: **Configuración** → **Básica**.
2. Ahí verás:
   - **ID de aplicación** → es tu `client_id`.
   - **Secreto de la aplicación** → haz clic en **Mostrar** para ver el `client_secret` (guárdalo en lugar seguro).

### 2.5 Modo desarrollo vs en vivo

- Por defecto la app está en **Modo desarrollo**: solo pueden iniciar sesión los usuarios que sean “probadores”/administradores de la app.
- Para que cualquier usuario pueda usar “Iniciar sesión con Facebook”, debes pasar la app a **En vivo** (arriba a la izquierda: selector de modo → **En vivo**). Puede pedir revisión de Meta según el uso.

### 2.6 Guardar en la base de datos (Integration)

En la tabla `integrations.integration` crea o actualiza un registro:

- **name**: `Login con Facebook`
- **provider**: `facebook`
- **integration_type**: `oauth`
- **config** (JSON):

```json
{
  "client_id": "TU_APP_ID",
  "client_secret": "TU_APP_SECRET",
  "redirect_uri": "https://tu-api.com/integraciones/oauth/facebook/callback"
}
```

- **enable**: `true`

`redirect_uri` debe coincidir **exactamente** con una de las URIs que configuraste en Meta.

---

## 3. Variables de entorno (API)

En tu `.env` define la URL base pública de tu API para que los callbacks se armen bien:

```env
# URL pública de la API (sin barra final)
# Desarrollo:
PUBLIC_URL=http://localhost:8000

# Producción:
# PUBLIC_URL=https://api.tudominio.com
```

Si no pones `redirect_uri` en el `config` de cada integración, la API usará por defecto:

- Google: `{PUBLIC_URL}/integraciones/oauth/google/callback`
- Facebook: `{PUBLIC_URL}/integraciones/oauth/facebook/callback`

---

## 4. Resumen rápido

| Proveedor | Dónde se obtiene | Qué guardas en `config` |
|-----------|------------------|--------------------------|
| **Google** | [Google Cloud Console](https://console.cloud.google.com/) → Credenciales → ID de cliente OAuth | `client_id`, `client_secret`, `redirect_uri` |
| **Facebook** | [Meta for Developers](https://developers.facebook.com/) → Tu app → Configuración → Básica | `client_id` (App ID), `client_secret` (App Secret), `redirect_uri` |

- **redirect_uri**: la misma en la consola del proveedor y en el `config` (y en `PUBLIC_URL` si usas el valor por defecto).
- **Nunca** subas `client_secret` al repositorio; guárdalo en `.env` o en la base (tabla `integrations.integration`) con las mismas precauciones que una contraseña.

Si quieres, el siguiente paso puede ser un ejemplo de request (POST/GET) para crear/actualizar el registro de integración desde tu API o desde SQL.
