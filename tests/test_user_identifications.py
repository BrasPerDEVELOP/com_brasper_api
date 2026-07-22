from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.users.application.schemas.user_schema import UserCreateCmd, UserUpdateCmd
from app.modules.users.application.use_cases.user_use_cases import (
    _sync_legacy_primary,
    _sync_primary_from_legacy,
)
from app.modules.users.domain.models import User, UserIdentification


def test_create_cmd_normalizes_one_primary_identification():
    cmd = UserCreateCmd.model_validate({
        "identifications": [
            {"document_type": "dni", "document_number": "12345678", "is_primary": True},
            {"document_type": "cpf", "document_number": "12345678901", "is_primary": True},
        ]
    })

    assert cmd.identifications is not None
    assert [item.is_primary for item in cmd.identifications] == [True, False]


def test_create_cmd_promotes_first_identification_when_none_is_primary():
    cmd = UserCreateCmd.model_validate({
        "identifications": [
            {"document_type": "cpf", "document_number": "12345678901"},
        ]
    })

    assert cmd.identifications is not None
    assert cmd.identifications[0].is_primary is True


def test_create_cmd_rejects_duplicate_identifications():
    with pytest.raises(ValidationError, match="No se puede repetir"):
        UserCreateCmd.model_validate({
            "identifications": [
                {"document_type": "dni", "document_number": "12345678"},
                {"document_type": "dni", "document_number": "12345678"},
            ]
        })


def test_update_cmd_distinguishes_omitted_from_empty_identifications():
    omitted = UserUpdateCmd(id=uuid4())
    cleared = UserUpdateCmd(id=uuid4(), identifications=[])

    assert "identifications" not in omitted.model_fields_set
    assert "identifications" in cleared.model_fields_set


def test_legacy_fields_follow_primary_identification():
    user = User()
    user.identifications = [
        UserIdentification(document_type="dni", document_number="12345678", is_primary=False, position=0),
        UserIdentification(document_type="cpf", document_number="12345678901", is_primary=True, position=1),
    ]

    _sync_legacy_primary(user)

    assert user.document_type == "cpf"
    assert user.document_number == "12345678901"


def test_legacy_update_changes_only_primary_identification():
    user = User(document_type="dni", document_number="87654321")
    user.identifications = [
        UserIdentification(document_type="dni", document_number="12345678", is_primary=True, position=0),
        UserIdentification(document_type="cpf", document_number="12345678901", is_primary=False, position=1),
    ]

    _sync_primary_from_legacy(user)

    assert user.identifications[0].document_number == "87654321"
    assert user.identifications[1].document_number == "12345678901"


def test_apply_identifications_reuses_existing_rows():
    """Regresión: reenviar el mismo documento no debe crear una fila nueva
    (el INSERT duplicado violaba uq_user_identifications_type_number)."""
    from app.modules.users.application.use_cases.user_use_cases import _apply_identifications

    user = User()
    original = UserIdentification(document_type="dni", document_number="71389479", is_primary=True, position=0)
    user.identifications = [original]

    cmd = UserUpdateCmd(id=uuid4(), identifications=[
        {"document_type": "dni", "document_number": "71389479", "is_primary": True},
        {"document_type": "cpf", "document_number": "13002863343", "is_primary": False},
    ])
    _apply_identifications(user, cmd.identifications)

    assert user.identifications[0] is original
    assert [(i.document_type, i.document_number) for i in user.identifications] == [
        ("dni", "71389479"),
        ("cpf", "13002863343"),
    ]
    assert [i.position for i in user.identifications] == [0, 1]


def test_apply_identifications_removes_absent_rows():
    from app.modules.users.application.use_cases.user_use_cases import _apply_identifications

    user = User()
    keep = UserIdentification(document_type="dni", document_number="71389479", is_primary=False, position=0)
    drop = UserIdentification(document_type="cpf", document_number="13002863343", is_primary=True, position=1)
    user.identifications = [keep, drop]

    cmd = UserUpdateCmd(id=uuid4(), identifications=[
        {"document_type": "dni", "document_number": "71389479", "is_primary": True},
    ])
    _apply_identifications(user, cmd.identifications)

    assert user.identifications == [keep]
    assert keep.is_primary is True
