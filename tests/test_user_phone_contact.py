from typing import Annotated, Optional
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, UploadFile
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.modules.users.adapters.router.user_routes import _parse_user_update_form
from app.modules.users.application.schemas.user_schema import (
    UpdateCurrentUserCmd,
    UserCreateCmd,
    UserUpdateCmd,
)


@pytest.mark.parametrize("schema", [UserCreateCmd, UserUpdateCmd, UpdateCurrentUserCmd])
@pytest.mark.parametrize("value,expected", [
    (None, None), ("", None), ("   ", None),
    ("@ana.perez", "@ana.perez"), ("  @ana.perez  ", "@ana.perez"),
    ("00999888777", "00999888777"), (999888777, "999888777"),
])
def test_phone_contact_preserves_text_and_accepts_legacy_numbers(schema, value, expected):
    fields = {"phone": value}
    if schema is UserUpdateCmd:
        fields["id"] = uuid4()
    assert schema(**fields).phone == expected


@pytest.mark.parametrize("schema", [UserCreateCmd, UserUpdateCmd, UpdateCurrentUserCmd])
def test_phone_contact_rejects_more_than_column_capacity(schema):
    fields = {"phone": "@" + "a" * 100}
    if schema is UserUpdateCmd:
        fields["id"] = uuid4()
    with pytest.raises(ValidationError):
        schema(**fields)


@pytest.mark.parametrize("contact,expected,present", [
    (None, None, False), ("", None, True),
    ("@ana.perez", "@ana.perez", True), ("00999888777", "00999888777", True),
])
def test_multipart_update_distinguishes_omitting_contact_from_clearing(contact, expected, present):
    app = FastAPI()

    @app.put("/contact")
    async def update_contact(
        form_data: Annotated[
            tuple[UserUpdateCmd, Optional[UploadFile]], Depends(_parse_user_update_form)
        ],
    ):
        cmd, _ = form_data
        return {"phone": cmd.phone, "present": "phone" in cmd.model_fields_set}

    data = {"id": str(uuid4())}
    if contact is not None:
        data["phone"] = contact
    with TestClient(app) as client:
        response = client.put("/contact", data=data)
    assert response.status_code == 200
    assert response.json() == {"phone": expected, "present": present}
