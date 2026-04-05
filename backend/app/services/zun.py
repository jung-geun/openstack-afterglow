"""Zun 컨테이너 서비스 — openstacksdk에 Zun 프록시가 없으므로 raw REST 사용."""
import openstack

from app.models.containers import ZunContainerInfo


class ZunServiceUnavailable(Exception):
    """Zun 서비스가 배포되지 않았거나 접근할 수 없을 때 발생."""


def _get_zun_endpoint(conn: openstack.connection.Connection) -> str:
    """서비스 카탈로그에서 Zun endpoint 조회."""
    try:
        endpoint = conn.session.get_endpoint(
            service_type='container',
            interface='public',
        )
        base = endpoint.rstrip('/')
        # 서비스 카탈로그 endpoint에 이미 /v1 경로가 포함된 경우 제거
        # (예: https://zun.dmslab.re.kr/v1/ → /v1/containers 이중 경로 방지)
        if base.endswith('/v1'):
            base = base[:-3]
        return base
    except Exception:
        pass
    # fallback: identity endpoint에서 추론
    auth_url = conn.auth.get('auth_url', '')
    host = auth_url.split('//')[1].split(':')[0] if '//' in auth_url else 'localhost'
    return f"http://{host}:9517"


def _container_to_info(data: dict) -> ZunContainerInfo:
    return ZunContainerInfo(
        uuid=data.get('uuid', ''),
        name=data.get('name', ''),
        status=data.get('status', ''),
        status_reason=data.get('status_reason'),
        image=data.get('image'),
        command=data.get('command') if isinstance(data.get('command'), str) else ' '.join(data.get('command') or []),
        cpu=data.get('cpu'),
        memory=str(data.get('memory', '')) if data.get('memory') else None,
        created_at=data.get('created_at'),
        addresses=data.get('addresses'),
    )


def list_containers(conn: openstack.connection.Connection) -> list[ZunContainerInfo]:
    endpoint = _get_zun_endpoint(conn)
    try:
        resp = conn.session.get(f"{endpoint}/v1/containers")
        # HTTP 상태 코드 검사 (404는 서비스 미배포를 의미)
        status_code = getattr(resp, 'status_code', None) or getattr(resp, 'status', None)
        if status_code == 404:
            raise ZunServiceUnavailable("Zun 서비스 엔드포인트가 404를 반환했습니다")
        data = resp.json() if hasattr(resp, 'json') else {}
        containers = data.get('containers', data) if isinstance(data, dict) else data
        if isinstance(containers, list):
            return [_container_to_info(c) for c in containers]
        return []
    except ZunServiceUnavailable:
        raise
    except Exception as e:
        err_str = str(e).lower()
        if '404' in err_str or 'not found' in err_str or 'connection' in err_str:
            raise ZunServiceUnavailable(f"Zun 서비스에 접근할 수 없습니다: {e}") from e
        raise


def get_container(conn: openstack.connection.Connection, container_id: str) -> ZunContainerInfo:
    endpoint = _get_zun_endpoint(conn)
    resp = conn.session.get(f"{endpoint}/v1/containers/{container_id}")
    return _container_to_info(resp.json())


def create_container(
    conn: openstack.connection.Connection,
    name: str,
    image: str,
    command: str | None = None,
    cpu: float | None = None,
    memory: str | None = None,
    environment: dict | None = None,
    auto_remove: bool = False,
) -> ZunContainerInfo:
    endpoint = _get_zun_endpoint(conn)
    body: dict = {"name": name, "image": image}
    if command:
        body["command"] = command
    if cpu is not None:
        body["cpu"] = cpu
    if memory:
        body["memory"] = memory
    if environment:
        body["environment"] = environment
    if auto_remove:
        body["auto_remove"] = auto_remove
    resp = conn.session.post(f"{endpoint}/v1/containers", json=body)
    return _container_to_info(resp.json())


def delete_container(conn: openstack.connection.Connection, container_id: str) -> None:
    endpoint = _get_zun_endpoint(conn)
    conn.session.delete(f"{endpoint}/v1/containers/{container_id}?force=true")


def start_container(conn: openstack.connection.Connection, container_id: str) -> None:
    endpoint = _get_zun_endpoint(conn)
    conn.session.post(f"{endpoint}/v1/containers/{container_id}/start")


def stop_container(conn: openstack.connection.Connection, container_id: str) -> None:
    endpoint = _get_zun_endpoint(conn)
    conn.session.post(f"{endpoint}/v1/containers/{container_id}/stop")


def get_container_logs(conn: openstack.connection.Connection, container_id: str) -> str:
    endpoint = _get_zun_endpoint(conn)
    resp = conn.session.get(f"{endpoint}/v1/containers/{container_id}/logs?stdout=true&stderr=true")
    return resp.text if hasattr(resp, 'text') else str(resp.content)
