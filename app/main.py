# app/main.py

# Importar modelos para registro en SQLAlchemy
import app.models_registry

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
from app.modules.world_cup.routes import router as world_cup_router, public_router as world_cup_public_router
from app.modules.world_cup.scheduler import start_scheduler, stop_scheduler

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
    
    logger.info("✓ Aplicación iniciada correctamente")
    logger.info("=" * 70)
    
    start_scheduler()
    yield
    stop_scheduler()
    
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos estáticos (imágenes, etc.)
from pathlib import Path
from fastapi.responses import FileResponse, Response
from fastapi import HTTPException
import re

_media_path = Path("media")

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
    """Sirve archivos de media/. Fallback: profile_xxx.jpg → profile_images/ o placeholder."""
    # Evitar path traversal
    if ".." in file_path or file_path.startswith("/"):
        raise HTTPException(status_code=404, detail="Not found")
    # Fallback para profile_xxx.jpg en raíz (legacy)
    if _PROFILE_SINGLE.match(file_path):
        for candidate in [
            _media_path / "profile_images" / file_path,
            _media_path / file_path,
        ]:
            if candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
        # Imagen no existe: devolver placeholder (evita 404 en <img src>)
        return Response(
            content=_PROFILE_PLACEHOLDER_SVG,
            media_type="image/svg+xml",
        )
    # Ruta normal
    full_path = _media_path / file_path
    if full_path.exists() and full_path.is_file():
        return FileResponse(full_path)
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
app.include_router(world_cup_router)
app.include_router(world_cup_public_router)

@app.get("/")
async def root():
    return {"message": "Com Brasper API", "version": "1.0.0"}
