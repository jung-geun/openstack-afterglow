"""librechat_mongo.get_usage_for_username 쿼리 구성 단위 테스트.

usage.py 테스트(test_chat_usage.py)는 이 함수를 통째로 모킹하므로, 실제 정규식
구성/조인 로직은 여기서 fake Motor 컬렉션으로 end-to-end 검증한다. 핵심 회귀 대상:
username에 정규식 메타문자(특히 `.`)가 섞여도 다른 사용자와 매칭되지 않아야 한다.
"""

import re

import pytest

from app.services import librechat_mongo


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, length=None):
        return self._rows[:length] if length is not None else list(self._rows)


class _FakeUsersCollection:
    def __init__(self, docs):
        self._docs = docs

    async def find_one(self, filter_):
        pattern = filter_["username"]["$regex"]
        flags = re.IGNORECASE if filter_["username"].get("$options") == "i" else 0
        for doc in self._docs:
            if re.fullmatch(pattern, doc["username"], flags):
                return doc
        return None


class _FakeTransactionsCollection:
    def __init__(self, rows_by_user):
        self._rows_by_user = rows_by_user

    def aggregate(self, pipeline):
        user_id = pipeline[0]["$match"]["user"]
        rows = self._rows_by_user.get(user_id, [])
        if not rows:
            return _FakeCursor([])
        total_raw = sum(r["rawAmount"] for r in rows)
        total_value = sum(r["tokenValue"] for r in rows)
        return _FakeCursor(
            [{"total_raw_amount": total_raw, "total_token_value": total_value, "transaction_count": len(rows)}]
        )


class _FakeDb:
    def __init__(self, users_docs, tx_by_user):
        self._collections = {
            "users": _FakeUsersCollection(users_docs),
            "transactions": _FakeTransactionsCollection(tx_by_user),
        }

    def __getitem__(self, name):
        return self._collections[name]


class _FakeClient:
    def __init__(self, db):
        self._db = db

    def get_default_database(self):
        return self._db


@pytest.fixture(autouse=True)
def _reset_client_cache():
    librechat_mongo._client = None
    yield
    librechat_mongo._client = None


@pytest.mark.asyncio
async def test_get_usage_for_username_matches_exact_user(monkeypatch):
    fake_db = _FakeDb(
        users_docs=[{"_id": "u1", "username": "alice"}],
        tx_by_user={"u1": [{"rawAmount": -100.0, "tokenValue": -50.0}, {"rawAmount": -20.0, "tokenValue": -10.0}]},
    )
    monkeypatch.setattr(librechat_mongo, "_get_client", lambda: _FakeClient(fake_db))

    result = await librechat_mongo.get_usage_for_username("alice")

    assert result == {"total_raw_amount": -120.0, "total_token_value": -60.0, "transaction_count": 2}


@pytest.mark.asyncio
async def test_get_usage_for_username_regex_metachar_does_not_match_other_user(monkeypatch):
    """username='a.b' 는 정규식 메타문자를 escape 없이 쓰면 'axb'와도 매칭된다.

    escape가 적용되면 'a.b' 사용자를 찾지 못해(DB에 없으므로) None을 반환해야 한다 —
    'axb' 사용자의 사용량이 새어나가면 안 된다(회귀 시 이 테스트가 실패해야 함).
    """
    fake_db = _FakeDb(
        users_docs=[{"_id": "u-other", "username": "axb"}],
        tx_by_user={"u-other": [{"rawAmount": -9999.0, "tokenValue": -9999.0}]},
    )
    monkeypatch.setattr(librechat_mongo, "_get_client", lambda: _FakeClient(fake_db))

    result = await librechat_mongo.get_usage_for_username("a.b")

    assert result is None


@pytest.mark.asyncio
async def test_get_usage_for_username_case_insensitive(monkeypatch):
    fake_db = _FakeDb(
        users_docs=[{"_id": "u1", "username": "Alice"}],
        tx_by_user={"u1": [{"rawAmount": -5.0, "tokenValue": -1.0}]},
    )
    monkeypatch.setattr(librechat_mongo, "_get_client", lambda: _FakeClient(fake_db))

    result = await librechat_mongo.get_usage_for_username("alice")

    assert result == {"total_raw_amount": -5.0, "total_token_value": -1.0, "transaction_count": 1}


@pytest.mark.asyncio
async def test_get_usage_for_username_no_user_found(monkeypatch):
    fake_db = _FakeDb(users_docs=[], tx_by_user={})
    monkeypatch.setattr(librechat_mongo, "_get_client", lambda: _FakeClient(fake_db))

    result = await librechat_mongo.get_usage_for_username("nobody")

    assert result is None


@pytest.mark.asyncio
async def test_get_usage_for_username_no_mongo_configured(monkeypatch):
    monkeypatch.setattr(librechat_mongo, "_get_client", lambda: None)

    result = await librechat_mongo.get_usage_for_username("alice")

    assert result is None


@pytest.mark.asyncio
async def test_get_usage_for_username_zero_transactions_for_found_user(monkeypatch):
    fake_db = _FakeDb(users_docs=[{"_id": "u1", "username": "alice"}], tx_by_user={})
    monkeypatch.setattr(librechat_mongo, "_get_client", lambda: _FakeClient(fake_db))

    result = await librechat_mongo.get_usage_for_username("alice")

    assert result == {"total_raw_amount": 0.0, "total_token_value": 0.0, "transaction_count": 0}
