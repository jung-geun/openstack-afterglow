import logging

import openstack
from keystoneauth1 import session as ks_session
from keystoneauth1.identity import v3

from app.config import get_settings

_logger = logging.getLogger(__name__)

# admin 프로젝트 ID / admin role ID 캐시 (서비스 admin 크리덴셜 조회 결과)
_admin_project_id_cache: str | None = None
_admin_role_id_cache: str | None = None


def _get_admin_ks_client():
    """서비스 admin 크리덴셜로 Keystone v3 Client 생성.

    사용자 세션은 OpenStack policy 때문에 role_assignments 조회가 제한될 수 있으므로,
    시스템 admin 판별은 서비스 크리덴셜로 수행한다.
    """
    from keystoneclient.v3 import client as ks_client

    settings = get_settings()
    admin_auth = v3.Password(
        auth_url=settings.os_auth_url,
        username=settings.os_username,
        password=settings.os_password,
        project_name=settings.os_project_name,
        user_domain_name=settings.os_user_domain_name,
        project_domain_name=settings.os_project_domain_name,
    )
    admin_sess = ks_session.Session(auth=admin_auth, timeout=15, verify=settings.ssl_verify)
    return ks_client.Client(session=admin_sess)


def _resolve_admin_ids() -> tuple[str | None, str | None]:
    """admin 프로젝트 ID와 admin role ID 반환 (프로세스 수명 동안 1회 조회)."""
    global _admin_project_id_cache, _admin_role_id_cache
    if _admin_project_id_cache and _admin_role_id_cache:
        return _admin_project_id_cache, _admin_role_id_cache

    settings = get_settings()
    try:
        ks = _get_admin_ks_client()
        admin_projects = ks.projects.list(name=settings.os_project_name)
        admin_roles = ks.roles.list(name="admin")
        if admin_projects and admin_roles:
            _admin_project_id_cache = admin_projects[0].id
            _admin_role_id_cache = admin_roles[0].id
            return _admin_project_id_cache, _admin_role_id_cache
    except Exception:
        _logger.warning("admin 프로젝트/role ID 조회 실패", exc_info=True)
    return None, None


def _is_system_admin(user_id: str, *_args, **_kwargs) -> bool:
    """사용자가 admin 프로젝트에서 admin role을 가지는지 확인.

    서비스 admin 크리덴셜로 role_assignments 를 조회하여 policy 제약을 회피한다.
    추가 인자(session, settings)는 호환성을 위해 받되 사용하지 않는다.
    """
    if not user_id:
        return False
    try:
        admin_project_id, admin_role_id = _resolve_admin_ids()
        if not admin_project_id or not admin_role_id:
            return False
        ks = _get_admin_ks_client()
        assignments = ks.role_assignments.list(
            user=user_id,
            project=admin_project_id,
            role=admin_role_id,
        )
        return len(assignments) > 0
    except Exception:
        _logger.warning("is_system_admin 체크 실패", exc_info=True)
        return False


