"""엔드포인트 카탈로그 회귀 방지 테스트.

FastAPI app.routes를 순회해:
1. /api/admin/ 경로에 require_admin 의존성이 반드시 있는지 검증
2. 인증 없이 접근 가능한 Public 엔드포인트가 예상 목록을 벗어나지 않는지 검증
3. 전체 라우트 수가 기준값 이상인지 감시 (라우트 대규모 삭제 감지)

이 테스트가 실패하면:
- 신규 admin 엔드포인트에 require_admin 누락 → 보안 이슈
- 예상 밖 Public 엔드포인트 추가 → 인증 누락 가능성
"""
import pytest
from fastapi.routing import APIRoute

from app.main import app
from app.api.deps import require_admin, get_token_info, get_os_conn


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _iter_api_routes():
    """app.routes 에서 /api/ 경로 APIRoute만 순회."""
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/"):
            yield route


def _get_route_dep_callables(route: APIRoute) -> set:
    """route.dependencies (decorator 레벨) 의 callable 집합 반환."""
    result = set()
    for dep in (route.dependencies or []):
        if hasattr(dep, "dependency"):
            result.add(dep.dependency)
    return result


def _has_any_auth_dep(route: APIRoute) -> bool:
    """route 에 어떤 형태로든 의존성이 있으면 True (= public 이 아님).

    두 가지 경로를 확인:
    1. decorator 레벨 dependencies=[Depends(...)]: route.dependencies 가 비어 있지 않음
    2. 핸들러 함수 파라미터에 Depends 기본값이 하나라도 존재

    이 휴리스틱으로 requirements=[Depends(require_admin)], Depends(get_os_conn),
    Depends(_require_admin) 등 모든 패턴을 감지한다.
    """
    # 1) decorator 레벨 dependencies
    if route.dependencies:
        return True

    # 2) 핸들러 파라미터 Depends
    import inspect
    from fastapi.params import Depends as _DependsClass
    if route.endpoint:
        try:
            sig = inspect.signature(route.endpoint)
            for param in sig.parameters.values():
                if isinstance(param.default, _DependsClass):
                    return True
        except (ValueError, TypeError):
            pass

    return False


# ---------------------------------------------------------------------------
# 공개 엔드포인트 스냅샷
# 이 목록 이외의 인증 없는 엔드포인트가 생기면 테스트가 실패한다.
# 조건부 서비스(k3s)의 라우트는 app에 없을 수 있으므로 optional 처리.
# ---------------------------------------------------------------------------

EXPECTED_PUBLIC = frozenset({
    ("GET",  "/api/health"),
    ("GET",  "/api/site-config"),
    ("GET",  "/api/dashboard/config"),   # 새로고침 간격 등 UI 설정만 반환, 인증 불필요
    ("GET",  "/api/auth/gitlab/enabled"),
    ("GET",  "/api/auth/gitlab/authorize"),
    ("POST", "/api/auth/gitlab/callback"),
    ("POST", "/api/auth/login"),
    # k3s 활성 시에만 등록되는 라우트
    ("POST", "/api/k3s/callback"),
})


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------

def test_admin_prefix_routes_have_require_admin():
    """/api/admin/ 경로 라우트 전체가 require_admin 의존성을 가져야 한다."""
    violations = []
    for route in _iter_api_routes():
        if not route.path.startswith("/api/admin/"):
            continue
        dep_callables = _get_route_dep_callables(route)
        if require_admin not in dep_callables:
            methods = ",".join(sorted(route.methods or []))
            violations.append(f"  {methods} {route.path} — require_admin 누락")

    assert not violations, (
        "다음 /api/admin/ 엔드포인트에 require_admin 의존성이 없습니다:\n"
        + "\n".join(violations)
    )


def test_no_unexpected_public_routes():
    """인증 없이 접근 가능한 엔드포인트가 EXPECTED_PUBLIC 스냅샷을 벗어나지 않아야 한다."""
    unexpected = []
    for route in _iter_api_routes():
        if _has_any_auth_dep(route):
            continue
        for method in (route.methods or []):
            key = (method, route.path)
            if key not in EXPECTED_PUBLIC:
                unexpected.append(f"  {method} {route.path}")

    assert not unexpected, (
        "인증 없이 접근 가능한 예상 외 엔드포인트가 감지되었습니다:\n"
        + "\n".join(unexpected)
        + "\n\n의도적으로 public으로 만든 경우 EXPECTED_PUBLIC 에 추가하세요."
    )


def test_minimum_route_count():
    """전체 /api/ 라우트 수가 기준값(200) 이상이어야 한다.

    대규모 라우터 삭제/미등록을 감지하기 위한 간단한 경보. 조건부 서비스 일부가 꺼진
    환경에서도 200개 미만이 되면 구조적 문제가 있는 것으로 판단한다.
    """
    count = sum(
        len(route.methods or [])
        for route in _iter_api_routes()
    )
    assert count >= 200, (
        f"전체 API 엔드포인트(HTTP method × path) 수가 {count}개로 기준값(200)에 미치지 못합니다. "
        "라우터 미등록 또는 대규모 삭제 여부를 확인하세요."
    )


def test_admin_routes_summary(capsys):
    """현재 등록된 /api/admin/ 라우트를 열거 (정보성)."""
    routes = sorted(
        (m, r.path)
        for r in _iter_api_routes()
        if r.path.startswith("/api/admin/")
        for m in (r.methods or [])
    )
    print(f"\n[admin routes total: {len(routes)}]")
    for method, path in routes:
        print(f"  {method:6} {path}")
    # 정보성 테스트 — 항상 통과
    assert len(routes) >= 50, (
        f"admin 라우트가 {len(routes)}개로 예상보다 적습니다. "
        "admin 라우터 등록 여부를 확인하세요."
    )
