# Ejecutar en el servidor con Docker y Nginx

## Requisitos

- Docker y Docker Compose instalados en el servidor.
- Puerto 80 (y opcionalmente 443) libres para Nginx.

## Arquitectura

```
Internet → Nginx (80/443) → API (8000) → PostgreSQL (5432)
```

La entrada pública es **Nginx** en el puerto **80**. La API no expone puerto al host; solo Nginx y (opcional) PostgreSQL.

## Levantar la aplicación en el servidor

### 1. Clonar (si aún no está) y entrar al proyecto

```bash
cd /ruta/donde/está/com_brasper_api
```

### 2. Crear `.env`

Copia `.env.example` a `.env` y edita los valores (sobre todo `POSTGRES_PASSWORD` y `SECRET_KEY`):

```bash
cp .env.example .env
nano .env   # o vim, etc.
```

Con Docker, el compose sobrescribe `POSTGRES_HOST` para que la API use el contenedor `db`; el resto de variables se leen del `.env`.

### 3. Levantar todo (Nginx + API + PostgreSQL)

```bash
docker compose up -d --build
```

- `--build`: construye la imagen de la API la primera vez o tras cambios.
- `-d`: ejecuta en segundo plano.

### 4. Comprobar que responde

Desde el propio servidor:

```bash
curl http://localhost/
```

Desde fuera (reemplaza por la IP o dominio de tu servidor):

```bash
curl http://TU_IP_O_DOMINIO/
```

Deberías recibir algo como: `{"message":"Com Brasper API","version":"1.0.0"}`.

La documentación Swagger queda en: **http://TU_IP_O_DOMINIO/docs**

### 5. Ver logs

```bash
# Todos los servicios
docker compose logs -f

# Solo Nginx
docker compose logs -f nginx

# Solo la API
docker compose logs -f api
```

### 6. Parar los contenedores

```bash
docker compose down
```

Para borrar también el volumen de PostgreSQL:

```bash
docker compose down -v
```

## Comportamiento al arrancar

1. PostgreSQL (`db`) arranca y se espera a que esté listo (healthcheck).
2. La API arranca: ejecuta `alembic upgrade head` y luego uvicorn en el puerto 8000 (interno).
3. Nginx arranca y redirige el tráfico del puerto 80 (y 443) a la API.

## Configuración de Nginx

- **Archivo:** `nginx/nginx.conf`
- **Puertos:** 80 (HTTP) y 443 (HTTPS, para cuando añadas certificado).
- Para **SSL con Let's Encrypt**, descomenta el bloque `server { listen 443 ssl; ... }` en `nginx/nginx.conf`, monta los certificados en el contenedor y reinicia Nginx.

## Base de datos externa

Si quieres usar una base de datos que ya está en otro servidor (no el contenedor `db`):

1. En `.env` pon `POSTGRES_HOST` (y `POSTGRES_PORT`) con la IP/host de ese servidor.
2. En `docker-compose.yml` comenta o elimina el servicio `db` y el `depends_on: db` de la API.
3. Levanta solo: `docker compose up -d --build nginx api`
