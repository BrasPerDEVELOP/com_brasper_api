import uuid
from uuid import UUID

from fastapi import APIRouter, File, Form, Depends, HTTPException, status, Request, UploadFile
from typing import Optional

from pydantic import BaseModel

from app.shared.services.file_service import save_profile_image

from app.modules.auth.application.use_cases import LoginUseCase, VerifyCredentialsUseCase
from app.modules.auth.application.schemas.auth_schema import (
    AuthCreateCmd,
    ChangePasswordRequest,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
)
from app.modules.auth.infrastructure.dependencies import (
    get_security_utils,
    get_auth_repository,
    get_current_user,
    get_current_user_permissions,
    get_optional_current_user,
    require_permission,
)
from app.modules.auth.interfaces.auth_repository import AuthRepositoryInterface
from app.modules.users.application.schemas.user_schema import (
    UpdateCurrentUserCmd,
    UserReadDTO,
    UserUpdateCmd,
)
from app.core.container import get_login_uc, get_auth_service, get_user_by_id_uc, update_user_uc

import logging

from app.core.routing import LegacyAliasRouter
from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit

logger = logging.getLogger(__name__)
router = LegacyAliasRouter(prefix="/auth", tags=["authentication"])


class CreateAuthRequest(BaseModel):
    username: str
    password: str


async def get_login_data(
    request: Request,
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
):
    if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
        return AuthCreateCmd(username=username, password=password)
    body = await request.json()
    return AuthCreateCmd(**body)


@router.get("/me", response_model=UserReadDTO)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    permissions=Depends(get_current_user_permissions),
    use_case=Depends(get_user_by_id_uc),
):
    """
    Obtiene el perfil del usuario autenticado. Alternativa: GET /user/{user_id}.

    Requiere autenticación pero ningún permiso: el frontend usa esta ruta para
    restaurar la sesión, así que exigir `profile.view` dejaría fuera del panel a
    todo un rol al que se le desmarcara ese permiso, sin forma de revertirlo
    desde la propia UI.
    """
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    result = await use_case.execute(UUID(user_id))
    if not result:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    result.permissions = permissions
    return result


async def _update_me(cmd: UpdateCurrentUserCmd, current_user: dict, use_case, permissions: list[str]):
    """Lógica común para POST y PUT /auth/me/."""
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    update_cmd = UserUpdateCmd(id=UUID(user_id), **cmd.model_dump(exclude_unset=True))
    result = await use_case.execute(update_cmd)
    if not result:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    result.permissions = permissions
    return result


@router.post("/me", response_model=UserReadDTO, status_code=status.HTTP_200_OK)
async def create_or_update_current_user(
    cmd: UpdateCurrentUserCmd,
    current_user: dict = Depends(get_current_user),
    permissions=Depends(require_permission("profile.update")),
    use_case=Depends(update_user_uc),
    get_use_case=Depends(get_user_by_id_uc),
    audit_event=Depends(stage_mutation_audit("profile.update", "user")),
):
    """Crea o actualiza el perfil del usuario autenticado. Todos los campos opcionales."""
    if audit_event and current_user and current_user.get("user_id"):
        audit_event.entity_id = str(current_user["user_id"])
        previous = await get_use_case.execute(UUID(current_user["user_id"]))
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
        audit_event.new_values = cmd.model_dump(mode="json", exclude_unset=True)
    return await _update_me(cmd, current_user, use_case, permissions)


@router.put("/me", response_model=UserReadDTO)
async def update_current_user(
    cmd: UpdateCurrentUserCmd,
    current_user: dict = Depends(get_current_user),
    permissions=Depends(require_permission("profile.update")),
    use_case=Depends(update_user_uc),
    get_use_case=Depends(get_user_by_id_uc),
    audit_event=Depends(stage_mutation_audit("profile.update", "user")),
):
    """Actualiza el perfil del usuario autenticado. Todos los campos opcionales."""
    if audit_event and current_user and current_user.get("user_id"):
        audit_event.entity_id = str(current_user["user_id"])
        previous = await get_use_case.execute(UUID(current_user["user_id"]))
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
        audit_event.new_values = cmd.model_dump(mode="json", exclude_unset=True)
    return await _update_me(cmd, current_user, use_case, permissions)


