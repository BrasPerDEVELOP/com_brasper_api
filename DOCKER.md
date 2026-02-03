# Ejecutar en el servidor con Docker

## Requisitos

- Docker y Docker Compose instalados en el servidor.

## Pasos

### 1. Crear `.env` en el servidor

Copia `.env.example` a `.env` y ajusta los valores (sobre todo `POSTGRES_PASSWORD` y `SECRET_KEY`):

```bash
cp .env.example .env
# Editar .env con tus valores
```

**Importante:** Con `docker-compose`, la API se conecta a PostgreSQL usando el servicio `db`. En `.env` debe estar:

- `POSTGRES_HOST=db`
- `POSTGRES_PORT=5432`

El resto de variables (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `SECRET_KEY`, etc.) deben coincidir con lo que use el contenedor de la base de datos.

### 2. Levantar los servicios

```bash
docker compose up -d --build
```

- `--build`: construye la imagen de la API.
- `-d`: ejecuta en segundo plano.

### 3. Comprobar que la API responde

```bash
curl http://localhost:8000/
```

La API queda en el puerto **8000** y PostgreSQL en **5432** (solo necesario si quieres conectar desde fuera al mismo host).

### 4. Ver logs

```bash
docker compose logs -f api
```

### 5. Parar los contenedores

```bash
docker compose down
```

Para borrar también el volumen de la base de datos:

```bash
docker compose down -v
```

## Comportamiento al arrancar

1. Se inicia PostgreSQL y se espera a que esté listo (healthcheck).
2. Se inicia la API: se ejecutan las migraciones (`alembic upgrade head`) y luego se lanza uvicorn en el puerto 8000.

Si ya tienes una base de datos externa, puedes usar solo el servicio `api` en `docker-compose` y poner en `.env` `POSTGRES_HOST` (y puerto) apuntando a ese servidor, eliminando o comentando el servicio `db` en `docker-compose.yml`.
