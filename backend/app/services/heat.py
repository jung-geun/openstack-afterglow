"""Heat 오케스트레이션 서비스 — Magnum K8s 클러스터 스택 추적 및 ephemeral 스택 관리."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    import openstack

_logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "heat"


class HeatServiceUnavailable(Exception):
    """Heat 서비스가 배포되지 않았거나 접근할 수 없을 때 발생."""


class HeatStackError(RuntimeError):
    """Heat stack 생성/삭제 중 오류."""


def _get_stack(conn: openstack.connection.Connection, stack_id: str):
    """스택 단건 조회."""
    try:
        return conn.orchestration.get_stack(stack_id)
    except Exception as e:
        err = str(e).lower()
        if "404" in err or "not found" in err or "no such" in err:
            raise HeatServiceUnavailable(f"스택을 찾을 수 없습니다: {stack_id}") from e
        if "endpoint" in err or "connection" in err or "503" in err:
            raise HeatServiceUnavailable(f"Heat 서비스에 접근할 수 없습니다: {e}") from e
        raise


def get_stack_detail(conn: openstack.connection.Connection, stack_id: str) -> dict:
    """스택 상세 정보 반환."""
    try:
        stack = _get_stack(conn, stack_id)
        s = stack.to_dict() if hasattr(stack, "to_dict") else {}
        return {
            "id": stack.id,
            "name": getattr(stack, "name", None) or s.get("stack_name"),
            "status": getattr(stack, "status", None) or s.get("stack_status"),
            "status_reason": getattr(stack, "status_reason", None) or s.get("stack_status_reason"),
            "created_at": str(getattr(stack, "created_at", None) or s.get("creation_time", "")),
            "updated_at": str(getattr(stack, "updated_at", None) or s.get("updated_time", "")),
            "parameters": s.get("parameters", {}),
            "outputs": s.get("outputs", []),
        }
    except HeatServiceUnavailable:
        raise
    except Exception as e:
        raise HeatServiceUnavailable(f"스택 조회 실패: {e}") from e


def list_stack_resources(conn: openstack.connection.Connection, stack_id: str) -> list[dict]:
    """스택 리소스 목록 반환."""
    try:
        _get_stack(conn, stack_id)  # 스택 존재 확인
        resources = []
        for r in conn.orchestration.resources(stack_id):
            resources.append(
                {
                    "resource_name": getattr(r, "resource_name", None) or getattr(r, "name", ""),
                    "resource_type": getattr(r, "resource_type", "") or "",
                    "physical_resource_id": getattr(r, "physical_resource_id", None) or "",
                    "resource_status": getattr(r, "resource_status", "") or getattr(r, "status", ""),
                    "resource_status_reason": getattr(r, "resource_status_reason", None)
                    or getattr(r, "status_reason", ""),
                    "created_at": str(getattr(r, "creation_time", "") or getattr(r, "created_at", "") or ""),
                }
            )
        return resources
    except HeatServiceUnavailable:
        raise
    except Exception as e:
        raise HeatServiceUnavailable(f"리소스 목록 조회 실패: {e}") from e


def list_stack_events(conn: openstack.connection.Connection, stack_id: str) -> list[dict]:
    """스택 이벤트 목록 반환 (최신순)."""
    try:
        _get_stack(conn, stack_id)  # 스택 존재 확인
        events = []
        for e in conn.orchestration.stack_events(stack_id):
            events.append(
                {
                    "resource_name": getattr(e, "resource_name", None) or getattr(e, "logical_resource_id", ""),
                    "resource_status": getattr(e, "resource_status", "") or getattr(e, "status", ""),
                    "resource_status_reason": getattr(e, "resource_status_reason", None) or "",
                    "event_time": str(getattr(e, "event_time", "") or getattr(e, "created_at", "") or ""),
                    "logical_resource_id": getattr(e, "logical_resource_id", None) or "",
                    "physical_resource_id": getattr(e, "physical_resource_id", None) or "",
                }
            )
        # 최신순 정렬
        events.sort(key=lambda x: x["event_time"], reverse=True)
        return events
    except HeatServiceUnavailable:
        raise
    except Exception as e:
        raise HeatServiceUnavailable(f"이벤트 목록 조회 실패: {e}") from e


# ---------------------------------------------------------------------------
# Ephemeral stack 생성 / 대기 / 삭제 (Phase 1 smoke-mount-heat)
# ---------------------------------------------------------------------------


def render_template(template_name: str, variables: dict) -> str:
    """Jinja2 로 Heat HOT 템플릿을 렌더링한다."""
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=False)
    return env.get_template(template_name).render(**variables)


def create_stack(
    conn: openstack.connection.Connection,
    stack_name: str,
    template_str: str,
    parameters: dict,
) -> str:
    """Heat stack 을 생성하고 stack_id 를 반환한다."""
    try:
        stack = conn.orchestration.create_stack(
            name=stack_name,
            template=template_str,
            parameters=parameters,
        )
        _logger.info("[heat] stack 생성 중: %s (%s)", stack_name, stack.id)
        return stack.id
    except Exception as e:
        err = str(e).lower()
        if "endpoint" in err or "503" in err:
            raise HeatServiceUnavailable(f"Heat 서비스에 접근할 수 없습니다: {e}") from e
        raise HeatStackError(f"stack 생성 실패: {e}") from e


def wait_for_stack_complete(
    conn: openstack.connection.Connection,
    stack_id: str,
    timeout: int = 600,
    poll_interval: int = 5,
) -> dict:
    """stack 이 CREATE_COMPLETE 될 때까지 폴링하고 outputs dict 를 반환한다."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            stack = conn.orchestration.get_stack(stack_id)
        except Exception as e:
            raise HeatStackError(f"stack 조회 실패: {e}") from e

        status = getattr(stack, "status", "") or ""
        _logger.debug("[heat] stack %s 상태: %s", stack_id, status)

        if status == "CREATE_COMPLETE":
            outputs = {}
            for item in getattr(stack, "outputs", []) or []:
                outputs[item.get("output_key", "")] = item.get("output_value", "")
            return outputs

        if "FAILED" in status:
            reason = getattr(stack, "status_reason", "") or ""
            raise HeatStackError(f"stack {stack_id} 실패: {status} — {reason}")

        time.sleep(poll_interval)

    raise HeatStackError(f"stack {stack_id} 완료 대기 시간 초과 ({timeout}s)")


def delete_stack(conn: openstack.connection.Connection, stack_id: str) -> None:
    """Heat stack 을 삭제한다. 오류는 경고로 기록하고 best-effort 로 처리한다."""
    try:
        conn.orchestration.delete_stack(stack_id)
        _logger.info("[heat] stack 삭제 요청: %s", stack_id)
    except Exception as e:
        _logger.warning("[heat] stack 삭제 실패 (dangling 가능): %s — %s", stack_id, e)
