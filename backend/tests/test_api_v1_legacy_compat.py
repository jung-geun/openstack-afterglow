"""레거시 /api 호환 회귀 테스트.

cloud-init에 baked된 VM이 재배포 없이 계속 동작하도록 3종 경로가
레거시 /api 와 /api/v1 양쪽에 마운트되어 있음을 고정한다.

baked 엔드포인트 (재bake 불가):
- POST /api/k3s/callback          — k3s_callback_router (k3s_server*.j2)
- POST /api/instances/{id}/health/report  — instance_health_router (health_check.sh.j2)
- POST /api/instances/{id}/credentials/rotate-cephx — instance_health_router (envmgr_rotate_key.sh.j2)

이 테스트가 실패한다면 레거시 dual-mount가 제거된 것이므로
기존 VM에서 해당 엔드포인트가 404로 깨진다.
"""

from fastapi.routing import APIRoute

from app.main import app


def _routes_by_path() -> dict[str, set[str]]:
    """path → set of HTTP methods"""
    result: dict[str, set[str]] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            result.setdefault(route.path, set()).update(route.methods or set())
    return result


BAKED_LEGACY_PATHS = [
    # (path_template, required_method)
    ("/api/k3s/callback", "POST"),
    ("/api/instances/{instance_id}/health/report", "POST"),
    ("/api/instances/{instance_id}/credentials/rotate-cephx", "POST"),
]

V1_PATHS = [
    ("/api/v1/k3s/callback", "POST"),
    ("/api/v1/instances/{instance_id}/health/report", "POST"),
    ("/api/v1/instances/{instance_id}/credentials/rotate-cephx", "POST"),
]


def test_legacy_baked_routes_exist():
    """3종 baked 경로가 레거시 /api 에 존재해야 한다 (404 아님)."""
    routes = _routes_by_path()
    for path, method in BAKED_LEGACY_PATHS:
        assert path in routes, (
            f"레거시 baked 경로 {path!r} 가 app.routes에서 사라졌습니다. "
            "instance_health_router / k3s_callback_router 의 레거시 dual-mount를 복원하세요."
        )
        assert method in routes[path], f"레거시 baked 경로 {path!r} 에 {method} 메서드가 없습니다."


def test_v1_baked_routes_also_exist():
    """동일 3종이 /api/v1 에도 존재해야 한다."""
    routes = _routes_by_path()
    for path, method in V1_PATHS:
        assert path in routes, f"v1 경로 {path!r} 가 app.routes에서 사라졌습니다."
        assert method in routes[path], f"v1 경로 {path!r} 에 {method} 메서드가 없습니다."


def test_legacy_routes_not_in_openapi_schema():
    """/api (v1 아님) 레거시 경로는 OpenAPI 스키마에서 숨겨져야 한다."""
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        # /api/v1/... 는 허용, /api/v1 이 아닌 /api/... 는 include_in_schema=False 여야 함
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            assert not route.include_in_schema, (
                f"레거시 경로 {path!r} 가 OpenAPI 스키마에 노출되어 있습니다. include_in_schema=False 를 설정하세요."
            )
