"""Prometheus query_range 클라이언트 (httpx 직접 호출)."""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

_logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        s = get_settings()
        auth: tuple[str, str] | None = None
        if s.prometheus_username and s.prometheus_password:
            auth = (s.prometheus_username, s.prometheus_password)
        _client = httpx.AsyncClient(
            timeout=15,
            auth=auth,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def aclose_client() -> None:
    """lifespan 종료 시 호출 — keep-alive 연결을 정상 종료한다."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


class PromUnavailable(Exception):
    """Prometheus 서버에 연결할 수 없거나 5xx 응답."""


class PromBadQuery(Exception):
    """PromQL 쿼리 문법 오류 (4xx)."""


async def query_range(
    expr: str,
    *,
    start_ts: int,
    end_ts: int,
    step_s: int,
) -> list[dict]:
    """Prometheus /api/v1/query_range 호출 → [{"ts": int, "value": float}].

    결과가 없으면 빈 리스트 반환.
    첫 번째 시계열만 반환 (단일 인스턴스 매칭 가정).
    """
    settings = get_settings()
    url = f"{settings.prometheus_base_url.rstrip('/')}/api/v1/query_range"
    params = {
        "query": expr,
        "start": start_ts,
        "end": end_ts,
        "step": f"{step_s}s",
    }
    try:
        resp = await _get_client().get(url, params=params)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise PromUnavailable(f"Prometheus 연결 실패: {exc}") from exc

    if resp.status_code >= 500:
        raise PromUnavailable(f"Prometheus {resp.status_code}: {resp.text[:200]}")
    if resp.status_code >= 400:
        raise PromBadQuery(f"PromQL 오류 {resp.status_code}: {resp.text[:200]}")

    body = resp.json()
    results = body.get("data", {}).get("result", [])
    if not results:
        return []

    return [{"ts": int(float(ts)), "value": float(val)} for ts, val in results[0].get("values", [])]


def calc_step(range_seconds: int) -> int:
    """range에 맞는 scrape step 계산 (최소 15초, 최대 100 포인트)."""
    return max(15, range_seconds // 100)


async def query_instant_multi(promql: str) -> list[tuple[dict[str, str], float]]:
    """Prometheus /api/v1/query — 다중 시계열의 (labels, value) 리스트 반환.

    토폴로지 트래픽처럼 모든 인스턴스의 instant 값을 한 번에 받을 때 사용.
    """
    settings = get_settings()
    url = f"{settings.prometheus_base_url.rstrip('/')}/api/v1/query"
    try:
        resp = await _get_client().get(url, params={"query": promql})
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise PromUnavailable(f"Prometheus 연결 실패: {exc}") from exc

    if resp.status_code >= 500:
        raise PromUnavailable(f"Prometheus {resp.status_code}: {resp.text[:200]}")
    if resp.status_code >= 400:
        raise PromBadQuery(f"PromQL 오류 {resp.status_code}: {resp.text[:200]}")

    body = resp.json()
    if body.get("status") != "success":
        raise PromBadQuery(body.get("error", "unknown"))

    out: list[tuple[dict[str, str], float]] = []
    for r in body.get("data", {}).get("result", []):
        try:
            out.append((dict(r["metric"]), float(r["value"][1])))
        except (KeyError, ValueError, TypeError):
            continue
    return out
