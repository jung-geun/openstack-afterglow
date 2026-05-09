"""prom_query — httpx 클라이언트 풀 재사용 단위 테스트."""

import httpx
import pytest

from app.services import prom_query


@pytest.fixture(autouse=True)
def reset_client():
    """각 테스트 전후 클라이언트 상태를 초기화한다."""
    prom_query._client = None
    yield
    prom_query._client = None


def test_get_client_returns_instance():
    """_get_client() 가 httpx.AsyncClient 를 반환해야 한다."""
    client = prom_query._get_client()
    assert isinstance(client, httpx.AsyncClient)


def test_get_client_reuses_instance():
    """_get_client() 를 두 번 호출하면 동일 객체를 반환해야 한다."""
    c1 = prom_query._get_client()
    c2 = prom_query._get_client()
    assert c1 is c2


@pytest.mark.anyio
async def test_aclose_client_resets():
    """aclose_client() 후 _get_client() 는 새 객체를 반환해야 한다."""
    c1 = prom_query._get_client()
    await prom_query.aclose_client()
    c2 = prom_query._get_client()
    assert c1 is not c2
    assert c1.is_closed


@pytest.mark.anyio
async def test_aclose_client_idempotent():
    """_client 가 None 이어도 aclose_client() 가 예외 없이 실행되어야 한다."""
    prom_query._client = None
    await prom_query.aclose_client()  # should not raise
