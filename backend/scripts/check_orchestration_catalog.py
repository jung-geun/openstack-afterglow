"""Phase 0 — Heat 오케스트레이션 카탈로그 및 Manila 리소스 타입 가용성 확인.

실행:
    cd backend
    uv run python scripts/check_orchestration_catalog.py
"""

from __future__ import annotations

import sys

MANILA_RESOURCE_TYPES = [
    "OS::Manila::Share",
    "OS::Manila::ShareAccessRule",
    "OS::Manila::ShareType",
    "OS::Manila::ShareNetwork",
]


def check_heat_catalog(conn) -> bool:
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
            print(f"  ?  예상치 못한 오류: {e}")
        return False


def check_manila_resource_types(conn) -> dict[str, bool]:
    print("\n── Manila Heat 리소스 타입 확인 ────────────────────────────────")
    result: dict[str, bool] = {}
    try:
        # openstacksdk 3.x: orchestration proxy 에 resource_types() 없음 → proxy.get() 사용
        resp = conn.orchestration.get("/resource_types")
        data = resp.json() if callable(resp.json) else {}
        available = set(data.get("resource_types", []))
        for rt in MANILA_RESOURCE_TYPES:
            supported = rt in available
            result[rt] = supported
            mark = "✓" if supported else "✗"
            print(f"  {mark}  {rt}")
    except Exception as e:
        print(f"  ERROR: resource_types 조회 실패: {e}")
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
        print("  → Heat 활성. Share는 HOT으로 가능, ShareAccessRule은 Python 위임.")
    else:
        print("  → Heat 활성이지만 Manila 리소스 타입 미지원. HOT은 Nova server + FIP만.")


def main() -> None:
    print("Afterglow Phase 0 — 오케스트레이션 카탈로그 검증")
    print("=" * 60)

    try:
        from app.services.keystone import get_service_project_connection

        conn = get_service_project_connection()
        print(f"  연결: {conn.auth.get('auth_url', '?')} (service project)")
    except Exception as e:
        print(f"ERROR: OpenStack 연결 실패: {e}")
        sys.exit(1)

    heat_ok = check_heat_catalog(conn)
    manila_types: dict[str, bool] = {}
    if heat_ok:
        manila_types = check_manila_resource_types(conn)

    print_summary(heat_ok, manila_types)
    print()


if __name__ == "__main__":
    main()
