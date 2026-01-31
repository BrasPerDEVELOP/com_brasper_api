import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, create_engine, pool, inspect
from alembic import context

# Agrega la carpeta raíz del proyecto al path para permitir imports
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
)

# Importa configuración, metadata y modelos necesarios
from app.core.settings import get_settings
from app.shared.model_base import ORMBase
from app.modules.auth.domain.models import AuthModel
from app.modules.users.domain.models import User
from app.modules.coin.domain.models import TaxRate, Commission
from app.modules.transactions.domain.models import Transaction

# Obtiene la configuración de la base de datos
settings = get_settings()

# Configuración base de Alembic
env_config = context.config
fileConfig(env_config.config_file_name)

# Convertir URL de asyncpg a psycopg2 para Alembic (necesita driver síncrono)
db_url = settings.database_url
# Reemplazar postgresql+asyncpg:// por postgresql:// o postgresql+psycopg2://
db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
env_config.set_main_option("sqlalchemy.url", db_url)

# Metadata objetivo para las migraciones
target_metadata = ORMBase.metadata

# Excluye la tabla de versión de Alembic y muestra advertencias si hay tablas fuera de los modelos
def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and name == "alembic_version":
        return False
    if type_ == "table":
        if reflected and compare_to is None:
            return False
        if not reflected and compare_to is not None:
            return True
    return True

# Configuración para ejecutar migraciones en modo offline (sin conexión a la base de datos)
def run_migrations_offline():
    url = env_config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

# Configuración para ejecutar migraciones con conexión activa a la base de datos
def run_migrations_online():
    # Usar URL desde .env (settings) para asegurar conexión correcta
    connectable = create_engine(
        db_url,
        poolclass=pool.NullPool,
        isolation_level="AUTOCOMMIT",
    )

    with connectable.connect() as connection:
        # Crea los esquemas necesarios si no existen
        for sch in ("user",):
            quoted = sch if sch != "user" else '"user"'
            connection.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {quoted}")

        # Crea la tabla de control de versiones si no existe
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS public.alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            )
            """
        )
        connection.commit()

        # Establece el search_path para los esquemas
        connection.exec_driver_sql(
            'SET search_path TO public, "user"'
        )

        # Configura Alembic con opciones para esquemas múltiples
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="public",
            compare_type=True,
            include_object=include_object,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()
        connection.commit()

# Ejecuta la migración en modo offline u online según corresponda
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