@router.post("/me/profile-image")
async def upload_profile_image(
    profile_image: UploadFile = File(..., description="Imagen de perfil (.png, .jpg, .jpeg, .webp, .gif)"),
    current_user: dict = Depends(get_current_user),
    _permissions=Depends(require_permission("profile.update")),
    audit_event=Depends(stage_mutation_audit("profile.update_image", "user")),
):
    """Sube imagen de perfil. Retorna la ruta para usar en PUT /auth/me/ (campo profile_image)."""
    if not current_user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if audit_event:
        audit_event.entity_id = str(current_user["user_id"])
    path = await save_profile_image(profile_image)
    if not path:
        raise HTTPException(status_code=400, detail="No se pudo guardar la imagen")
    return {"profile_image": path}


from sqlalchemy import select
from fastapi.responses import JSONResponse
from app.core.settings import get_settings
from app.db.base import get_db
from app.modules.auth.domain.models import AuthSessionModel
from app.modules.auth.infrastructure.auth_session_repository import AuthSessionRepository
from app.modules.auth.infrastructure.jwt_service import create_access_token, hash_refresh_token
from app.modules.auth.infrastructure.cookies import MEDIA_COOKIE_NAME, MEDIA_COOKIE_PATH
from app.middlewares.security import resolve_client_ip


def _validate_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin:
        settings = get_settings()
        if origin not in settings.CORS_ALLOWED_ORIGINS:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origen no permitido para esta operación")


def set_refresh_cookie(response: JSONResponse, raw_refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        path="/auth",
        max_age=settings.REFRESH_TOKEN_TTL_DAYS * 86400,
    )


def set_media_cookie(response: JSONResponse, access_token: str) -> None:
    """
    Copia el access token en una cookie limitada a `/media`.

    Los comprobantes se muestran con `<img src>` y se abren en pestaña nueva, y
    el navegador no adjunta la cabecera `Authorization` en ninguno de los dos
    casos: sin esto el panel recibe 401 en cada imagen. La cookie usa el mismo
    token y la misma caducidad corta, así que no amplía el acceso; solo cambia
    el transporte para las descargas que inicia el navegador.
    """
    settings = get_settings()
    response.set_cookie(
        key=MEDIA_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        path=MEDIA_COOKIE_PATH,
        max_age=settings.JWT_ACCESS_TTL_MINUTES * 60,
    )


def clear_media_cookie(response: JSONResponse) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=MEDIA_COOKIE_NAME,
        path=MEDIA_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def clear_refresh_cookie(response: JSONResponse) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path="/auth",
        domain=settings.REFRESH_COOKIE_DOMAIN,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
from app.modules.audit.infrastructure.audit_repository import AuditRepository


async def _log_failed_login_best_effort(
    db,
    request: Request,
    attempted_username: Optional[str] = None,
    failure_reason: Optional[str] = None,
    client_app: str = "backoffice",
) -> None:
    """Los intentos fallidos se guardan fuera de la transacción del login."""
    try:
        req_id_str = getattr(request.state, "request_id", None)
        req_id = UUID(req_id_str) if req_id_str else uuid.uuid4()
        client_ip = resolve_client_ip(request)
        user_agent = request.headers.get("user-agent")

        audit_repo = AuditRepository(db)
        await audit_repo.log_login_event(
            success=False,
            request_id=req_id,
            attempted_username=attempted_username,
            failure_reason=failure_reason,
            ip_address=client_ip,
            user_agent=user_agent,
            source=client_app,
        )
        await db.commit()
    except Exception as audit_err:
        logger.error(f"Error registrando evento de auditoría de login: {audit_err}")


def _login_failure_reason(error: Exception) -> str:
    """Código estable sin copiar excepciones, credenciales ni detalles internos."""
    if isinstance(error, HTTPException):
        return f"http_{error.status_code}"
    if isinstance(error, ValueError):
        return "invalid_credentials"
    return "internal_error"


from sqlalchemy import select, update
from app.middlewares.auth import get_current_token
from app.modules.auth.domain.models import AuthModel, AuthSessionModel


