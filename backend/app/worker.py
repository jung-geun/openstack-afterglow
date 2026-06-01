"""Drover Health Manager — 별도 파드로 실행.

사용법:
  uv run python -m app.worker

K3s ACTIVE 클러스터를 3분 간격으로 프로빙하여 Redis에 헬스 결과 저장.
Stampede 오토스케일 reconcile을 별도 주기(STAMPEDE_INTERVAL)로 실행.
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

_logger = logging.getLogger("drover.health")

_CHECK_INTERVAL = int(os.environ.get("K3S_HEALTH_INTERVAL", "180"))  # 기본 3분
_STAMPEDE_INTERVAL = int(os.environ.get("STAMPEDE_INTERVAL", "60"))  # 기본 1분


async def _run_health_check() -> None:
    """K3s 헬스체크 1회 실행."""
    from app.services import k3s_health

    await k3s_health.check_all_active_clusters()


async def _run_stampede() -> None:
    """Stampede 오토스케일 reconcile 1회 실행."""
    from app.services import k3s_stampede

    await k3s_stampede.run_all()


async def _health_loop() -> None:
    """헬스체크 루프 (3분 주기)."""
    while True:
        try:
            await _run_health_check()
        except Exception:
            _logger.exception("헬스체크 루프 오류")
        await asyncio.sleep(_CHECK_INTERVAL)


async def _stampede_loop() -> None:
    """Stampede reconcile 루프 (기본 1분 주기)."""
    while True:
        try:
            await _run_stampede()
        except Exception:
            _logger.exception("Stampede reconcile 루프 오류")
        await asyncio.sleep(_STAMPEDE_INTERVAL)


async def main() -> None:
    _logger.info(
        "Drover Health Manager 시작 (health_interval=%ds, stampede_interval=%ds)",
        _CHECK_INTERVAL,
        _STAMPEDE_INTERVAL,
    )

    # DB 초기화 (admin kubeconfig / Stampede 설정 접근에 필요)
    # init_db는 동기 함수 — asyncio.to_thread 불필요, 직접 호출
    try:
        from app.config import get_settings
        from app.database import init_db

        s = get_settings()
        db_url = s.database_url or os.environ.get("DATABASE_URL", "")
        init_db(db_url)  # db_url이 비어있으면 내부에서 Redis 폴백 로그만 출력
        if db_url:
            _logger.info("Drover: DB 초기화 완료")
        else:
            _logger.warning("Drover: DATABASE_URL 미설정 — DB 없이 실행 (Redis 폴백)")
    except Exception:
        _logger.exception("Drover: DB 초기화 실패 — Redis 폴백으로 진행")

    # 초기 대기: 메인 API 및 DB 준비 시간
    await asyncio.sleep(30)

    # 헬스체크 + Stampede reconcile을 병렬로 실행
    await asyncio.gather(
        _health_loop(),
        _stampede_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
