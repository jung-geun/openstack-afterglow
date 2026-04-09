import openstack
from keystoneauth1.identity import v3
from keystoneauth1 import session as ks_session

from app.config import get_settings


def authenticate(username: str, password: str, project_name: str, domain_name: str = "Default") -> dict:
    """
    Keystone 인증 후 토큰과 사용자 정보를 반환.
    """
    settings = get_settings()

    auth_plugin = v3.Password(
        auth_url=settings.os_auth_url,
        username=username,
        password=password,
        project_name=project_name or settings.os_project_name,
        user_domain_name=domain_name,
        project_domain_name=settings.os_project_domain_name,
    )

    sess = ks_session.Session(auth=auth_plugin, timeout=30)
    access = auth_plugin.get_access(sess)

    return {
        "token": access.auth_token,
        "project_id": access.project_id or "",
        "project_name": access.project_name or "",
        "user_id": access.user_id or "",
        "username": access.username or username,
        "expires_at": access.expires.isoformat() if access.expires else "",
        "roles": list(access.role_names) if access.role_names else [],
    }


def validate_token(token: str, project_id: str = "") -> dict:
    """
    토큰 유효성 검증. 유효하면 토큰 정보 반환, 아니면 예외 발생.
    """
    settings = get_settings()

    kwargs = {"auth_url": settings.os_auth_url, "token": token}
    if project_id:
        kwargs["project_id"] = project_id

    auth_plugin = v3.Token(**kwargs)
    sess = ks_session.Session(auth=auth_plugin, timeout=30)
    access = auth_plugin.get_access(sess)

    return {
        "token": access.auth_token,
        "project_id": access.project_id or "",
        "project_name": access.project_name or "",
        "user_id": access.user_id or "",
        "username": access.username or "",
        "expires_at": access.expires.isoformat() if access.expires else "",
        "roles": list(access.role_names) if access.role_names else [],
    }


def get_openstack_connection(token: str, project_id: str) -> openstack.connection.Connection:
    """
    검증된 토큰으로 openstacksdk Connection 객체 반환.
    load_envvars=False 로 OS_* 환경변수를 무시해 v3.Token에 불필요한 인자가
    전달되는 오류를 방지한다.
    """
    settings = get_settings()

    return openstack.connect(
        load_envvars=False,
        load_yaml_config=False,
        auth_url=settings.os_auth_url,
        auth_type="token",
        token=token,
        project_id=project_id or None,
        region_name=settings.os_region_name,
        api_timeout=30,
    )


def revoke_token(token: str) -> None:
    """Keystone에 토큰 폐기 요청 (DELETE /v3/auth/tokens)."""
    settings = get_settings()
    auth_plugin = v3.Token(auth_url=settings.os_auth_url, token=token)
    sess = ks_session.Session(auth=auth_plugin, timeout=10)
    sess.delete(
        f"{settings.os_auth_url}/auth/tokens",
        endpoint_filter=None,
        headers={"X-Subject-Token": token},
        authenticated=False,
    )


def get_user(conn: openstack.connection.Connection, user_id: str) -> dict:
    """user_id로 사용자 상세 정보 조회 (이름, 이메일 등)."""
    u = conn.identity.get_user(user_id)
    return {
        "id": u.id,
        "name": u.name or "",
        "email": getattr(u, 'email', None) or "",
    }


def list_projects(token: str) -> list[dict]:
    """
    사용자가 접근 가능한 프로젝트 목록 반환.
    Keystone v3 API를 사용하여 토큰의 사용자가 접근할 수 있는 모든 프로젝트를 조회.
    """
    settings = get_settings()

    # 토큰으로 세션 생성
    auth_plugin = v3.Token(
        auth_url=settings.os_auth_url,
        token=token,
    )
    sess = ks_session.Session(auth=auth_plugin)

    # Keystone v3 API로 프로젝트 목록 조회
    from keystoneclient.v3 import client as ks_client
    ks = ks_client.Client(session=sess)

    # 현재 사용자가 접근 가능한 프로젝트 목록
    user_id = auth_plugin.get_access(sess).user_id
    projects = ks.projects.list(user=user_id)

    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description or "",
            "domain_id": p.domain_id,
            "enabled": p.enabled,
        }
        for p in projects
    ]