@router.post("/login", response_model=None)
async def login(
    request: Request,
    login_data: AuthCreateCmd = Depends(get_login_data),
    use_case: LoginUseCase = Depends(get_login_uc),
    db=Depends(get_db),
):
    client_ip = resolve_client_ip(request)
    user_agent = request.headers.get("user-agent")
    client_app = request.headers.get("X-Client-App", "backoffice")
    if client_app not in ("backoffice", "www"):
        client_app = "backoffice"

    try:
        result = await use_case.execute(login_data, client_ip, defer_commit=True)
        settings = get_settings()
        user_data = result.user.model_dump(mode="json")

        if settings.AUTH_MODE.lower() == "legacy":
            req_id_str = getattr(request.state, "request_id", None)
            req_id = UUID(req_id_str) if req_id_str else uuid.uuid4()
            await AuditRepository(db).log_login_event(
                success=True,
                request_id=req_id,
                attempted_username=login_data.username,
                user_id=result.user.id,
                ip_address=client_ip,
                user_agent=user_agent,
                source=client_app,
            )
            await db.commit()
            return JSONResponse(
                content={
                    "access_token": result.token,
                    "token_type": "bearer",
                    "user": user_data,
                }
            )

        # Crear sesión JWT y refresh token en BD
        session_repo = AuthSessionRepository(db)
        session_model, raw_refresh_token = await session_repo.create_session(
            user_id=result.user.id,
            client_app=client_app,
            user_agent=user_agent,
            ip_address=client_ip,
        )

        audit_repo = AuditRepository(db)
        req_id_str = getattr(request.state, "request_id", None)
        req_id = UUID(req_id_str) if req_id_str else uuid.uuid4()

        await audit_repo.log_login_event(
            success=True,
            request_id=req_id,
            attempted_username=login_data.username,
            user_id=result.user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            source=client_app,
            session_id=session_model.id,
        )
        await db.commit()

        access_token, _ = create_access_token(
            user_id=result.user.id,
            session_id=session_model.id,
            client_app=client_app,
        )

        response_data = {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_data,
        }

        response = JSONResponse(content=response_data)
        set_refresh_cookie(response, raw_refresh_token)
        set_media_cookie(response, access_token)
        return response
    except Exception as e:
        await db.rollback()
        # Registrar intento de login fallido en transacción aislada
        from app.db.base import AsyncSessionLocal
        async with AsyncSessionLocal() as audit_db:
            await _log_failed_login_best_effort(
                audit_db,
                request=request,
                attempted_username=login_data.username,
                failure_reason=_login_failure_reason(e),
                client_app=client_app,
            )

        if isinstance(e, HTTPException):
            raise e
        if isinstance(e, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar el inicio de sesión",
        )


@router.post("/refresh", response_model=dict)
async def refresh(
    request: Request,
    db=Depends(get_db),
):
    _validate_origin(request)
    settings = get_settings()
    raw_refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)

    if not raw_refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token no proporcionado en cookie")

    client_ip = resolve_client_ip(request)
    user_agent = request.headers.get("user-agent")

    session_repo = AuthSessionRepository(db)
    try:
        new_session, new_raw_refresh = await session_repo.rotate_refresh_token(
            raw_refresh_token=raw_refresh_token,
            user_agent=user_agent,
            ip_address=client_ip,
        )

        audit_repo = AuditRepository(db)
        req_id_str = getattr(request.state, "request_id", None)
        req_id = UUID(req_id_str) if req_id_str else uuid.uuid4()
        await audit_repo.log_audit_event(
            action="auth.refresh",
            entity="auth_session",
            entity_id=str(new_session.id),
            request_id=req_id,
            actor_user_id=new_session.user_id,
            source=new_session.client_app,
            ip_address=client_ip,
            user_agent=user_agent,
            method="POST",
            path="/auth/refresh",
            status_code=200,
            success=True,
        )
        await db.commit()

        new_access_token, _ = create_access_token(
            user_id=new_session.user_id,
            session_id=new_session.id,
            client_app=new_session.client_app,
        )

        response = JSONResponse(
            content={
                "access_token": new_access_token,
                "token_type": "bearer",
            }
        )
        set_refresh_cookie(response, new_raw_refresh)
        set_media_cookie(response, new_access_token)
        return response
    except ValueError as e:
        response = JSONResponse(status_code=401, content={"detail": str(e)})
        clear_refresh_cookie(response)
        clear_media_cookie(response)
        return response


