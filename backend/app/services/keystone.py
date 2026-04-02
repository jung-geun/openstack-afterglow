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

    sess = ks_session.Session(auth=auth_plugin)
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

    kwargs = dict(auth_url=settings.os_auth_url, token=token)
    if project_id:
        kwargs["project_id"] = project_id

    auth_plugin = v3.Token(**kwargs)
    sess = ks_session.Session(auth=auth_plugin)
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
    )
