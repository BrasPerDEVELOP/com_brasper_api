import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.marketing import mail, routes
from app.modules.marketing.schemas import CampaignInput, PreviewInput
from app.modules.marketing.template_renderer import (
    ASSET_DIR, ASSET_NAMES, ASSET_PREFIX, DEFAULT_BODY, DEFAULT_SUBJECT, TEMPLATE_KEY,
    asset_cid, render_email,
)


def test_template_has_no_local_assets_and_escapes_campaign_text():
    markup = render_email('Subject <script>', '<img src=x onerror=alert(1)>\n{{ unsubscribe_url }}',
                          'https://api.example.com/unsubscribe?a=1&b=2', TEMPLATE_KEY)
    assert '<html lang="pt-BR"' in markup
    assert '<img src=x' not in markup
    assert '&lt;img src=x onerror=alert(1)&gt;' in markup
    assert '{{ unsubscribe_url }}' in markup  # campaign text remains literal
    assert 'href="https://api.example.com/unsubscribe?a=1&amp;b=2"' in markup
    sources = re.findall(r'src="([^"]+)"', markup)
    assert sources and all(src.startswith('cid:') for src in sources)
    assert len(set(sources)) == len(ASSET_NAMES)


def test_preview_and_email_share_the_same_layout():
    preview = render_email(DEFAULT_SUBJECT, DEFAULT_BODY, '#preview', TEMPLATE_KEY, 'https://api.example.com')
    email = render_email(DEFAULT_SUBJECT, DEFAULT_BODY, '#preview', TEMPLATE_KEY)
    for name in ASSET_NAMES:
        assert (ASSET_DIR / name).is_file()
        preview = preview.replace('https://api.example.com' + ASSET_PREFIX + '/' + name, 'cid:' + asset_cid(name))
    assert preview == email


def test_template_id_is_validated_not_used_as_a_file_path():
    with pytest.raises(ValidationError):
        PreviewInput(template_key='../../.env')
    with pytest.raises(ValueError):
        render_email('Subject', 'body', '#', '../../.env')


async def test_asset_endpoint_only_serves_named_images():
    with pytest.raises(HTTPException) as exc:
        await routes.template_asset('../../.env')
    assert exc.value.status_code == 404
    result = await routes.template_asset('logo_brasper.png')
    assert result.path == ASSET_DIR / 'logo_brasper.png'
    assert 'immutable' in result.headers['cache-control']


def test_template_images_are_public_but_campaigns_are_private():
    from app.middlewares.auth import TokenAuthMiddleware
    from starlette.requests import Request
    middleware = TokenAuthMiddleware(None)
    def request(path):
        return Request({'type': 'http', 'method': 'GET', 'path': path, 'headers': []})
    for name in ASSET_NAMES:
        assert middleware._is_public_path(request(ASSET_PREFIX + '/' + name))
    assert not middleware._is_public_path(request(ASSET_PREFIX + '/secret.png'))
    assert not middleware._is_public_path(request('/marketing/campaigns'))


def test_branded_message_embeds_each_cid_once_and_keeps_text_alternative(monkeypatch):
    settings = SimpleNamespace(SMTP_HOST='smtp.gmail.com', SMTP_PORT=587, SMTP_USERNAME='sender@example.com',
        SMTP_PASSWORD='secret', SMTP_FROM_EMAIL='sender@example.com', SMTP_USE_TLS=True,
        PUBLIC_URL='https://api.example.com', SECRET_KEY='test-key-long-enough-12345678901234567890')
    monkeypatch.setattr(mail, 'get_settings', lambda: settings)
    message = mail.build_message('recipient@example.com', DEFAULT_SUBJECT, DEFAULT_BODY, True, TEMPLATE_KEY)
    assert message['Subject'].startswith('[PRUEBA]')
    assert message.get_body(preferencelist=('plain',)) is not None
    html = message.get_body(preferencelist=('html',)).get_content()
    images = [part for part in message.walk() if part.get_content_maintype() == 'image']
    assert len(images) == len(ASSET_NAMES)
    assert len({image['Content-ID'] for image in images}) == len(ASSET_NAMES)
    for image in images:
        assert image.get_content_disposition() == 'inline'
        assert 'cid:' + image['Content-ID'].strip('<>') in html
    assert 'Cancelar inscrição' in message.get_body(preferencelist=('plain',)).get_content()
    assert 'href="{{ unsubscribe_url }}"' not in html
    assert 'src="assets/' not in html
    assert len(message.as_bytes()) < 2_000_000


@pytest.mark.parametrize("key,language,banner", [
    ("brasper_peru_pt_v1", "pt-BR", "banner_superior_portugues.jpg"),
    ("brasper_brasil_es_v1", "es-PE", "banner_superior_espanol.jpg"),
])
def test_each_audience_uses_its_own_images_and_language(key, language, banner, monkeypatch):
    from app.modules.marketing.template_renderer import TEMPLATES, template_assets
    settings = SimpleNamespace(SMTP_HOST='smtp.gmail.com', SMTP_PORT=587, SMTP_USERNAME='sender@example.com',
        SMTP_PASSWORD='secret', SMTP_FROM_EMAIL='sender@example.com', SMTP_USE_TLS=True,
        PUBLIC_URL='https://api.example.com', SECRET_KEY='test-key-long-enough-12345678901234567890')
    monkeypatch.setattr(mail, 'get_settings', lambda: settings)
    item = TEMPLATES[key]
    message = mail.build_message('recipient@example.com', item['default_subject'], item['default_body'], template_key=key)
    markup = message.get_body(preferencelist=('html',)).get_content()
    assert f'lang="{language}"' in markup
    assert 'cid:' + asset_cid(banner) in markup
    images = [part for part in message.walk() if part.get_content_maintype() == 'image']
    assert {part.get_filename() for part in images} == set(template_assets(key))
    for part in images:
        assert part.get_payload(decode=True) == (ASSET_DIR / part.get_filename()).read_bytes()
    if language == 'es-PE':
        assert 'Haz tu cotización' in message.get_body(preferencelist=('plain',)).get_content()
        assert 'Cancelar inscrição' not in markup
    PreviewInput(template_key=key)
