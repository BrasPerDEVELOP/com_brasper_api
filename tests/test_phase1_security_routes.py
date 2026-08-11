import uuid
from fastapi import FastAPI, File, Form, Request, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from app.core.routing import LegacyAliasRouter
from app.core.settings import get_settings
from app.middlewares.auth import TokenAuthMiddleware
from app.middlewares.security import SecurityHeadersMiddleware, resolve_client_ip, check_rate_limit


# -----------------------------------------------------------------------------
# App determinista aislada sin BD ni R2
# -----------------------------------------------------------------------------
dummy_test_app = FastAPI()

# Mismo orden de middleware que en app/main.py
dummy_test_app.add_middleware(TokenAuthMiddleware)
dummy_test_app.add_middleware(SecurityHeadersMiddleware)

dummy_test_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

router = LegacyAliasRouter()


@router.get("/health")
async def health_dummy():
    return {"status": "ok"}


@router.get("/blog")
async def blog_list():
    return {"items": []}


@router.get("/blog/slug/{slug}")
async def blog_detail(slug: str):
    return {"slug": slug}


@router.post("/auth/login")
async def dummy_login():
    return {"token": "dummy"}


@router.post("/user")
async def dummy_user():
    return {"user": "created"}


@router.post("/brasper/contact-form")
async def dummy_contact():
    return {"contact": "received"}


@router.post("/contract/json")
async def contract_json(request: Request):
    return await request.json()


@router.post("/contract/multipart")
async def contract_multipart(
    label: str = Form(...),
    attachment: UploadFile = File(...),
):
    return {"label": label, "filename": attachment.filename, "body": (await attachment.read()).decode()}


