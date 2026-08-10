"""Reutilizar el correo/documento de un usuario eliminado.

El borrado de usuarios es lógico. Con restricciones únicas incondicionales, la
fila borrada seguía ocupando el índice y volver a registrar a la misma persona
fallaba con 409 «Conflicto de datos». La migración 063 las convierte en índices
únicos parciales sobre las filas vivas.
"""
import datetime
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import ColumnDefault, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.users.domain.models import User, UserIdentification
from app.modules.users.infrastructure.repository import SQLAlchemyUserRepository
from app.shared.model_base import ORMBase


def _now(_ctx=None):
    return datetime.datetime.now(datetime.timezone.utc)


@pytest_asyncio.fixture
async def session():
    """SQLite en memoria con los índices parciales que crea la migración 063."""
    tables = [User.__table__, UserIdentification.__table__]
    # El metadata es global al proceso: se guarda el estado original para
    # devolverlo al terminar y no contaminar al resto de la suite.
    original = {
        table: (table.schema, set(table.indexes)) for table in tables
    }
    for table in tables:
        table.schema = None
        for column in ("created_at", "updated_at"):
            col = table.c[column]
            col.server_default = col.server_onupdate = None
            col.default = ColumnDefault(_now)
            col.onupdate = ColumnDefault(_now, for_update=True)
        # Los índices del modelo llevan `postgresql_where`, que SQLite no
        # entiende: se crean abajo a mano con el mismo `WHERE` de la migración.
        table.indexes.clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync: ORMBase.metadata.create_all(sync, tables=tables))
        for ddl in (
            "CREATE UNIQUE INDEX uq_user_email_alive ON user (email) "
            "WHERE deleted = 0 AND email IS NOT NULL",
            "CREATE UNIQUE INDEX uq_user_document_number_alive ON user (document_number) "
            "WHERE deleted = 0 AND document_number IS NOT NULL",
            "CREATE UNIQUE INDEX uq_user_identifications_type_number_alive "
            "ON user_identifications (document_type, document_number) WHERE deleted = 0",
        ):
            await conn.exec_driver_sql(ddl)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as db:
            yield db
    finally:
        await engine.dispose()
        for table, (schema, indexes) in original.items():
            table.schema = schema
            table.indexes.clear()
            table.indexes.update(indexes)


def _user(email: str, document: str) -> User:
    u = User(names="Alberto", email=email, document_number=document, role="client")
    u.id = uuid.uuid4()
    u.deleted = False
    return u


@pytest.mark.asyncio
class TestUniquesConBorradoLogico:
    async def test_dos_usuarios_vivos_no_pueden_repetir_email(self, session):
        session.add(_user("a@b.com", "111"))
        await session.flush()
        session.add(_user("a@b.com", "222"))
        with pytest.raises(IntegrityError):
            await session.flush()

    async def test_se_puede_reusar_el_email_de_un_usuario_borrado(self, session):
        viejo = _user("a@b.com", "111")
        session.add(viejo)
        await session.flush()

        viejo.deleted = True
        await session.flush()

        session.add(_user("a@b.com", "111"))
        await session.flush()  # antes reventaba con IntegrityError

        vivos = (
            await session.execute(select(User).where(User.deleted.is_(False)))
        ).scalars().all()
        assert len(vivos) == 1

    async def test_el_documento_del_borrado_tambien_se_libera(self, session):
        viejo = _user("uno@b.com", "26716288")
        session.add(viejo)
        await session.flush()
        viejo.deleted = True
        await session.flush()

        session.add(_user("dos@b.com", "26716288"))
        await session.flush()

    async def test_borrar_el_usuario_marca_sus_identificaciones(self, session):
        user = _user("a@b.com", "111")
        session.add(user)
        await session.flush()
        ident = UserIdentification(
            user_id=user.id, document_type="dni", document_number="26716288", is_primary=True
        )
        ident.id = uuid.uuid4()
        ident.deleted = False
        session.add(ident)
        await session.flush()

        repo = SQLAlchemyUserRepository(session)
        await repo.soft_delete_identifications(user.id)
        await session.flush()

        assert (await session.get(UserIdentification, ident.id)).deleted is True

    async def test_tras_borrar_se_puede_registrar_el_mismo_documento(self, session):
        user = _user("a@b.com", "111")
        session.add(user)
        await session.flush()
        ident = UserIdentification(
            user_id=user.id, document_type="dni", document_number="26716288", is_primary=True
        )
        ident.id = uuid.uuid4()
        ident.deleted = False
        session.add(ident)
        await session.flush()

        repo = SQLAlchemyUserRepository(session)
        await repo.soft_delete_identifications(user.id)
        user.deleted = True
        await session.flush()

        # La misma persona, dada de alta otra vez con su mismo DNI.
        nuevo = _user("a@b.com", "111")
        session.add(nuevo)
        await session.flush()
        otro = UserIdentification(
            user_id=nuevo.id, document_type="dni", document_number="26716288", is_primary=True
        )
        otro.id = uuid.uuid4()
        otro.deleted = False
        session.add(otro)
        await session.flush()

    async def test_dos_identificaciones_vivas_no_pueden_repetirse(self, session):
        user = _user("a@b.com", "111")
        session.add(user)
        await session.flush()
        for _ in range(2):
            ident = UserIdentification(
                user_id=user.id, document_type="dni", document_number="26716288", is_primary=False
            )
            ident.id = uuid.uuid4()
            ident.deleted = False
            session.add(ident)
        with pytest.raises(IntegrityError):
            await session.flush()
