"""swift.count_containers_all_projects — admin fan-out 컨테이너 합산 단위 테스트."""

from unittest.mock import MagicMock, patch

from app.services import swift


def _container(name: str) -> MagicMock:
    c = MagicMock()
    c.name = name
    c.count = 0
    c.bytes = 0
    return c


def _conn_with_containers(*names: str) -> MagicMock:
    conn = MagicMock()
    conn.object_store.containers = MagicMock(return_value=[_container(n) for n in names])
    conn.object_store.get_endpoint = MagicMock(return_value="http://swift")
    conn._afterglow_project_id = "p"
    conn.close = MagicMock()
    return conn


def test_count_all_projects_sums_containers_across_projects():
    """여러 프로젝트의 컨테이너 수가 합산된다."""
    projects = [{"id": "p1", "name": "A"}, {"id": "p2", "name": "B"}]
    conn_p1 = _conn_with_containers("a", "b")  # 2
    conn_p2 = _conn_with_containers("c", "d", "e")  # 3

    with (
        patch("app.services.keystone.list_projects", return_value=projects),
        patch(
            "app.services.keystone.get_admin_connection_for_project",
            side_effect=[conn_p1, conn_p2],
        ),
    ):
        total = swift.count_containers_all_projects("admin-token")

    assert total == 5


def test_count_all_projects_skips_unauthorized_project():
    """한 프로젝트 connection 이 401이면 그 프로젝트만 0 처리하고 나머지는 합산."""
    from keystoneauth1.exceptions.http import Unauthorized

    projects = [{"id": "p1", "name": "A"}, {"id": "p2", "name": "B"}]
    conn_p2 = _conn_with_containers("c")  # 1

    def _get_conn(pid: str):
        if pid == "p1":
            raise Unauthorized("no admin role")
        return conn_p2

    with (
        patch("app.services.keystone.list_projects", return_value=projects),
        patch("app.services.keystone.get_admin_connection_for_project", side_effect=_get_conn),
    ):
        total = swift.count_containers_all_projects("admin-token")

    assert total == 1


def test_count_all_projects_returns_zero_when_keystone_fails():
    """Keystone 프로젝트 목록 조회 실패 시 0 (silent fail)."""
    with patch("app.services.keystone.list_projects", side_effect=Exception("keystone down")):
        assert swift.count_containers_all_projects("admin-token") == 0


def test_count_all_projects_skips_project_without_id():
    """id 없는 프로젝트 항목은 skip 한다."""
    projects = [{"name": "no-id"}, {"id": "p2", "name": "B"}]
    conn_p2 = _conn_with_containers("c", "d")  # 2

    with (
        patch("app.services.keystone.list_projects", return_value=projects),
        patch(
            "app.services.keystone.get_admin_connection_for_project",
            return_value=conn_p2,
        ),
    ):
        total = swift.count_containers_all_projects("admin-token")

    assert total == 2
