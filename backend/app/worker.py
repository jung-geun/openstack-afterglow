"""Afterglow 헬스체크 워커 — 별도 파드로 실행.

사용법:
  uv run python -m app.worker

K3s ACTIVE 클러스터를 3분 간격으로 프로빙하여 Redis에 헬스 결과 저장.
메인 API(app.main)는 이 결과를 Redis에서 읽어 제공.
"""

import asyncio
import logging
import os

# 로깅 설정 (JSON 포맷)
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

_logger = logging.getLogger("afterglow.worker")

_CHECK_INTERVAL = int(os.environ.get("K3S_HEALTH_INTERVAL", "180"))  # 기본 3분


async def _run_health_check() -> None:
    """K3s 헬스체크 1회 실행."""
    from app.services import k3s_health

    await k3s_health.check_all_active_clusters()


async def main() -> None:
    _logger.info("Afterglow 헬스체크 워커 시작 (interval=%ds)", _CHECK_INTERVAL)
    await asyncio.sleep(30)  # 초기 대기: 메인 API 및 DB 준비 시간

    while True:
        try:
            await _run_health_check()
        except Exception:
            _logger.exception("헬스체크 루프 오류")
        await asyncio.sleep(_CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
