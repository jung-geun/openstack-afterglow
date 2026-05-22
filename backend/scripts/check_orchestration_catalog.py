"""Phase 0 — Heat 오케스트레이션 카탈로그 및 Manila 리소스 타입 가용성 확인.

실행:
    cd backend
    uv run python scripts/check_orchestration_catalog.py

OS_* 환경변수 또는 clouds.yaml 기반 인증을 사용한다.
"""
from __future__ import annotations

import sys

try:
    import openstack
except ImportError:
    print("ERROR: openstacksdk 가 설치되지 않았습니다. `uv run python ...` 으로 실행하세요.")
    sys.exit(1)


MANILA_RESOURCE_TYPES = [
    "OS::Manila::Share",
    "OS::Manila::ShareAccessRule",
    "OS::Manila::ShareType",
    "OS::Manila::ShareNetwork",
]


def check_heat_catalog(conn) -> bool:
    """Heat(orchestration) 서비스 카탈로그 활성화 여부 확인."""
    print("\n── Heat 카탈로그 확인 ──────────────────────────────────────────")
    try:
        list(conn.orchestration.stacks(limit=1))
        print("  ✓  orchestration endpoint 접근 성공 — Heat 활성화됨")
        return True
    except Exception as e:
        err = str(e).lower()
        if "endpoint" in err or "not found" in err or "404" in err or "503" in err:
            print(f"  ✗  Heat 서비스 미활성 또는 카탈로그 없음: {e}")
        else:
            print(f"  ?  예상치 못한 오류 (카탈로그 활성화 여부 불명): {e}")
        return False


def check_manila_resource_types(conn) -> dict[str, bool]:
    """Heat에서 Manila 리소스 타입 지원 여부 확인."""
    print("\n── Manila Heat 리소스 타입 확인 ────────────────────────────────")
    result: dict[str, bool] = {}
    try:
        available = {rt.resource_type for rt in conn.orchestration.resource_types()}
        for rt in MANILA_RESOURCE_TYPES:
            supported = rt in available
            result[rt] = supported
            mark = "✓" if supported else "✗"
            print(f"  {mark}  {rt}")
    except Exception as e:
        print(f"  ERROR: resource_types() 조회 실패: {e}")
        for rt in MANILA_RESOURCE_TYPES:
            result[rt] = False
    return result


def print_summary(heat_ok: bool, manila_types: dict[str, bool]) -> None:
    print("\n── 결론 ────────────────────────────────────────────────────────")
    if not heat_ok:
        print("  → Heat 미활성. Phase 1은 OpenTofu 단독으로 진행.")
        return

    share_ok = manila_types.get("OS::Manila::Share", False)
    access_ok = manila_types.get("OS::Manila::ShareAccessRule", False)

    if share_ok and access_ok:
        print("  → Heat 활성 + Manila 리소스 타입 지원. Heat PoC 전체 가능.")
    elif share_ok:
        print("  → Heat 활성. Share는 HOT으로 가능, ShareAccessRule은 Python 위임 필요.")
    else:
        print("  → Heat 활성이지만 Manila 리소스 타입 미지원.")
        print("     HOT은 Nova server + FIP만 처리, Manila 전체 Python 위임.")


def main() -> None:
    print("Afterglow Phase 0 — 오케스트레이션 카탈로그 검증")
    print("=" * 60)

    try:
        conn = openstack.connect()
    except Exception as e:
        print(f"ERROR: OpenStack 연결 실패: {e}")
        print("OS_AUTH_URL, OS_USERNAME 등 환경변수 또는 clouds.yaml을 설정하세요.")
        sys.exit(1)

    heat_ok = check_heat_catalog(conn)

    manila_types: dict[str, bool] = {}
    if heat_ok:
        manila_types = check_manila_resource_types(conn)

    print_summary(heat_ok, manila_types)
    print()


if __name__ == "__main__":
    main()
