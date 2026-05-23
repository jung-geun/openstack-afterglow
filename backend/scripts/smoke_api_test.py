"""Phase 1 — _smoke-mount-heat / _smoke-mount-tofu 실제 API 호출 테스트.

실행:
    cd backend
    uv run python scripts/smoke_api_test.py [--proto NFS|CEPHFS] [--tool heat|tofu|both]

백엔드(localhost:8000)가 실행 중이어야 한다.
config.toml의 admin credentials 로 Keystone 토큰을 발급해 사용한다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx

BASE_URL = "http://localhost:8000"


def get_admin_token() -> str:
    """config.toml 의 admin credentials 로 Keystone 토큰을 발급한다."""
    from app.config import get_settings

    settings = get_settings()
    # admin 프로젝트 스코프 연결 (require_admin 통과용)
    # os_service_project_id 대신 admin 프로젝트를 사용
    import openstack

    conn = openstack.connect(
        auth_url=settings.os_auth_url,
        username=settings.os_username,
        password=settings.os_password,
        project_name=settings.os_project_name,
        user_domain_name=settings.os_user_domain_name,
        project_domain_name=settings.os_project_domain_name,
        region_name=settings.os_region_name,
    )
    token = conn.auth_token
    if not token:
        raise RuntimeError("Keystone 토큰 발급 실패")
    print(f"  토큰 발급 완료 (앞 20자): {token[:20]}...")
    return token


def call_smoke(token: str, tool: str, proto: str, size_gb: int = 1) -> dict:
    """smoke-mount-{tool} 엔드포인트를 호출하고 결과를 반환한다."""
    endpoint = f"{BASE_URL}/api/admin/libraries/builder-vm/_smoke-mount-{tool}"
    payload = {"share_proto": proto, "size_gb": size_gb}
    print(f"\n  POST {endpoint}")
    print(f"  payload: {json.dumps(payload)}")

    start = time.monotonic()
    resp = httpx.post(
        endpoint,
        json=payload,
        headers={"X-Auth-Token": token},
        timeout=900,  # VM 생성 + cloud-init 최대 15분
    )
    elapsed = time.monotonic() - start

    print(f"  응답: HTTP {resp.status_code} ({elapsed:.1f}s)")
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return {"status_code": resp.status_code, "elapsed": elapsed, "body": body}


def print_result(tool: str, result: dict) -> None:
    code = result["status_code"]
    body = result["body"]
    elapsed = result["elapsed"]
    mark = "✓" if code == 200 else "✗"
    print(f"\n── {mark}  [{tool.upper()}] HTTP {code}  ({elapsed:.1f}s) ──────────────")
    print(json.dumps(body, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="smoke-mount API 실제 호출 테스트")
    parser.add_argument("--proto", default="NFS", choices=["NFS", "CEPHFS"])
    parser.add_argument("--tool", default="both", choices=["heat", "tofu", "both"])
    parser.add_argument("--size-gb", type=int, default=1)
    args = parser.parse_args()

    print("Afterglow Phase 1 — smoke-mount API 테스트")
    print("=" * 60)

    print("\n[1] 관리자 토큰 발급 중...")
    try:
        token = get_admin_token()
    except Exception as e:
        print(f"ERROR: 토큰 발급 실패: {e}")
        sys.exit(1)

    tools = ["heat", "tofu"] if args.tool == "both" else [args.tool]
    results = {}

    for tool in tools:
        print(f"\n[2] {tool.upper()} smoke-mount 호출 (proto={args.proto})...")
        try:
            results[tool] = call_smoke(token, tool, args.proto, args.size_gb)
        except Exception as e:
            results[tool] = {"status_code": -1, "elapsed": 0, "body": {"error": str(e)}}

    print("\n\n" + "=" * 60)
    print("── 결과 요약 ──────────────────────────────────────────────────")
    for tool, result in results.items():
        print_result(tool, result)

    if len(results) == 2:
        heat_ok = results.get("heat", {}).get("status_code") == 200
        tofu_ok = results.get("tofu", {}).get("status_code") == 200
        print("\n── 비교 ────────────────────────────────────────────────────")
        print(f"  Heat : {'성공' if heat_ok else '실패'}")
        print(f"  Tofu : {'성공' if tofu_ok else '실패'}")
        if heat_ok and tofu_ok:
            h_time = results["heat"]["elapsed"]
            t_time = results["tofu"]["elapsed"]
            faster = "Heat" if h_time < t_time else "OpenTofu"
            print(f"  속도 : Heat {h_time:.1f}s / Tofu {t_time:.1f}s → {faster} 빠름")

    print()


if __name__ == "__main__":
    main()