def authenticate(username: str, password: str, project_name: str, domain_name: str = "Default") -> dict:
    """
    Keystone 인증 후 토큰과 사용자 정보를 반환.

    project_name이 지정되면 해당 프로젝트로 scoped 인증.
    미지정 시 unscoped 인증 → 사용자의 프로젝트 목록 조회 → 첫 번째 프로젝트로 scoped 토큰 발급.
    """
    settings = get_settings()

    if project_name:
        # 명시적 프로젝트 지정 시 직접 scoped 인증
        return _authenticate_scoped(
            username,
            password,
            project_name,
            domain_name,
            settings,
        )

    # 1) unscoped 인증
    unscoped_auth = v3.Password(
        auth_url=settings.os_auth_url,
        username=username,
        password=password,
        user_domain_name=domain_name,
        unscoped=True,
    )
    unscoped_sess = ks_session.Session(auth=unscoped_auth, timeout=30, verify=settings.ssl_verify)
    unscoped_access = unscoped_auth.get_access(unscoped_sess)
    unscoped_token = unscoped_access.auth_token
    user_id = unscoped_access.user_id

    # 2) 사용자의 프로젝트 목록 조회
    from keystoneclient.v3 import client as ks_client

    ks = ks_client.Client(session=unscoped_sess)
    projects = ks.projects.list(user=user_id)
    enabled_projects = [p for p in projects if p.enabled]

    if not enabled_projects:
        raise Exception("접근 가능한 프로젝트가 없습니다")

    # 3) default_project_id가 있으면 우선, 없으면 첫 번째 프로젝트
    default_pid = getattr(unscoped_access, "project_id", None)
    target_project = None
    if default_pid:
        target_project = next((p for p in enabled_projects if p.id == default_pid), None)
    if not target_project:
        target_project = enabled_projects[0]

    # 4) 선택된 프로젝트로 scoped 토큰 발급
    scoped_auth = v3.Token(
        auth_url=settings.os_auth_url,
        token=unscoped_token,
        project_id=target_project.id,
    )
    scoped_sess = ks_session.Session(auth=scoped_auth, timeout=30, verify=settings.ssl_verify)
    scoped_access = scoped_auth.get_access(scoped_sess)

    return {
        "token": scoped_access.auth_token,
        "project_id": scoped_access.project_id or "",
        "project_name": scoped_access.project_name or "",
        "user_id": scoped_access.user_id or "",
        "username": scoped_access.username or username,
        "expires_at": scoped_access.expires.isoformat() if scoped_access.expires else "",
        "roles": list(scoped_access.role_names) if scoped_access.role_names else [],
        "is_system_admin": _is_system_admin(scoped_access.user_id, scoped_sess, settings),
    }


def _authenticate_scoped(
    username: str,
    password: str,
    project_name: str,
    domain_name: str,
    settings,
) -> dict:
    """지정된 프로젝트로 직접 scoped 인증."""
    auth_plugin = v3.Password(
        auth_url=settings.os_auth_url,
        username=username,
        password=password,
        project_name=project_name,
        user_domain_name=domain_name,
        project_domain_name=settings.os_project_domain_name,
    )
    sess = ks_session.Session(auth=auth_plugin, timeout=30, verify=settings.ssl_verify)
    access = auth_plugin.get_access(sess)

    return {
        "token": access.auth_token,
        "project_id": access.project_id or "",
        "project_name": access.project_name or "",
        "user_id": access.user_id or "",
        "username": access.username or username,
        "expires_at": access.expires.isoformat() if access.expires else "",
        "roles": list(access.role_names) if access.role_names else [],
        "is_system_admin": _is_system_admin(access.user_id, sess, settings),
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
    sess = ks_session.Session(auth=auth_plugin, timeout=30, verify=settings.ssl_verify)
    access = auth_plugin.get_access(sess)

    return {
        "token": access.auth_token,
        "project_id": access.project_id or "",
        "project_name": access.project_name or "",
        "user_id": access.user_id or "",
        "username": access.username or "",
        "expires_at": access.expires.isoformat() if access.expires else "",
        "roles": list(access.role_names) if access.role_names else [],
        "is_system_admin": _is_system_admin(access.user_id, sess, settings),
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
        verify=settings.ssl_verify,
    )


def get_admin_connection_for_project(project_id: str) -> openstack.connection.Connection:
    """관리자 크리덴셜로 특정 프로젝트에 스코프된 OpenStack 연결 반환.

    콜백 등 사용자 토큰이 없는 상황에서 프로젝트 리소스를 조작할 때 사용.
    """
    settings = get_settings()
    return openstack.connect(
        load_envvars=False,
        load_yaml_config=False,
        auth_url=settings.os_auth_url,
        auth_type="password",
        username=settings.os_username,
        password=settings.os_password,
        project_id=project_id,
        user_domain_name=settings.os_user_domain_name,
        project_domain_name=settings.os_project_domain_name,
        region_name=settings.os_region_name,
        api_timeout=30,
        verify=settings.ssl_verify,
    )


def revoke_token(token: str) -> None:
    """Keystone에 토큰 폐기 요청 (DELETE /v3/auth/tokens)."""
    settings = get_settings()
    auth_plugin = v3.Token(auth_url=settings.os_auth_url, token=token)
    sess = ks_session.Session(auth=auth_plugin, timeout=10, verify=settings.ssl_verify)
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
        "email": getattr(u, "email", None) or "",
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
    sess = ks_session.Session(auth=auth_plugin, verify=settings.ssl_verify)

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
