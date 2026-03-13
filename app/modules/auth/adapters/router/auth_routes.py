# app/modules/auth/adapters/router/auth_routes.py
from uuid import UUID

from fastapi import APIRouter, File, Form, Depends, HTTPException, status, Request, UploadFile
from typing import Optional

from pydantic import BaseModel

from app.shared.services.file_service import save_profile_image

from app.modules.auth.application.use_cases import LoginUseCase, VerifyCredentialsUseCase
from app.modules.auth.application.schemas.auth_schema import (
    AuthCreateCmd,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
)
from app.modules.auth.infrastructure.dependencies import (
    get_security_utils,
    get_auth_repository,
    get_current_user,
)
from app.modules.auth.interfaces.auth_repository import AuthRepositoryInterface
from app.modules.users.application.schemas.user_schema import (
    UpdateCurrentUserCmd,
    UserReadDTO,
    UserUpdateCmd,
)
from app.core.container import get_login_uc, get_auth_service, get_user_by_id_uc, update_user_uc

import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


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


@router.get("/me/", response_model=UserReadDTO)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    use_case=Depends(get_user_by_id_uc),
):
    """Obtiene el perfil del usuario autenticado. Alternativa: GET /user/{user_id}."""
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
    return result


async def _update_me(cmd: UpdateCurrentUserCmd, current_user: dict, use_case):
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
    return result


@router.post("/me/", response_model=UserReadDTO, status_code=status.HTTP_200_OK)
async def create_or_update_current_user(
    cmd: UpdateCurrentUserCmd,
    current_user: dict = Depends(get_current_user),
    use_case=Depends(update_user_uc),
):
    """Crea o actualiza el perfil del usuario autenticado. Todos los campos opcionales."""
    return await _update_me(cmd, current_user, use_case)


@router.put("/me/", response_model=UserReadDTO)
async def update_current_user(
    cmd: UpdateCurrentUserCmd,
    current_user: dict = Depends(get_current_user),
    use_case=Depends(update_user_uc),
):
    """Actualiza el perfil del usuario autenticado. Todos los campos opcionales."""
    return await _update_me(cmd, current_user, use_case)


@router.post("/me/profile-image")
async def upload_profile_image(
    profile_image: UploadFile = File(..., description="Imagen de perfil (.png, .jpg, .jpeg, .webp, .gif)"),
    current_user: dict = Depends(get_current_user),
):
    """Sube imagen de perfil. Retorna la ruta para usar en PUT /auth/me/ (campo profile_image)."""
    if not current_user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    path = await save_profile_image(profile_image)
    if not path:
        raise HTTPException(status_code=400, detail="No se pudo guardar la imagen")
    return {"profile_image": path}


@router.post("/login/", response_model=None)
async def login(
    request: Request,
    login_data: AuthCreateCmd = Depends(get_login_data),
    use_case: LoginUseCase = Depends(get_login_uc),
):
    try:
        client_ip = request.client.host if request.client else "unknown"
        result = await use_case.execute(login_data, client_ip)
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/x-www-form-urlencoded"):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                content={
                    "access_token": result.token,
                    "token_type": "bearer",
                    "user": result.user.model_dump(mode="json"),
                }
            )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/verify-credentials", response_model=dict)
async def verify_credentials(
    payload: CreateAuthRequest,
    auth_repo: AuthRepositoryInterface = Depends(get_auth_repository),
):
    security_utils = get_security_utils()
    use_case = VerifyCredentialsUseCase(auth_repo, security_utils)
    try:
        await use_case.execute(
            AuthCreateCmd(username=payload.username, password=payload.password)
        )
        return {"valid": True}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error",
        )


@router.post("/logout", response_model=dict)
async def logout(
    auth_repo: AuthRepositoryInterface = Depends(get_auth_repository),
):
    try:
        logger.info("Logout (sin token por el momento)")
        return {"message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout",
        )


@router.post("/reset-password")
async def request_password_reset(
    request: PasswordResetRequest,
    auth_service=Depends(get_auth_service),
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
