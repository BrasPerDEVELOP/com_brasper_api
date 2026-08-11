# app/modules/auth/infrastructure/auth_session_repository.py
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.modules.auth.domain.models import AuthSessionModel
from app.modules.auth.infrastructure.jwt_service import generate_opaque_refresh_token, hash_refresh_token
from app.modules.users.domain.models import User as UserModel


def _utc_now() -> datetime:
    """Devuelve UTC aware, consistente con las columnas TIMESTAMPTZ."""
    return datetime.now(timezone.utc)


class AuthSessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        user_id: uuid.UUID,
        client_app: str = "backoffice",
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        family_id: Optional[uuid.UUID] = None,
        parent_session_id: Optional[uuid.UUID] = None,
        rotation_number: int = 1,
    ) -> Tuple[AuthSessionModel, str]:
        """
        Crea una nueva sesión de autenticación y devuelve (session_model, raw_refresh_token).
        Sin hacer commit interno (para permitir control transaccional externo).
        """
        settings = get_settings()
        raw_token, token_hash = generate_opaque_refresh_token()
        now = _utc_now()
        expires_at = now + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)

        session_model = AuthSessionModel(
            id=uuid.uuid4(),
            user_id=user_id,
            refresh_token_hash=token_hash,
            family_id=family_id or uuid.uuid4(),
            parent_session_id=parent_session_id,
            rotation_number=rotation_number,
            client_app=client_app,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
            last_used_at=now,
            created_at=now,
            updated_at=now,
        )

        self.db.add(session_model)
        await self.db.flush()
        return session_model, raw_token

    async def rotate_refresh_token(
        self,
        raw_refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[AuthSessionModel, str]:
        """
        Rotación de refresh token transaccional de un solo uso con SELECT FOR UPDATE.
        Exige User.deleted == False y User.enable == True.
        Si se detecta reutilización: marca reuse_detected_at, revoca la familia completa en la misma transacción y lanza ValueError.
        """
        token_hash = hash_refresh_token(raw_refresh_token)

        # SELECT FOR UPDATE para bloquear la fila de sesión concurrentemente
        stmt = (
            select(AuthSessionModel, UserModel)
            .join(UserModel, UserModel.id == AuthSessionModel.user_id)
            .where(
                AuthSessionModel.refresh_token_hash == token_hash,
                UserModel.deleted.is_(False),
                UserModel.enable.is_(True),
            )
            .with_for_update(of=AuthSessionModel)
        )
        result = await self.db.execute(stmt)
        row = result.first()

        if not row:
            raise ValueError("Refresh token inválido o usuario no activo")

        session, user = row
        now = _utc_now()

        # Detección de reutilización
        if session.revoked_at is not None:
            session.reuse_detected_at = now
            await self.revoke_family_tx(session.family_id, reason="reuse_detected", reuse_at=now)
            await self.db.commit()
            raise ValueError("Reutilización de token detectada. Sesiones revocadas.")

        # Expiración
        if session.expires_at < now:
            session.revoked_at = now
            session.revoke_reason = "expired"
            await self.db.commit()
            raise ValueError("Refresh token expirado")

        # Marcar la sesión actual como rotada/revocada
        session.revoked_at = now
        session.revoke_reason = "rotated"
        session.last_used_at = now
        session.updated_at = now

        # Crear la nueva sesión hija atómicamente dentro de la misma transacción
        new_session, new_raw_token = await self.create_session(
            user_id=session.user_id,
            client_app=session.client_app,
            user_agent=user_agent or session.user_agent,
            ip_address=ip_address or session.ip_address,
            family_id=session.family_id,
            parent_session_id=session.id,
            rotation_number=session.rotation_number + 1,
        )

        # Dejar la transacción abierta para que el route incluya la auditoría y haga un solo commit
        return new_session, new_raw_token

    async def revoke_session_tx(self, session_id: uuid.UUID, reason: str = "logout") -> None:
        """Revoca una sesión específica dentro de la transacción activa (sin commit explícito)."""
        now = _utc_now()
        stmt = (
            update(AuthSessionModel)
            .where(AuthSessionModel.id == session_id, AuthSessionModel.revoked_at.is_(None))
            .values(revoked_at=now, revoke_reason=reason, updated_at=now)
        )
        await self.db.execute(stmt)

    async def revoke_session(self, session_id: uuid.UUID, reason: str = "logout") -> None:
        """Revoca una sesión específica con commit."""
        await self.revoke_session_tx(session_id, reason=reason)
        await self.db.commit()

    async def revoke_family_tx(self, family_id: uuid.UUID, reason: str = "logout", reuse_at: Optional[datetime] = None) -> None:
        """Revoca toda la familia dentro de la transacción activa (sin commit explícito)."""
        now = _utc_now()
        values = {"revoked_at": now, "revoke_reason": reason, "updated_at": now}
        if reuse_at:
            values["reuse_detected_at"] = reuse_at

        stmt = (
            update(AuthSessionModel)
            .where(AuthSessionModel.family_id == family_id, AuthSessionModel.revoked_at.is_(None))
            .values(**values)
        )
        await self.db.execute(stmt)

    async def revoke_family(self, family_id: uuid.UUID, reason: str = "logout") -> None:
        """Revoca toda la familia y ejecuta commit."""
        await self.revoke_family_tx(family_id, reason=reason)
        await self.db.commit()

    async def get_active_session_with_user(self, session_id: uuid.UUID) -> Optional[Tuple[AuthSessionModel, UserModel]]:
        """
        Obtiene una sesión activa (no revocada ni expirada) con su usuario activo (deleted=False, enable=True).
        """
        now = _utc_now()
        stmt = (
            select(AuthSessionModel, UserModel)
            .join(UserModel, UserModel.id == AuthSessionModel.user_id)
            .where(
                AuthSessionModel.id == session_id,
                AuthSessionModel.revoked_at.is_(None),
                AuthSessionModel.expires_at > now,
                UserModel.deleted.is_(False),
                UserModel.enable.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        return result.first()
