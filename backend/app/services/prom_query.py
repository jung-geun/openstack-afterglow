"""Prometheus query_range 클라이언트 (httpx 직접 호출)."""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

_logger = logging.getLogger(__name__)


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
    auth = None
    if settings.prometheus_username and settings.prometheus_password:
        auth = (settings.prometheus_username, settings.prometheus_password)
    try:
        async with httpx.AsyncClient(timeout=15, auth=auth) as client:
            resp = await client.get(url, params=params)
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
    """range에 맞는 scrape step 계산 (최소 15초)."""
    return max(15, range_seconds // 200)
