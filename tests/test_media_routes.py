"""Tests del endpoint GET /media/{path}."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def media_client():
    with patch("app.main.file_service") as mock_fs, patch("app.main.settings") as mock_settings:
        mock_settings.R2_PUBLIC_URL = ""
        mock_fs.read_file = AsyncMock(return_value=None)
        yield TestClient(app, follow_redirects=False), mock_fs


def test_media_blocks_path_traversal(media_client):
    client, _ = media_client

    response = client.get("/media/../etc/passwd")

    assert response.status_code == 404


def test_media_serves_file_from_r2(media_client):
    client, mock_fs = media_client
    mock_fs.read_file = AsyncMock(return_value=(b"image-bytes", "image/webp"))

    response = client.get("/media/home_banner/banner_es_abc123.webp")

    assert response.status_code == 200
    assert response.content == b"image-bytes"
    assert response.headers["content-type"] == "image/webp"
    mock_fs.read_file.assert_awaited_with("home_banner/banner_es_abc123.webp")


def test_media_legacy_profile_tries_profile_images_folder(media_client):
    client, mock_fs = media_client

    async def read_side_effect(key):
        if key == "profile_images/profile_abc123.jpg":
            return b"profile", "image/jpeg"
        return None

    mock_fs.read_file = AsyncMock(side_effect=read_side_effect)

    response = client.get("/media/profile_abc123.jpg")

    assert response.status_code == 200
    assert response.content == b"profile"
    assert mock_fs.read_file.await_args_list[0].args[0] == "profile_images/profile_abc123.jpg"


def test_media_legacy_profile_returns_placeholder_when_missing(media_client):
    client, mock_fs = media_client
    mock_fs.read_file = AsyncMock(return_value=None)

    response = client.get("/media/profile_missing123.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert b"<svg" in response.content


def test_media_returns_404_when_file_not_found(media_client):
    client, mock_fs = media_client
    mock_fs.read_file = AsyncMock(return_value=None)

    response = client.get("/media/home_popup/not_found.webp")

    assert response.status_code == 404


def test_media_redirects_when_r2_public_url_is_set():
    with patch("app.main.settings") as mock_settings:
        mock_settings.R2_PUBLIC_URL = "https://media.example.workers.dev/web"
        mock_settings.media_public_url.return_value = (
            "https://media.example.workers.dev/web/home_banner/x.webp"
        )
        client = TestClient(app, follow_redirects=False)

        response = client.get("/media/home_banner/x.webp")

    assert response.status_code == 302
    assert response.headers["location"] == "https://media.example.workers.dev/web/home_banner/x.webp"