@router.post("/logout", response_model=dict)
async def logout(
    request: Request,
    current_user: dict = Depends(get_optional_current_user),
    db=Depends(get_db),
):
    """
    Cierra la sesión con o sin access token válido. La autoridad para revocar es
    la cookie de refresh, no el access token: exigir este último dejaría sesiones
    vivas cada vez que el usuario cierra pasados los 15 minutos de TTL.
    """
    _validate_origin(request)
    settings = get_settings()
    raw_refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    session_repo = AuthSessionRepository(db)
    user_id = UUID(current_user["user_id"]) if current_user and current_user.get("user_id") else None

    # 1. Revocar sesión JWT si existe en contexto
    if current_user and current_user.get("session_id"):
        try:
            sid = UUID(current_user["session_id"])
            await session_repo.revoke_session_tx(sid, reason="logout")
        except (ValueError, TypeError):
            pass

    # 2. Revocar familia de sesión por cookie si está presente
    if raw_refresh_token:
        h = hash_refresh_token(raw_refresh_token)
        stmt = select(AuthSessionModel).where(AuthSessionModel.refresh_token_hash == h)
        res = await db.execute(stmt)
        s_model = res.scalar_one_or_none()
        if s_model:
            await session_repo.revoke_family_tx(s_model.family_id, reason="logout")
            if not user_id:
                user_id = s_model.user_id

    # 3. Invalidar token opaco si vino en el request
    current_token = get_current_token()
    if current_token:
        await db.execute(
            update(AuthModel)
            .where(AuthModel.token == current_token)
            .values(token=None)
        )

    # 4. Registrar evento de auditoría de logout
    req_id_str = getattr(request.state, "request_id", None)
    req_id = UUID(req_id_str) if req_id_str else uuid.uuid4()
    client_ip = resolve_client_ip(request)
    user_agent = request.headers.get("user-agent")

    audit_repo = AuditRepository(db)
    await audit_repo.log_audit_event(
        action="auth.logout",
        entity="auth_session",
        request_id=req_id,
        actor_user_id=user_id,
        actor_username=current_user.get("username") if current_user else None,
        actor_role=current_user.get("role") if current_user else None,
        source=current_user.get("client_app", "backoffice") if current_user else "backoffice",
        ip_address=client_ip,
        user_agent=user_agent,
        method="POST",
        path="/auth/logout",
        status_code=200,
        success=True,
    )

    # 5. Un solo commit para toda la operación de logout
    await db.commit()

    response = JSONResponse(content={"message": "Logged out successfully"})
    clear_refresh_cookie(response)
    clear_media_cookie(response)
    return response


@router.post("/change-password", response_model=dict)
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    _permissions=Depends(require_permission("profile.change_password")),
    auth_service=Depends(get_auth_service),
    audit_event=Depends(stage_mutation_audit("auth.change_password", "user")),
):
    """
    Cambia la contraseña del usuario autenticado.

    El panel depende de esta ruta para el cambio voluntario y para el cambio
    forzado de `must_change_password`: sin ella, una cuenta marcada no puede
    completar el flujo. Nunca se auditan las contraseñas, solo la acción.
    """
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    audit_event.entity_id = str(user_id)
    try:
        await auth_service.change_password(
            UUID(user_id),
            request.current_password,
            request.new_password,
        )
        return {"message": "Password changed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/reset-password")
async def request_password_reset(
    request: PasswordResetRequest,
    auth_service=Depends(get_auth_service),
    audit_event=Depends(stage_mutation_audit("auth.reset_password_request", "user")),
):
    try:
        await auth_service.generate_password_reset(request.email)
        return {"message": "If the email exists, a password reset code has been sent"}
    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        return {"message": "If the email exists, a password reset code has been sent"}


@router.post("/reset-password/confirm")
async def confirm_password_reset(
    request: PasswordResetConfirmRequest,
    auth_service=Depends(get_auth_service),
    audit_event=Depends(stage_mutation_audit("auth.reset_password_confirm", "user")),
):
    try:
        await auth_service.reset_password(
            request.username,
            request.recovery_code,
            request.new_password,
        )
        logger.info("Password reset successful")
        return {"message": "Password has been reset successfully"}
    except ValueError as e:
        logger.warning(f"Password reset confirmation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request",
        )
