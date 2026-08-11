# tests/test_blog.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import get_db
from app.modules.blog.application.schemas import BlogReadDTO, BlogListPage
from app.modules.blog.adapters.dependencies.blog_dependencies import (
    get_blog_by_id_uc,
    get_blog_by_slug_uc,
    list_blogs_uc,
    create_blog_uc,
    update_blog_uc,
    delete_blog_uc,
)


@pytest.fixture
def mock_get_blog_by_id_uc():
    use_case = AsyncMock()
    # Un resultado no configurado debe representar "no encontrado", no otro
    # AsyncMock cuyo model_dump produciría una coroutine sin esperar.
    use_case.execute.return_value = None
    return use_case


@pytest.fixture
def mock_get_blog_by_slug_uc():
    return AsyncMock()


@pytest.fixture
def mock_list_blogs_uc():
    return AsyncMock()


@pytest.fixture
def mock_create_blog_uc():
    return AsyncMock()


@pytest.fixture
def mock_update_blog_uc():
    return AsyncMock()


@pytest.fixture
def mock_delete_blog_uc():
    return AsyncMock()


@pytest.fixture
def blog_client(
    mock_get_blog_by_id_uc,
    mock_get_blog_by_slug_uc,
    mock_list_blogs_uc,
    mock_create_blog_uc,
    mock_update_blog_uc,
    mock_delete_blog_uc,
):
    app.dependency_overrides[get_blog_by_id_uc] = lambda: mock_get_blog_by_id_uc
    app.dependency_overrides[get_blog_by_slug_uc] = lambda: mock_get_blog_by_slug_uc
    app.dependency_overrides[list_blogs_uc] = lambda: mock_list_blogs_uc
    app.dependency_overrides[create_blog_uc] = lambda: mock_create_blog_uc
    app.dependency_overrides[update_blog_uc] = lambda: mock_update_blog_uc
    app.dependency_overrides[delete_blog_uc] = lambda: mock_delete_blog_uc
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db

    yield TestClient(app)

    app.dependency_overrides.pop(get_blog_by_id_uc, None)
    app.dependency_overrides.pop(get_blog_by_slug_uc, None)
    app.dependency_overrides.pop(list_blogs_uc, None)
    app.dependency_overrides.pop(create_blog_uc, None)
    app.dependency_overrides.pop(update_blog_uc, None)
    app.dependency_overrides.pop(delete_blog_uc, None)
    app.dependency_overrides.pop(get_db, None)


def test_create_blog(blog_client, mock_create_blog_uc):
    blog_id = uuid4()
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)

    mock_read_dto = BlogReadDTO(
        id=blog_id,
        title="Test Blog Title",
        slug="test-blog-title",
        excerpt="An excerpt",
        content="Some content",
        category="Tech",
        public_id="pub-1",
        read_time=5,
        date=created_at,
        language="es",
        enable=True,
        created_at=created_at,
        created_by=None,
        updated_at=updated_at,
    )
    mock_create_blog_uc.execute.return_value = mock_read_dto

    payload = {
        "title": "Test Blog Title",
        "slug": "test-blog-title",
        "excerpt": "An excerpt",
        "content": "Some content",
        "category": "Tech",
        "public_id": "pub-1",
        "read_time": 5,
        "date": created_at.isoformat(),
        "language": "es",
        "enable": True,
    }

    response = blog_client.post("/blog/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == str(blog_id)
    assert data["title"] == "Test Blog Title"
    assert data["slug"] == "test-blog-title"
    assert data["language"] == "es"


def test_get_blog_by_id(blog_client, mock_get_blog_by_id_uc):
    blog_id = uuid4()
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)

    mock_read_dto = BlogReadDTO(
        id=blog_id,
        title="Test Blog Title",
        slug="test-blog-title",
        excerpt="An excerpt",
        content="Some content",
        category="Tech",
        public_id="pub-1",
        read_time=5,
        date=created_at,
        language="es",
        enable=True,
        created_at=created_at,
        created_by=None,
        updated_at=updated_at,
    )
    mock_get_blog_by_id_uc.execute.return_value = mock_read_dto

    response = blog_client.get(f"/blog/{blog_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(blog_id)
    assert data["slug"] == "test-blog-title"


def test_get_blog_by_id_not_found(blog_client, mock_get_blog_by_id_uc):
    mock_get_blog_by_id_uc.execute.return_value = None
    response = blog_client.get(f"/blog/{uuid4()}")
    assert response.status_code == 404


def test_get_blog_by_slug(blog_client, mock_get_blog_by_slug_uc):
    blog_id = uuid4()
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)

    mock_read_dto = BlogReadDTO(
        id=blog_id,
        title="Test Blog Title",
        slug="test-blog-title",
        excerpt="An excerpt",
        content="Some content",
        category="Tech",
        public_id="pub-1",
        read_time=5,
        date=created_at,
        language="es",
        enable=True,
        created_at=created_at,
        created_by=None,
        updated_at=updated_at,
    )
    mock_get_blog_by_slug_uc.execute.return_value = mock_read_dto

    response = blog_client.get("/blog/slug/test-blog-title")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(blog_id)
    assert data["slug"] == "test-blog-title"


