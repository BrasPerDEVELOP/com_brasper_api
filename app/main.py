# app/main.py

# Importar modelos para registro en SQLAlchemy
import app.models_registry

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import get_settings

# Auth, User, Coin, Transactions
from app.modules.auth.adapters.router import router as auth_router
from app.modules.users.adapters.router import router as user_router
from app.modules.coin.adapters.router import router as coin_router
from app.modules.transactions.adapters.router import router as transaction_router

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

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de auth desactivado por el momento (sin tokens)
# app.add_middleware(TokenAuthMiddleware)

# Incluir routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(coin_router)
app.include_router(transaction_router)

@app.get("/")
async def root():
    return {"message": "Com Brasper API", "version": "1.0.0"}
