from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.modules.notifications.routes import read_one, create_notice, NoticeCreate
from app.modules.notifications.service import validate_recipients


def mock_db(value=None, rows=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalars.return_value.all.return_value = rows or []
    return SimpleNamespace(execute=AsyncMock(return_value=result), commit=AsyncMock(), add=MagicMock())


async def test_read_is_scoped_to_recipient():
    db = mock_db()
    owner, notice = uuid4(), uuid4()
    with pytest.raises(HTTPException) as exc:
        await read_one(notice, {'user_id': str(owner)}, db, [])
    assert exc.value.status_code == 404
    query = db.execute.call_args.args[0]
    assert 'recipient_user_id' in str(query)
    assert owner in query.compile().params.values()
    db.commit.assert_not_awaited()


async def test_read_is_idempotent():
    timestamp = datetime.now(timezone.utc)
    row = SimpleNamespace(read_at=timestamp)
    db = mock_db(row)
    await read_one(uuid4(), {'user_id': str(uuid4())}, db, [])
    assert row.read_at == timestamp
    db.commit.assert_not_awaited()


async def test_invalid_recipient_rejected_before_notice_write():
    cmd = NoticeCreate(title='Aviso', body='Mensaje', recipient_user_ids=[uuid4()])
    db = mock_db()
    with pytest.raises(HTTPException) as exc:
        await create_notice(cmd, {'user_id': str(uuid4())}, db, [])
    assert exc.value.status_code == 400
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


async def test_duplicate_recipients_create_one_notice():
    uid = uuid4()
    db = mock_db(rows=[uid])
    cmd = NoticeCreate(title='Aviso', body='Mensaje', recipient_user_ids=[uid, uid])
    assert await create_notice(cmd, {'user_id': str(uuid4())}, db, []) == {'created': 1}
    assert db.add.call_count == 1
    query = db.execute.call_args.args[0]
    assert 'client' not in str(query.compile().params)


async def test_empty_mentions_do_not_query_staff():
    db = mock_db()
    assert await validate_recipients(db, []) == []
    db.execute.assert_not_awaited()


def test_transaction_json_preserves_observations_and_mention_ids(client, valid_transaction_payload, mock_create_transaction_uc):
    uid = str(uuid4())
    payload = {**valid_transaction_payload, 'observaciones': 'Revisar con @Ana Pérez', 'mentioned_user_ids': [uid]}
    response = client.post('/transactions', json=payload)
    assert response.status_code == 201
    cmd = mock_create_transaction_uc.execute.call_args.args[0]
    assert cmd.observaciones == payload['observaciones']
    assert list(map(str, cmd.mentioned_user_ids)) == [uid]


def test_transaction_multipart_preserves_observations_and_mention_ids(client, valid_transaction_payload, mock_create_transaction_uc):
    import json
    uid = str(uuid4())
    payload = {**valid_transaction_payload, 'observaciones': 'Revisar con @Ana Pérez', 'mentioned_user_ids': json.dumps([uid])}
    response = client.post('/transactions', data=payload)
    assert response.status_code == 201
    cmd = mock_create_transaction_uc.execute.call_args.args[0]
    assert cmd.observaciones == payload['observaciones']
    assert list(map(str, cmd.mentioned_user_ids)) == [uid]