@router.delete("/contract/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def contract_delete(item_id: str):
    return None


@router.get("/private/resource")
async def dummy_private():
    return {"secret": "data"}


prefixed_router = LegacyAliasRouter(prefix="/catalog")


@prefixed_router.get("")
async def catalog_list():
    return {"items": []}


dummy_test_app.include_router(router)
dummy_test_app.include_router(prefixed_router)
client = TestClient(dummy_test_app)


# -----------------------------------------------------------------------------
# Pruebas unitarias deterministas
# -----------------------------------------------------------------------------

def _make_req(method: str, path: str) -> Request:
    return Request({"type": "http", "method": method, "path": path, "headers": []})


def test_unit_allowlist_matcher():
    """Pruebas del matcher _is_public_path sobre métodos y rutas."""
    middleware = TokenAuthMiddleware(dummy_test_app)

    # 1. Rutas públicas exactas (método + path)
    assert middleware._is_public_path(_make_req("GET", "/health"))
    assert middleware._is_public_path(_make_req("GET", "/blog"))
    assert middleware._is_public_path(_make_req("POST", "/auth/login"))
    assert middleware._is_public_path(_make_req("POST", "/user"))
    assert middleware._is_public_path(_make_req("GET", "/transactions/coupons/automatic"))

    # 2. Rutas dinámicas
    assert middleware._is_public_path(_make_req("GET", "/blog/slug/mi-post"))
    assert middleware._is_public_path(_make_req("GET", "/media/profile_images/avatar.png"))
    assert not middleware._is_public_path(
        _make_req("GET", "/media/transaction_vouchers/send_secret.pdf")
    )
    assert middleware._is_public_path(_make_req("GET", "/blog/slug/mi-post/"))

    # 3. Alias legacy con barra final
    assert middleware._is_public_path(_make_req("GET", "/health/"))
    assert middleware._is_public_path(_make_req("POST", "/auth/login/"))

    # 4. Negativos: método diferente o prefijo abierto
    assert not middleware._is_public_path(_make_req("POST", "/blog"))
    assert not middleware._is_public_path(_make_req("POST", "/coin/tax-rate"))
    assert not middleware._is_public_path(_make_req("GET", "/auth/me"))
    assert not middleware._is_public_path(_make_req("GET", "/transactions/coupons"))
    assert not middleware._is_public_path(_make_req("POST", "/transactions/coupons/automatic"))
    assert not middleware._is_public_path(_make_req("GET", "/brasper/contact-form"))
    assert not middleware._is_public_path(_make_req("GET", "/integraciones/oauth/google/callback"))
    assert not middleware._is_public_path(_make_req("PUT", "/home-banner/home-image"))

    # 5. Intentos de evasión: dobles barras, dot-segments, caracteres codificados
    assert not middleware._is_public_path(_make_req("GET", "//health"))
    assert not middleware._is_public_path(_make_req("GET", "/health/../private"))
    assert not middleware._is_public_path(_make_req("GET", "/health%2f"))


def test_unit_canonical_openapi_and_legacy_alias():
    """Prueba que OpenAPI solo exponga rutas canónicas y los alias funcionen sin 307/308."""
    schema = dummy_test_app.openapi()
    paths = schema["paths"]

    # OpenAPI solo contiene rutas canónicas
    for p in paths.keys():
        if p != "/":
            assert not p.endswith("/"), f"OpenAPI schema contains non-canonical trailing slash: {p}"

    # Legacy alias ejecuta el handler directamente sin 307/308
    res_canonical = client.get("/health")
    res_alias = client.get("/health/")

    assert res_canonical.status_code == 200
    assert res_alias.status_code == 200
    assert res_alias.history == [], "Legacy alias should not perform 307/308 redirect"
    assert client.get("/catalog").status_code == 200
    catalog_alias = client.get("/catalog/")
    assert catalog_alias.status_code == 200
    assert catalog_alias.history == []
    assert catalog_alias.headers["deprecation"] == "true"


def test_legacy_alias_preserves_json_multipart_and_delete_without_redirect():
    json_body = {"items": [{"id": "one", "amount": 12.5}]}
    canonical_json = client.post("/contract/json", json=json_body)
    legacy_json = client.post("/contract/json/", json=json_body)
    assert canonical_json.status_code == legacy_json.status_code == 200
    assert canonical_json.json() == legacy_json.json() == json_body
    assert legacy_json.history == []

    files = {"attachment": ("proof.txt", b"same-body", "text/plain")}
    canonical_form = client.post("/contract/multipart", data={"label": "proof"}, files=files)
    legacy_form = client.post("/contract/multipart/", data={"label": "proof"}, files=files)
    assert canonical_form.status_code == legacy_form.status_code == 200
    assert canonical_form.json() == legacy_form.json()
    assert legacy_form.history == []

    canonical_delete = client.delete("/contract/example")
    legacy_delete = client.delete("/contract/example/")
    assert canonical_delete.status_code == legacy_delete.status_code == 204
    assert legacy_delete.history == []


def test_unit_request_id_and_unauthorized():
    """Prueba que X-Request-ID se envíe en respuestas 200 y en respuestas 401."""
    settings = get_settings()
    orig = settings.AUTH_REQUIRED
    try:
        settings.AUTH_REQUIRED = True

        # 200 OK en pública
        res_ok = client.get("/health")
        assert "x-request-id" in res_ok.headers
        assert res_ok.headers["x-content-type-options"] == "nosniff"
        assert res_ok.headers["x-frame-options"] == "DENY"
        assert res_ok.headers["referrer-policy"] == "no-referrer"
        uuid.UUID(res_ok.headers["x-request-id"])  # Debe ser UUID válido

        # 401 en privada sin token
        res_unauth = client.get("/private/resource")
        assert res_unauth.status_code == 401
        assert "x-request-id" in res_unauth.headers
        uuid.UUID(res_unauth.headers["x-request-id"])
        assert res_unauth.headers["x-content-type-options"] == "nosniff"

        # Preservar UUID del cliente si es válido
        valid_uuid = str(uuid.uuid4())
        res_custom = client.get("/health", headers={"X-Request-ID": valid_uuid})
        assert res_custom.headers.get("x-request-id") == valid_uuid

        # Reemplazar con UUID generado si el cliente envía texto inválido
        res_invalid = client.get("/health", headers={"X-Request-ID": "invalid-uuid-text"})
        assert res_invalid.headers.get("x-request-id") != "invalid-uuid-text"
        uuid.UUID(res_invalid.headers["x-request-id"])

        login_response = client.post("/auth/login")
        assert login_response.headers["cache-control"] == "no-store"
        assert login_response.headers["pragma"] == "no-cache"
    finally:
        settings.AUTH_REQUIRED = orig


def test_unit_cors_explicit_origins():
    """Prueba la política CORS estricta con orígenes permitidos y denegados."""
    # Permitiendo origin en la allowlist
    origin_ok = "http://localhost:5173"
    res_ok = client.options("/health", headers={"Origin": origin_ok, "Access-Control-Request-Method": "GET"})
    assert res_ok.headers.get("access-control-allow-origin") == origin_ok

    # Rechazando origin fuera de allowlist
    origin_bad = "http://evil-hacker.com"
    res_bad = client.options("/health", headers={"Origin": origin_bad, "Access-Control-Request-Method": "GET"})
    assert res_bad.headers.get("access-control-allow-origin") != origin_bad


def test_unit_ip_resolution_trusted_proxies():
    """Prueba la resolución de IP directa vs proxy confiable y prevención de falsificación XFF."""
    req_direct = Request({
        "type": "http",
        "client": ("198.51.100.5", 12345),
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 10.0.0.1")],
    })
    # Proxy no confiable: ignora XFF y retorna IP del cliente directo
    assert resolve_client_ip(req_direct) == "198.51.100.5"

    settings = get_settings()
    previous_cidrs = list(settings.TRUSTED_PROXY_CIDRS)
    settings.TRUSTED_PROXY_CIDRS = ["127.0.0.1/32", "10.0.0.0/8"]
    try:
        req_trusted = Request({
            "type": "http",
            "client": ("127.0.0.1", 12345),
            "headers": [(b"x-forwarded-for", b"203.0.113.195, 10.0.0.1")],
        })
        assert resolve_client_ip(req_trusted) == "203.0.113.195"

        req_spoofed_leftmost = Request({
            "type": "http",
            "client": ("127.0.0.1", 12345),
            "headers": [(b"x-forwarded-for", b"198.51.100.9, 203.0.113.195")],
        })
        assert resolve_client_ip(req_spoofed_leftmost) == "203.0.113.195"
    finally:
        settings.TRUSTED_PROXY_CIDRS = previous_cidrs

    req_malformed = Request({
        "type": "http",
        "client": ("127.0.0.1", 12345),
        "headers": [(b"x-forwarded-for", b"garbage, 203.0.113.195")],
    })
    assert resolve_client_ip(req_malformed) == "127.0.0.1"


def test_unit_rate_limiter():
    """Prueba unitaria aislada del Rate Limiter en-memoria concurrente."""
    ip = "192.0.2.45"
    scope = "test_scope"

    # Permite 3 peticiones
    assert check_rate_limit(ip, scope, max_requests=3, window_seconds=10)
    assert check_rate_limit(ip, scope, max_requests=3, window_seconds=10)
    assert check_rate_limit(ip, scope, max_requests=3, window_seconds=10)

    # La 4ta petición excede el límite
    assert not check_rate_limit(ip, scope, max_requests=3, window_seconds=10)


def test_transaction_voucher_urls_never_use_public_r2_domain():
    settings = get_settings()
    previous_public_url = settings.PUBLIC_URL
    previous_r2_url = settings.R2_PUBLIC_URL
    try:
        settings.PUBLIC_URL = "https://api.example.test"
        settings.R2_PUBLIC_URL = "https://public-r2.example.test"
        assert settings.media_public_url("home_banner/banner.webp") == (
            "https://public-r2.example.test/home_banner/banner.webp"
        )
        assert settings.media_public_url("transaction_vouchers/send.pdf") == (
            "https://api.example.test/media/transaction_vouchers/send.pdf"
        )
    finally:
        settings.PUBLIC_URL = previous_public_url
        settings.R2_PUBLIC_URL = previous_r2_url


def test_oauth_callbacks_do_not_accept_redirect_token_queries():
    """Los callbacks privados nunca deben volver a enviar credenciales en una URL."""
    from app.main import app as main_app

    paths = main_app.openapi()["paths"]
    for provider in ("google", "facebook"):
        operation = paths[f"/integraciones/oauth/{provider}/callback"]["get"]
        query_names = {
            parameter["name"]
            for parameter in operation.get("parameters", [])
            if parameter.get("in") == "query"
        }
        assert "redirect" not in query_names