def test_list_blogs(blog_client, mock_list_blogs_uc):
    blog_id = uuid4()
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)

    mock_read_dto = BlogReadDTO(
        id=blog_id,
        title="Test Blog Title",
        slug="test-blog-title",
        excerpt="An excerpt",
        content="Some content",
        category="Tech",
        public_id="pub-1",
        read_time=5,
        date=created_at,
        language="es",
        enable=True,
        created_at=created_at,
        created_by=None,
        updated_at=updated_at,
    )

    mock_list_page = BlogListPage(
        items=[mock_read_dto],
        total=1,
        skip=0,
        limit=20,
        has_next=False,
        has_previous=False,
    )
    mock_list_blogs_uc.execute.return_value = mock_list_page

    response = blog_client.get("/blog/?skip=0&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["slug"] == "test-blog-title"
    assert "content" not in data["items"][0]
    mock_list_blogs_uc.execute.assert_called_once_with(
        limit=20,
        skip=0,
        search=None,
        category=None,
        enable=None,
    )


def test_list_blogs_with_filters(blog_client, mock_list_blogs_uc):
    mock_list_page = BlogListPage(
        items=[],
        total=0,
        skip=10,
        limit=10,
        has_next=False,
        has_previous=True,
    )
    mock_list_blogs_uc.execute.return_value = mock_list_page

    response = blog_client.get(
        "/blog/?skip=10&limit=10&search=remesas&category=Finanzas&enable=true"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    mock_list_blogs_uc.execute.assert_called_once_with(
        limit=10,
        skip=10,
        search="remesas",
        category="Finanzas",
        enable=True,
    )


def test_update_blog(blog_client, mock_update_blog_uc):
    blog_id = uuid4()
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)

    mock_read_dto = BlogReadDTO(
        id=blog_id,
        title="Updated Blog Title",
        slug="test-blog-title",
        excerpt="An excerpt",
        content="Some content",
        category="Tech",
        public_id="pub-1",
        read_time=5,
        date=created_at,
        language="es",
        enable=True,
        created_at=created_at,
        created_by=None,
        updated_at=updated_at,
    )
    mock_update_blog_uc.execute.return_value = mock_read_dto

    payload = {
        "id": str(blog_id),
        "title": "Updated Blog Title",
    }

    response = blog_client.put("/blog/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Blog Title"


def test_delete_blog(blog_client, mock_delete_blog_uc):
    mock_delete_blog_uc.execute.return_value = True
    response = blog_client.delete(f"/blog/{uuid4()}")
    assert response.status_code == 204
