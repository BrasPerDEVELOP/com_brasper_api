# Com Brasper API

API REST con **FastAPI** y **Arquitectura Hexagonal**. Autenticación con tokens opacos y gestión de usuarios, monedas, transacciones, bancos y cupones.

## Requisitos

- Python 3.9+
- PostgreSQL
- Poetry (recomendado) o pip

## Configuración

### Variables de entorno

Copia `.env.example` a `.env` (o crea `.env`) y configura:

```env
POSTGRES_DB=com_brasper
POSTGRES_USER=postgres
POSTGRES_PASSWORD=tu_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DEBUG=True
LOG_LEVEL=debug

TOKEN_EXPIRATION_MINUTES=1440
TOKEN_REFRESH_EXPIRATION_MINUTES=2880
SECRET_KEY=tu-clave-secreta-min-32-caracteres
```

**Importante:** No subas `.env` al repositorio (está en `.gitignore`). Genera una `SECRET_KEY` segura:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Instalación

```bash
# Con Poetry
poetry install
poetry shell

# O con pip
python -m venv venv
source venv/bin/activate   # Linux/macOS
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## Migraciones

**Importante:** Ejecuta las migraciones antes de arrancar la API. Si no, el POST de transacciones puede devolver 500.

```bash
# Aplicar todas las migraciones (obligatorio antes de uvicorn)
poetry run alembic upgrade head
# o con el script:
sh scripts/migrate.sh

# Ver versión actual
poetry run alembic current

# Crear nueva migración (tras cambiar modelos)
alembic revision --autogenerate -m "descripcion"

# Historial
alembic history

# Revertir última migración
alembic downgrade -1
```

## Ejecutar la aplicación

```bash
# 1. Aplicar migraciones (si no lo has hecho)
poetry run alembic upgrade head

# 2. Arrancar la API
uvicorn app.main:app --reload
```

- **API:** http://localhost:8000  
- **Docs (Swagger):** http://localhost:8000/docs  
- **ReDoc:** http://localhost:8000/redoc  

## Estructura del proyecto

```
app/
├── core/                    # Configuración, settings, contenedores DI
├── db/                       # Conexión DB y configuración Alembic
├── shared/                   # Bases (ORM, repositorios, interfaces)
├── middlewares/              # Middlewares (ej. autenticación)
├── modules/
│   ├── auth/                 # Login, tokens opacos
│   ├── users/                # Usuarios (CRUD, roles, etc.)
│   ├── coin/                 # Monedas, TaxRate, Commission
│   └── transactions/         # Transaction, Bank, BankAccount, Coupon
├── models_registry.py        # Registro de modelos SQLAlchemy
└── main.py                   # App FastAPI
```

Cada módulo sigue **hexagonal**: `domain/`, `application/` (schemas, use cases), `interfaces/`, `infrastructure/`, `adapters/` (dependencies, router).

## Módulos y rutas principales

| Módulo       | Prefijo / Ejemplos                    |
|-------------|---------------------------------------|
| Auth        | `/auth` (login, refresh, logout)      |
| Users       | `/user`                               |
| Coin        | `/coin` (currencies, tax-rate, commission) |
| Transactions| `/transactions` (transactions, banks, bank-accounts, coupons) |
| Mundial 2026 | `/world-cup` (campaña, partidos, aprobación y alertas) |

## Campaña Mundial 2026

La campaña arranca deshabilitada y en modo `REVIEW`. Antes de activarla, aplica la migración `050` y configura:

```env
SPORTMONKS_API_TOKEN=
SPORTMONKS_WORLD_CUP_LEAGUE_ID=
WORLD_CUP_SCHEDULER_ENABLED=true
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=true
```

Sin credenciales, el resto de la API y la home continúan funcionando; la sincronización manual devuelve un error controlado. El scheduler usa un bloqueo PostgreSQL para que solo una réplica procese cada ciclo.

## Seguridad

- Tokens opacos validados en base de datos (tabla `auth_login`).
- Contraseñas con hash (Argon2 / PBKDF2).
- Expiración y revocación de tokens.
- CORS y configuración vía `core/settings`.

## Licencia

Uso interno / según criterio del equipo.
