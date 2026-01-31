# app/modules/users/application/user_service.py
"""Re-exporta los casos de uso para compatibilidad con container y routers."""
from app.modules.users.application.use_cases import (
    GetUserByIdUseCase,
    GetUserByEmailUseCase,
    GetUserByAuthIdUseCase,
    CreateUserUseCase,
    UpdateUserUseCase,
    DeleteUserUseCase,
    ListUserUseCase,
    ListUserNameUseCase,
    ListUsersWithDetailsUseCase,
)

__all__ = [
    "GetUserByIdUseCase",
    "GetUserByEmailUseCase",
    "GetUserByAuthIdUseCase",
    "CreateUserUseCase",
    "UpdateUserUseCase",
    "DeleteUserUseCase",
    "ListUserUseCase",
    "ListUserNameUseCase",
    "ListUsersWithDetailsUseCase",
]
