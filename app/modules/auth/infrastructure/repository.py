# com_build_api/app/auth/infrastructure/repository.py
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
import logging

from app.modules.auth.interfaces.auth_repository import AuthRepositoryInterface
from app.modules.auth.domain.credentials import Credentials
from app.modules.auth.domain.models import AuthModel

logger = logging.getLogger(__name__)

class SQLAlchemyAuthRepository(AuthRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, auth_id: UUID) -> Optional[Credentials]:
        try:
            query = select(AuthModel).where(AuthModel.id == auth_id)
            result = await self.session.execute(query)
            auth_model = result.scalars().first()
            
            if not auth_model:
                return None
                
            return Credentials(
                id=auth_model.id,
                username=auth_model.username,
                password=auth_model.password,
                recovery_code=auth_model.recovery_code,
                token=auth_model.token,
                created_at=auth_model.created_at,
                updated_at=auth_model.updated_at
            )
        except Exception as e:
            logger.error(f"Error in get_by_id: {str(e)}")
            raise
    
    async def get_by_username(self, username: str) -> Optional[Credentials]:
        try:
            safe_username = username.lower()
            
            query = select(AuthModel).where(AuthModel.username == safe_username)
            result = await self.session.execute(query)
            auth_model = result.scalars().first()
            
            if not auth_model:
                return None
                
            return Credentials(
                id=auth_model.id,
                username=auth_model.username,
                password=auth_model.password,
                recovery_code=auth_model.recovery_code,
                token=auth_model.token,
                created_at=auth_model.created_at,
                updated_at=auth_model.updated_at
            )
        except Exception as e:
            logger.error(f"Error in get_by_username: {str(e)}")
            raise
    
    async def create(self, credentials: Credentials) -> Credentials:
        """Persiste credenciales. Commit/rollback lo gestiona el Unit of Work."""
        safe_username = credentials.username.lower()
        auth_model = AuthModel(
            id=credentials.id,
            username=safe_username,
            password=credentials.password,
            recovery_code=credentials.recovery_code,
            token=credentials.token,
        )
        self.session.add(auth_model)
        await self.session.flush()
        return Credentials(
            id=auth_model.id,
            username=auth_model.username,
            password=auth_model.password,
            recovery_code=auth_model.recovery_code,
            token=auth_model.token,
            created_at=auth_model.created_at,
            updated_at=auth_model.updated_at,
        )
    
    async def update_token(self, auth_id: UUID, token: Optional[str] = None) -> bool:
        """Actualiza o revoca el token. Commit lo gestiona el Unit of Work."""
        stmt = (
            update(AuthModel)
            .where(AuthModel.id == auth_id)
            .values(token=token)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0
    
    async def get_by_token(self, token: str) -> Optional[Credentials]:
        """Obtiene credenciales por token"""
        try:
            query = select(AuthModel).where(AuthModel.token == token)
            result = await self.session.execute(query)
            auth_model = result.scalars().first()
            
            if not auth_model:
                return None
                
            return Credentials(
                id=auth_model.id,
                username=auth_model.username,
                password=auth_model.password,
                recovery_code=auth_model.recovery_code,
                token=auth_model.token,
                created_at=auth_model.created_at,
                updated_at=auth_model.updated_at
            )
        except Exception as e:
            logger.error(f"Error in get_by_token: {str(e)}")
            raise
    
    async def update_password(self, auth_id: UUID, hashed_password: str) -> bool:
        """Actualiza contraseña. Commit lo gestiona el Unit of Work."""
        stmt = (
            update(AuthModel)
            .where(AuthModel.id == auth_id)
            .values(password=hashed_password)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0
    
    async def update_recovery_code(self, auth_id: UUID, recovery_code: Optional[str]) -> bool:
        """Actualiza código de recuperación. Commit lo gestiona el Unit of Work."""
        stmt = (
            update(AuthModel)
            .where(AuthModel.id == auth_id)
            .values(recovery_code=recovery_code)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def delete(self, auth_id: UUID) -> bool:
        """Elimina credenciales. Commit lo gestiona el Unit of Work."""
        from sqlalchemy import delete
        stmt = delete(AuthModel).where(AuthModel.id == auth_id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0
