"""신규 컨테이너 생성 시 X-Container-Meta-Owner-Project-Id 부착 검증.

Swift 의 account 모델 (project-scoped token = 그 account 의 컨테이너만) 이 1차 방어선이라
metadata 자체로 IDOR 검증을 수행하지 않지만, admin/operator 도구가 owner 식별을 할 수
있도록 향후 검증의 토대로 부착해 둔다.
"""

from unittest.mock import MagicMock

from app.services import swift


def _make_conn(project_id: str = "proj-123") -> MagicMock:
    conn = MagicMock()
    conn._afterglow_project_id = project_id
    return conn


def test_create_container_attaches_owner_metadata():
    """SDK 성공 경로 — set_container_metadata 가 owner_project_id 인자로 호출됨."""
    conn = _make_conn("proj-123")
    created = MagicMock()
    created.name = "my-bucket"
    conn.object_store.create_container = MagicMock(return_value=created)
    conn.object_store.set_container_metadata = MagicMock()

    result = swift.create_container(conn, "my-bucket")

    assert result["name"] == "my-bucket"
    conn.object_store.set_container_metadata.assert_called_once_with(
        "my-bucket", owner_project_id="proj-123"
    )


def test_create_container_swallows_metadata_failure():
    """metadata set 실패는 컨테이너 생성 결과를 무효화하지 않음."""
    conn = _make_conn("proj-123")
    created = MagicMock()
    created.name = "my-bucket"
    conn.object_store.create_container = MagicMock(return_value=created)
    conn.object_store.set_container_metadata = MagicMock(side_effect=Exception("metadata fail"))

    result = swift.create_container(conn, "my-bucket")

    assert result["name"] == "my-bucket"


def test_create_container_no_metadata_when_no_project_id():
    """conn 에 project_id 가 없으면 metadata 호출 자체 생략."""
    conn = MagicMock()
    conn._afterglow_project_id = None
    created = MagicMock()
    created.name = "my-bucket"
    conn.object_store.create_container = MagicMock(return_value=created)
    conn.object_store.set_container_metadata = MagicMock()

    swift.create_container(conn, "my-bucket")

    conn.object_store.set_container_metadata.assert_not_called()
