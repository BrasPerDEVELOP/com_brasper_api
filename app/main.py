# app/main.py

# Importar modelos para registro en SQLAlchemy
import app.models_registry

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import get_settings

# Auth, User, Coin, Transactions, Integraciones
from app.modules.auth.adapters.router import router as auth_router
from app.modules.users.adapters.router import router as user_router
from app.modules.users.adapters.router.role_permission_routes import router as role_router
from app.modules.coin.adapters.router import router as coin_router
from app.modules.transactions.adapters.router import router as transaction_router
from app.modules.integraciones.adapters.router import router as integraciones_router
from app.modules.home_image.adapters.router import router as home_banner_router
from app.modules.brasper.adapters.router import router as brasper_router
from app.modules.blog.adapters.router import router as blog_router
from app.modules.metrics.adapters.router import router as metrics_router

settings = get_settings()

# Configurar logging
log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurar cache
settings.configure_cache()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager para eventos de startup y shutdown"""
    logger.info("=" * 70)
    logger.info("Iniciando aplicación Com Brasper API...")
    logger.info("=" * 70)
    
    logger.info("Verificando conexión con Cloudflare R2...")
    from app.shared.services.file_service import file_service

    await file_service.verify_connection()
    logger.info(f"✓ Cloudflare R2 conectado (bucket: {settings.R2_BUCKET_NAME})")
    logger.info("✓ Aplicación iniciada correctamente")
    logger.info("=" * 70)
    
    yield
    
    logger.info("=" * 70)
    logger.info("Cerrando aplicación...")
    logger.info("=" * 70)

app = FastAPI(
    title="Com Brasper API",
    description="API para gestión de usuarios y autenticación",
    version="1.0.0",
    root_path=settings.ROOT_PATH,
    debug=settings.DEBUG,
    lifespan=lifespan,
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    if settings.PUBLIC_URL:
        url = settings.PUBLIC_URL.rstrip("/")
        openapi_schema["servers"] = [{"url": url}]
    # Asegurar que TransactionCreateCmd esté en schemas (para Swagger POST /transactions/)
    from app.modules.transactions.application.schemas import TransactionCreateCmd
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "schemas" not in openapi_schema["components"]:
        openapi_schema["components"]["schemas"] = {}
    schemas = openapi_schema["components"]["schemas"]
    if "TransactionCreateCmd" not in schemas:
        # Usar ref_template para que $ref apunten a #/components/schemas/...
        schema = TransactionCreateCmd.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        defs = schema.pop("$defs", {})
        for name, def_schema in defs.items():
            if name not in schemas:
                schemas[name] = def_schema
        schemas["TransactionCreateCmd"] = schema
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# Middleware de auth (interno): debe ir antes que CORS en el registro.
# CORS se registra después para quedar en el borde del stack: así las respuestas
# cortas (p. ej. 401 sin token válido) siguen pasando por CORSMiddleware.
from app.middlewares.auth import TokenAuthMiddleware

app.add_middleware(TokenAuthMiddleware)

# Handlers globales: sin ellos, cualquier excepción no manejada se convierte en
# un 500 emitido por ServerErrorMiddleware SIN cabeceras CORS, que el navegador
# bloquea y axios reporta como "Network Error" en el backoffice.
from sqlalchemy.exc import IntegrityError
from fastapi.responses import JSONResponse


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.warning(f"IntegrityError en {request.url.path}: {exc.orig}")
    return JSONResponse(
        status_code=409,
        content={"detail": "Conflicto de datos: el registro ya existe o viola una restricción única."},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.warning(f"ValueError en {request.url.path}: {exc}")
    return JSONResponse(status_code=422, content={"detail": str(exc)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos estáticos (imágenes, etc.)
from fastapi.responses import RedirectResponse, Response
from fastapi import HTTPException
import re

from app.shared.services.file_service import file_service

# Solo rutas sin subcarpeta: /media/profile_xxx.jpg (legacy)
_PROFILE_SINGLE = re.compile(r"^profile_[a-zA-Z0-9\-]+\.(jpg|jpeg|png|webp|gif)$", re.I)

# Placeholder SVG cuando la imagen de perfil no existe (evita 404 en <img src>)
_PROFILE_PLACEHOLDER_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
    b'<rect width="100" height="100" fill="#e8e8e8"/>'
    b'<circle cx="50" cy="38" r="14" fill="#b0b0b0"/>'
    b'<ellipse cx="50" cy="88" rx="28" ry="22" fill="#b0b0b0"/>'
    b"</svg>"
)


@app.get("/media/{file_path:path}")
async def serve_media(file_path: str):
    """Sirve archivos desde Cloudflare R2. Fallback: profile_xxx.jpg → profile_images/ o placeholder."""
    if ".." in file_path or file_path.startswith("/"):
        raise HTTPException(status_code=404, detail="Not found")

    if settings.R2_PUBLIC_URL:
        key = file_path
        if _PROFILE_SINGLE.match(file_path):
            key = f"profile_images/{file_path}"
        return RedirectResponse(settings.media_public_url(key), status_code=302)

    candidates = [file_path]
    if _PROFILE_SINGLE.match(file_path):
        candidates = [f"profile_images/{file_path}", file_path]

    for key in candidates:
        result = await file_service.read_file(key)
        if result:
            content, media_type = result
            return Response(content=content, media_type=media_type)

    if _PROFILE_SINGLE.match(file_path):
        return Response(
            content=_PROFILE_PLACEHOLDER_SVG,
            media_type="image/svg+xml",
        )

    raise HTTPException(status_code=404, detail="Not found")


# Incluir routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(role_router)
app.include_router(coin_router)
app.include_router(transaction_router)
app.include_router(integraciones_router)
app.include_router(home_banner_router)
app.include_router(brasper_router)
app.include_router(blog_router)
app.include_router(metrics_router)

@app.get("/")
async def root():
    return {"message": "Com Brasper API", "version": "1.0.0"}
