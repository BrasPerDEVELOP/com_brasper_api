"""Catálogo de etiquetas de transacción: rutas y reglas de negocio."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.transactions.adapters.dependencies.transaction_dependencies import (
    create_tag_uc,
    delete_tag_uc,
    get_tag_by_id_uc,
    list_tags_uc,
    update_tag_uc,
)
from app.modules.transactions.application.schemas import (
    TAG_COLORS,
    TagCreateCmd,
    TagReadDTO,
    TagUpdateCmd,
)
from app.modules.transactions.application.use_cases.tag_use_cases import (
    CreateTagUseCase,
    UpdateTagUseCase,
)
from app.modules.transactions.domain.models import Tag

NEW_TAG_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TAG_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _dto(tag_id: UUID = NEW_TAG_ID, label: str = "Cliente nuevo", **kw) -> TagReadDTO:
    base = dict(
        id=tag_id,
        label=label,
        color="amber",
        active=True,
        counts_as_new_client=True,
        position=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(kw)
    return TagReadDTO(**base)


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


# --------------------------------------------------------------- schema
class TestTagSchema:
    def test_color_fuera_de_la_paleta_cae_en_slate(self):
        """La UI solo sabe pintar la paleta cerrada; un color libre la rompería."""
        cmd = TagCreateCmd(label="Prueba", color="fucsia-neon")
        assert cmd.color == "slate"

    def test_color_de_la_paleta_se_respeta(self):
        for color in TAG_COLORS:
            assert TagCreateCmd(label="X", color=color).color == color

    def test_label_se_recorta(self):
        assert TagCreateCmd(label="  Campaña  ").label == "Campaña"

    def test_label_vacio_es_rechazado(self):
        with pytest.raises(ValueError):
            TagCreateCmd(label="   ")

    def test_update_sin_campos_no_inventa_valores(self):
        """`exclude_unset` es lo que permite editar solo el color, por ejemplo."""
        cmd = TagUpdateCmd(id=NEW_TAG_ID, color="blue")
        changed = cmd.model_dump(exclude_unset=True, exclude={"id"})
        assert changed == {"color": "blue"}


# --------------------------------------------------------------- casos de uso
class _FakeRepo:
    """Repo en memoria con la superficie que usan los casos de uso."""

    def __init__(self, tags=None):
        self.tags = list(tags or [])
        self.cleared_except = "no-llamado"

    async def list_ordered(self, only_active: bool = False):
        items = [t for t in self.tags if not getattr(t, "deleted", False)]
        if only_active:
            items = [t for t in items if t.active]
        return items

    async def get(self, tag_id):
        return next((t for t in self.tags if t.id == tag_id), None)

    async def add(self, obj):
        obj.id = obj.id or uuid4()
        self.tags.append(obj)
        return obj

    async def update(self, obj):
        return obj

    async def delete(self, tag_id):
        for t in self.tags:
            if t.id == tag_id:
                t.deleted = True

    async def clear_new_client_flag(self, except_id=None):
        self.cleared_except = except_id
        for t in self.tags:
            if t.id != except_id:
                t.counts_as_new_client = False

    async def commit(self):
        return None

    async def refresh(self, obj, **kw):
        return obj


def _tag(tag_id, label, counts=False, active=True) -> Tag:
    t = Tag(label=label, color="amber", active=active, counts_as_new_client=counts, position=0)
    t.id = tag_id
    t.deleted = False
    t.created_at = datetime.now(timezone.utc)
    t.updated_at = datetime.now(timezone.utc)
    return t


class TestReglasDeNegocio:
    @pytest.mark.asyncio
    async def test_no_se_repite_el_nombre(self):
        repo = _FakeRepo([_tag(OTHER_TAG_ID, "Cliente nuevo")])
        with pytest.raises(ValueError, match="Ya existe"):
            await CreateTagUseCase(repo).execute(TagCreateCmd(label="cliente NUEVO"))

    @pytest.mark.asyncio
    async def test_crear_con_flag_se_lo_quita_a_las_demas(self):
        """Solo una etiqueta puede alimentar el indicador de clientes nuevos."""
        previa = _tag(OTHER_TAG_ID, "Recurrente", counts=True)
        repo = _FakeRepo([previa])

        creada = await CreateTagUseCase(repo).execute(
            TagCreateCmd(label="Cliente nuevo", counts_as_new_client=True)
        )

        assert creada.counts_as_new_client is True
        assert previa.counts_as_new_client is False
        assert repo.cleared_except == creada.id

    @pytest.mark.asyncio
    async def test_crear_sin_flag_no_toca_a_las_demas(self):
        previa = _tag(OTHER_TAG_ID, "Cliente nuevo", counts=True)
        repo = _FakeRepo([previa])

        await CreateTagUseCase(repo).execute(TagCreateCmd(label="Campaña"))

        assert previa.counts_as_new_client is True
        assert repo.cleared_except == "no-llamado"

    @pytest.mark.asyncio
    async def test_mover_el_flag_al_editar(self):
        actual = _tag(NEW_TAG_ID, "Cliente nuevo", counts=True)
        otra = _tag(OTHER_TAG_ID, "Recurrente")
        repo = _FakeRepo([actual, otra])

        await UpdateTagUseCase(repo).execute(
            TagUpdateCmd(id=OTHER_TAG_ID, counts_as_new_client=True)
        )

        assert otra.counts_as_new_client is True
        assert actual.counts_as_new_client is False

    @pytest.mark.asyncio
    async def test_desactivar_no_borra(self):
        """Inactiva deja de ofrecerse, pero sigue en las transacciones viejas."""
        etiqueta = _tag(NEW_TAG_ID, "Campaña")
        repo = _FakeRepo([etiqueta])

        await UpdateTagUseCase(repo).execute(TagUpdateCmd(id=NEW_TAG_ID, active=False))

        assert etiqueta.active is False
        assert etiqueta.deleted is False
        assert await repo.list_ordered(only_active=True) == []
        assert await repo.list_ordered() == [etiqueta]

    @pytest.mark.asyncio
    async def test_renombrar_a_un_nombre_ya_usado_falla(self):
        repo = _FakeRepo([_tag(NEW_TAG_ID, "Campaña"), _tag(OTHER_TAG_ID, "VIP")])
        with pytest.raises(ValueError, match="Ya existe"):
            await UpdateTagUseCase(repo).execute(
                TagUpdateCmd(id=OTHER_TAG_ID, label="Campaña")
            )

    @pytest.mark.asyncio
    async def test_renombrarse_a_si_misma_es_valido(self):
        repo = _FakeRepo([_tag(NEW_TAG_ID, "Campaña")])
        result = await UpdateTagUseCase(repo).execute(
            TagUpdateCmd(id=NEW_TAG_ID, label="Campaña")
        )
        assert result.label == "Campaña"

    @pytest.mark.asyncio
    async def test_editar_una_etiqueta_inexistente_devuelve_none(self):
        repo = _FakeRepo([])
        assert await UpdateTagUseCase(repo).execute(TagUpdateCmd(id=NEW_TAG_ID)) is None


# --------------------------------------------------------------- rutas
class TestRutas:
    def test_listado(self):
        uc = AsyncMock()
        uc.execute = AsyncMock(return_value=[_dto()])
        app.dependency_overrides[list_tags_uc] = lambda: uc

        r = TestClient(app).get("/transactions/tags/")

        assert r.status_code == 200
        body = r.json()
        assert body[0]["label"] == "Cliente nuevo"
        assert body[0]["counts_as_new_client"] is True

    def test_listado_only_active_llega_al_caso_de_uso(self):
        uc = AsyncMock()
        uc.execute = AsyncMock(return_value=[])
        app.dependency_overrides[list_tags_uc] = lambda: uc

        TestClient(app).get("/transactions/tags/?only_active=true")

        uc.execute.assert_awaited_once_with(only_active=True)

    def test_detalle_inexistente_da_404(self):
        uc = AsyncMock()
        uc.execute = AsyncMock(return_value=None)
        app.dependency_overrides[get_tag_by_id_uc] = lambda: uc

        r = TestClient(app).get(f"/transactions/tags/{uuid4()}")

        assert r.status_code == 404

    def test_crear_devuelve_201(self):
        uc = AsyncMock()
        uc.execute = AsyncMock(return_value=_dto())
        app.dependency_overrides[create_tag_uc] = lambda: uc

        r = TestClient(app).post(
            "/transactions/tags/",
            json={"label": "Cliente nuevo", "color": "amber", "counts_as_new_client": True},
        )

        assert r.status_code == 201

    def test_nombre_duplicado_da_400_y_no_500(self):
        uc = AsyncMock()
        uc.execute = AsyncMock(side_effect=ValueError("Ya existe una etiqueta llamada «X»"))
        app.dependency_overrides[create_tag_uc] = lambda: uc

        r = TestClient(app).post("/transactions/tags/", json={"label": "X"})

        assert r.status_code == 400
        assert "Ya existe" in r.json()["detail"]

    def test_editar_duplicado_da_400(self):
        uc = AsyncMock()
        uc.execute = AsyncMock(side_effect=ValueError("Ya existe una etiqueta llamada «X»"))
        app.dependency_overrides[update_tag_uc] = lambda: uc

        r = TestClient(app).put(
            "/transactions/tags/", json={"id": str(NEW_TAG_ID), "label": "X"}
        )

        assert r.status_code == 400

    def test_editar_inexistente_da_404(self):
        uc = AsyncMock()
        uc.execute = AsyncMock(return_value=None)
        app.dependency_overrides[update_tag_uc] = lambda: uc

        r = TestClient(app).put(
            "/transactions/tags/", json={"id": str(NEW_TAG_ID), "label": "X"}
        )

        assert r.status_code == 404

    def test_borrar_devuelve_204(self):
        uc = AsyncMock()
        uc.execute = AsyncMock(return_value=None)
        app.dependency_overrides[delete_tag_uc] = lambda: uc

        r = TestClient(app).delete(f"/transactions/tags/{NEW_TAG_ID}")

        assert r.status_code == 204
