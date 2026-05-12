# app/modules/users/adapters/router/user_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status, File
from uuid import UUID
from typing import Annotated, List, Optional

from app.shared.services.file_service import save_profile_image

from app.modules.auth.application.schemas.auth_schema import AdminResetPasswordRequest, UserInfoDTO
from app.modules.auth.infrastructure.dependencies import require_permission
from app.modules.users.application.schemas.user_schema import (
    UserCreateCmd,
    UserNameDTO,
    UserReadGeneralDTO,
    UserUpdateCmd,
    UserReadDTO,
)
from app.modules.users.application.user_service import (
    GetUserByEmailUseCase,
    GetUserByAuthIdUseCase,
    CreateUserUseCase,
    ListUserNameUseCase,
    ListUserUseCase,
    ListUsersWithDetailsUseCase,
    ListSalesUserIdsUseCase,
    UpdateUserUseCase,
    DeleteUserUseCase,
)
from app.core.container import (
    get_user_by_email_uc,
    get_user_by_auth_id_uc,
    create_user_uc,
    list_user_name_uc,
    list_users_uc,
    list_users_with_details_uc,
    list_sales_user_ids_uc,
    update_user_uc,
    delete_user_uc,
    get_auth_service,
)

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/email/{email}", response_model=UserReadDTO)
async def get_user_by_email(
    email: str,
    use_case: GetUserByEmailUseCase = Depends(get_user_by_email_uc),
    _permissions=Depends(require_permission("users.view")),
):
    user = await use_case.execute(email)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@router.get("/auth-id/{auth_id}", response_model=UserReadDTO)
async def get_user_by_auth_id(
    auth_id: UUID,
    use_case: GetUserByAuthIdUseCase = Depends(get_user_by_auth_id_uc),
    _permissions=Depends(require_permission("users.view")),
):
    user = await use_case.execute(auth_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@router.post("/", response_model=UserReadDTO, status_code=status.HTTP_201_CREATED)
async def create_user(
    form_data: Annotated[tuple[UserCreateCmd, Optional[UploadFile]], Depends(UserCreateCmd.from_form)],
    use_case: CreateUserUseCase = Depends(create_user_uc),
    _permissions=Depends(require_permission("users.create")),
):
    cmd, image = form_data
    return await use_case.execute(cmd, image)


@router.put("/", response_model=UserReadDTO)
async def update_user(
    form_data: Annotated[tuple[UserUpdateCmd, Optional[UploadFile]], Depends(UserUpdateCmd.from_form)],
    use_case: UpdateUserUseCase = Depends(update_user_uc),
    _permissions=Depends(require_permission("users.update")),
):
    cmd, profile_image_file = form_data
    if profile_image_file and profile_image_file.filename:
        image_path = await save_profile_image(profile_image_file)
        if image_path:
            cmd.profile_image = image_path
    return await use_case.execute(cmd)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    use_case: DeleteUserUseCase = Depends(delete_user_uc),
    _permissions=Depends(require_permission("users.delete")),
):
    await use_case.execute(user_id)


@router.post("/{user_id}/reset-password/", response_model=dict)
async def reset_user_password(
    user_id: UUID,
    request: AdminResetPasswordRequest,
    _permissions=Depends(require_permission("users.reset_password")),
    auth_service=Depends(get_auth_service),
):
    try:
        await auth_service.admin_reset_password(user_id, request.new_password)
        return {"message": "Temporary password assigned successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/sales-ids/", response_model=List[UUID])
async def list_sales_user_ids(
    use_case: ListSalesUserIdsUseCase = Depends(list_sales_user_ids_uc),
    _permissions=Depends(require_permission("users.view")),
):
    """Devuelve los IDs de usuarios con rol sales."""
    return await use_case.execute()


@router.get("/detail/", response_model=List[UserInfoDTO])
async def list_users_with_details(
    use_case: ListUsersWithDetailsUseCase = Depends(list_users_with_details_uc),
    user_id: Optional[UUID] = Query(None, description="Filtro por ID de usuario"),
    role: Optional[str] = Query(None, description="Filtro por rol (user, sales, admin, client, etc.)"),
    _permissions=Depends(require_permission("users.view")),
):
    """Lista usuarios con detalles. Filtros: user_id, role."""
    return await use_case.execute(user_id=user_id, role=role)


@router.get("/", response_model=List[UserReadGeneralDTO])
async def list_users(
    use_case: ListUserUseCase = Depends(list_users_uc),
    user_id: Optional[UUID] = Query(None, description="Filtro por ID de usuario"),
    role: Optional[str] = Query(None, description="Filtro por rol (user, sales, admin, client, etc.)"),
    _permissions=Depends(require_permission("users.view")),
):
    """Lista usuarios. Filtros: user_id, role. Si user_id no existe → 404."""
    users = await use_case.execute(user_id=user_id, role=role)
    if user_id is not None and not users:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return users


@router.get("/name-list/", response_model=List[UserNameDTO])
async def list_user_name(
    use_case: ListUserNameUseCase = Depends(list_user_name_uc),
    user_id: Optional[UUID] = Query(None, description="Filtro por ID de usuario"),
    role: Optional[str] = Query(None, description="Filtro por rol"),
    _permissions=Depends(require_permission("users.view")),
):
    """Lista usuarios con id, names, lastnames. Filtros: user_id, role."""
    return await use_case.execute(user_id=user_id, role=role)
