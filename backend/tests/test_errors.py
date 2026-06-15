"""openstack_error_to_http: 5xx 내부 정보 노출 차단 검증 (CLAUDE.md §6)."""

from __future__ import annotations

from openstack.exceptions import ConflictException, HttpException, NotFoundException

from app.api.common.errors import openstack_error_to_http

_INTERNAL = "https://keystone.internal.svc:5000/v3 returned 503 — backend pool exhausted"


def test_5xx_hides_internal_detail_from_non_admin():
    """5xx 는 일반 사용자에게 내부 URL/메시지를 노출하지 않고 일반 메시지로 치환."""
    exc = HttpException(message=_INTERNAL, http_status=503)
    result = openstack_error_to_http(exc, is_admin=False)
    assert result.status_code == 503
    assert result.detail == "작업 실패"
    assert "keystone.internal" not in str(result.detail)


def test_5xx_shows_detail_to_admin():
    """관리자에게는 운영 디버깅을 위해 원본 메시지를 그대로 전달."""
    exc = HttpException(message=_INTERNAL, http_status=503)
    result = openstack_error_to_http(exc, is_admin=True)
    assert result.status_code == 503
    assert "keystone.internal" in str(result.detail)


def test_4xx_preserves_detail():
    """4xx 는 사용자에게 유의미하므로 원본 메시지 유지."""
    exc = HttpException(message="invalid parameter 'foo'", http_status=400)
    result = openstack_error_to_http(exc, is_admin=False)
    assert result.status_code == 400
    assert "invalid parameter" in str(result.detail)


def test_not_found_maps_to_generic_404():
    result = openstack_error_to_http(NotFoundException(), is_admin=False)
    assert result.status_code == 404
    assert result.detail == "리소스를 찾을 수 없습니다"


def test_conflict_maps_to_generic_409():
    result = openstack_error_to_http(ConflictException(), is_admin=False)
    assert result.status_code == 409


def test_unknown_exception_maps_to_generic_500():
    result = openstack_error_to_http(RuntimeError("boom"), is_admin=False)
    assert result.status_code == 500
    assert result.detail == "작업 실패"
    assert "boom" not in str(result.detail)
