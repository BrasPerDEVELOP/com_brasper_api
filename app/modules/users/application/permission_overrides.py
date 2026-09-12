"""Authorization and validation for user access changes."""
from fastapi import HTTPException
from app.modules.auth.domain.permissions import validate_permission_deltas


def validate_user_access_change(cmd, previous, actor_id, permissions):
    supplied = any(getattr(cmd, key, None) is not None for key in
                   ("permissions_granted", "permissions_revoked"))
    if not supplied:
        return
    if not {"users.update", "roles.permissions.update"} <= set(permissions):
        raise HTTPException(403, "Se requieren users.update y roles.permissions.update")
    if previous and str(previous.id) == str(actor_id):
        raise HTTPException(403, "No puedes editar tus propios permisos")
    role = cmd.role if cmd.role is not None else getattr(previous, "role", None)
    role = getattr(role, "value", role)
    granted = cmd.permissions_granted
    revoked = cmd.permissions_revoked
    if granted is None:
        granted = getattr(previous, "permissions_granted", [])
    if revoked is None:
        revoked = getattr(previous, "permissions_revoked", [])
    try:
        validate_permission_deltas(role, granted, revoked)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
