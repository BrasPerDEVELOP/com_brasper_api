# app/modules/auth/adapters/router/auth_routes.py
from fastapi import APIRouter, Form, Depends, HTTPException, status, Request
from typing import Optional

from pydantic import BaseModel

from app.modules.auth.application.use_cases import LoginUseCase, VerifyCredentialsUseCase
from app.modules.auth.application.schemas.auth_schema import (
    AuthCreateCmd,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
)
from app.modules.auth.infrastructure.dependencies import get_security_utils, get_auth_repository
from app.modules.auth.interfaces.auth_repository import AuthRepositoryInterface
from app.core.container import get_login_uc, get_auth_service

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
                content={"access_token": result.token, "token_type": "bearer"}
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
