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

```bash
# Aplicar todas las migraciones
alembic upgrade head

# Crear nueva migración (tras cambiar modelos)
alembic revision --autogenerate -m "descripcion"

# Historial
alembic history

# Revertir última migración
alembic downgrade -1
```

## Ejecutar la aplicación

```bash
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

## Seguridad

- Tokens opacos validados en base de datos (tabla `auth_login`).
- Contraseñas con hash (Argon2 / PBKDF2).
- Expiración y revocación de tokens.
- CORS y configuración vía `core/settings`.

## Licencia

Uso interno / según criterio del equipo.
