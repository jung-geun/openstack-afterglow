"""Heat 오케스트레이션 서비스 — Magnum K8s 클러스터 스택 추적용."""
import openstack


class HeatServiceUnavailable(Exception):
    """Heat 서비스가 배포되지 않았거나 접근할 수 없을 때 발생."""


def _get_stack(conn: openstack.connection.Connection, stack_id: str):
    """스택 단건 조회."""
    try:
        return conn.orchestration.get_stack(stack_id)
    except Exception as e:
        err = str(e).lower()
        if '404' in err or 'not found' in err or 'no such' in err:
            raise HeatServiceUnavailable(f"스택을 찾을 수 없습니다: {stack_id}") from e
        if 'endpoint' in err or 'connection' in err or '503' in err:
            raise HeatServiceUnavailable(f"Heat 서비스에 접근할 수 없습니다: {e}") from e
        raise


def get_stack_detail(conn: openstack.connection.Connection, stack_id: str) -> dict:
    """스택 상세 정보 반환."""
    try:
        stack = _get_stack(conn, stack_id)
        s = stack.to_dict() if hasattr(stack, 'to_dict') else {}
        return {
            "id": stack.id,
            "name": getattr(stack, 'name', None) or s.get('stack_name'),
            "status": getattr(stack, 'status', None) or s.get('stack_status'),
            "status_reason": getattr(stack, 'status_reason', None) or s.get('stack_status_reason'),
            "created_at": str(getattr(stack, 'created_at', None) or s.get('creation_time', '')),
            "updated_at": str(getattr(stack, 'updated_at', None) or s.get('updated_time', '')),
            "parameters": s.get('parameters', {}),
            "outputs": s.get('outputs', []),
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
            resources.append({
                "resource_name": getattr(r, 'resource_name', None) or getattr(r, 'name', ''),
                "resource_type": getattr(r, 'resource_type', '') or '',
                "physical_resource_id": getattr(r, 'physical_resource_id', None) or '',
                "resource_status": getattr(r, 'resource_status', '') or getattr(r, 'status', ''),
                "resource_status_reason": getattr(r, 'resource_status_reason', None) or getattr(r, 'status_reason', ''),
                "created_at": str(getattr(r, 'creation_time', '') or getattr(r, 'created_at', '') or ''),
            })
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
        for e in conn.orchestration.events(stack_id):
            events.append({
                "resource_name": getattr(e, 'resource_name', None) or getattr(e, 'logical_resource_id', ''),
                "resource_status": getattr(e, 'resource_status', '') or getattr(e, 'status', ''),
                "resource_status_reason": getattr(e, 'resource_status_reason', None) or '',
                "event_time": str(getattr(e, 'event_time', '') or getattr(e, 'created_at', '') or ''),
                "logical_resource_id": getattr(e, 'logical_resource_id', None) or '',
                "physical_resource_id": getattr(e, 'physical_resource_id', None) or '',
            })
        # 최신순 정렬
        events.sort(key=lambda x: x['event_time'], reverse=True)
        return events
    except HeatServiceUnavailable:
        raise
    except Exception as e:
        raise HeatServiceUnavailable(f"이벤트 목록 조회 실패: {e}") from e
