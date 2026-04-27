"""union_layers 서비스 — MariaDB 실 SQL 통합 테스트 (20 케이스).

실행: AFTERGLOW_TEST_DATABASE_URL=mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_test \
     pytest tests/test_union_layers_db.py -v -m db
"""

import os
import secrets

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.db  # noqa: F401 — side-effect: Base에 ORM 모델 등록
from app.models.union import CreateLayerRequest
from app.services import union_layers as svc

pytestmark = pytest.mark.db

_DB_URL_ENV = "AFTERGLOW_TEST_DATABASE_URL"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash() -> str:
    return f"sha256:{secrets.token_hex(32)}"


def _req(**kwargs) -> CreateLayerRequest:
    defaults = dict(
        name="test-layer",
        version="1.0",
        content_hash=_hash(),
        ubuntu_base="ubuntu:22.04",
        build_recipe={},
        installed_packages={},
        size_bytes=1024,
        file_count=10,
    )
    defaults.update(kwargs)
    return CreateLayerRequest(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get(_DB_URL_ENV)
    if not url:
        pytest.skip(f"{_DB_URL_ENV} 미설정 — MariaDB 통합 테스트 건너뜀")
    return url


@pytest_asyncio.fixture(scope="module")
async def db_engine(db_url):
    from app.database import Base

    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def sess(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        # SUT이 내부에서 session.commit()을 호출하므로 ROLLBACK 격리 불가.
        # FK 체크를 임시 해제한 뒤 전수 삭제 후 재활성.
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        await session.execute(text("DELETE FROM union_user_mounts"))
        await session.execute(text("DELETE FROM union_templates"))
        await session.execute(text("DELETE FROM union_layers"))
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        await session.commit()


# ---------------------------------------------------------------------------
# C3-1  create_layer — INSERT 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_layer_row_exists(sess):
    req = _req(name="base-layer", version="1.0")
    info = await svc.create_layer(sess, req, created_by="user-a")
    assert info.id.startswith("sha256:")

    # 실 SELECT로 존재 확인
    row = await sess.execute(text("SELECT id, name, sealed FROM union_layers WHERE id = :id"), {"id": info.id})
    r = row.mappings().one()
    assert r["name"] == "base-layer"
    assert r["sealed"] == 0  # FALSE


# ---------------------------------------------------------------------------
# C3-2  content_hash 중복 → ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_layer_duplicate_hash_raises(sess):
    req = _req(name="dup-layer", version="1.0")
    await svc.create_layer(sess, req, created_by="user-a")
    # 같은 content_hash로 다시 시도 → ValueError
    with pytest.raises(ValueError, match="이미 존재합니다"):
        await svc.create_layer(sess, req, created_by="user-a")


# ---------------------------------------------------------------------------
# C3-3  seal_layer — sealed_at NOT NULL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seal_layer_sealed_at_set(sess):
    req = _req(name="sealable", version="1.0")
    info = await svc.create_layer(sess, req, created_by="user-a")
    seal_resp = await svc.seal_layer(sess, info.id)

    assert seal_resp.sealed is True
    assert seal_resp.sealed_at is not None

    # DB에서 직접 확인
    row = await sess.execute(text("SELECT sealed, sealed_at FROM union_layers WHERE id = :id"), {"id": info.id})
    r = row.mappings().one()
    assert r["sealed"] == 1
    assert r["sealed_at"] is not None


# ---------------------------------------------------------------------------
# C3-4  seal_layer 이미 봉인된 레이어 → ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seal_already_sealed_raises(sess):
    req = _req(name="double-seal", version="1.0")
    info = await svc.create_layer(sess, req, created_by="user-a")
    await svc.seal_layer(sess, info.id)

    with pytest.raises(ValueError, match="이미 봉인"):
        await svc.seal_layer(sess, info.id)


# ---------------------------------------------------------------------------
# C3-5  봉인 안 된 부모로 자식 생성 → ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_child_requires_sealed_parent(sess):
    parent_req = _req(name="unsealed-parent", version="1.0")
    parent = await svc.create_layer(sess, parent_req, created_by="user-a")
    # 봉인하지 않음

    child_req = _req(name="child", version="1.0", parent_id=parent.id)
    with pytest.raises(ValueError, match="봉인되지 않았습니다"):
        await svc.create_layer(sess, child_req, created_by="user-a")


# ---------------------------------------------------------------------------
# C3-6  봉인된 부모로 자식 생성 — 정상 경로
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_child_with_sealed_parent(sess):
    parent_req = _req(name="sealed-parent", version="1.0")
    parent = await svc.create_layer(sess, parent_req, created_by="user-a")
    await svc.seal_layer(sess, parent.id)

    child_req = _req(name="child", version="1.0", parent_id=parent.id)
    child = await svc.create_layer(sess, child_req, created_by="user-a")
    assert child.parent_id == parent.id


# ---------------------------------------------------------------------------
# C3-7  존재하지 않는 parent_id → ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_layer_nonexistent_parent_raises(sess):
    req = _req(name="orphan", version="1.0", parent_id=_hash())
    with pytest.raises(ValueError, match="존재하지 않습니다"):
        await svc.create_layer(sess, req, created_by="user-a")


# ---------------------------------------------------------------------------
# C3-8  get_ancestors — 5단 체인: base-first 순서 검증 (WITH RECURSIVE CTE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ancestors_five_chain(sess):
    layers = []
    prev_id = None
    for i in range(5):
        req = _req(name=f"chain-layer-{i}", version="1.0", parent_id=prev_id)
        info = await svc.create_layer(sess, req, created_by="user-a")
        if prev_id is not None:
            await svc.seal_layer(sess, prev_id)
        layers.append(info)
        prev_id = info.id

    leaf_id = layers[-1].id
    chain = await svc.get_ancestors(sess, leaf_id)

    assert len(chain.layers) == 5
    # base-first: chain.layers[0] is root, chain.layers[-1] is leaf
    assert chain.layers[0].id == layers[0].id
    assert chain.layers[-1].id == leaf_id
    # depth 순서 확인 (이름 순서)
    names = [lyr.name for lyr in chain.layers]
    assert names == [f"chain-layer-{i}" for i in range(5)]


# ---------------------------------------------------------------------------
# C3-9  get_ancestors — 부모 없는 단일 레이어 → 자기 자신만 반환
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ancestors_root_node(sess):
    req = _req(name="root-only", version="1.0")
    info = await svc.create_layer(sess, req, created_by="user-a")

    chain = await svc.get_ancestors(sess, info.id)
    assert len(chain.layers) == 1
    assert chain.layers[0].id == info.id


# ---------------------------------------------------------------------------
# C3-10  get_layer — 존재하지 않는 레이어 → None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_layer_not_found(sess):
    result = await svc.get_layer(sess, _hash())
    assert result is None


# ---------------------------------------------------------------------------
# C3-11  list_layers — name 필터
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_layers_name_filter(sess):
    for i in range(3):
        await svc.create_layer(sess, _req(name="alpha", version=f"{i}"), created_by="u")
    await svc.create_layer(sess, _req(name="beta", version="1"), created_by="u")

    alpha_layers = await svc.list_layers(sess, name="alpha", is_admin=True)
    beta_layers = await svc.list_layers(sess, name="beta", is_admin=True)
    assert len(alpha_layers) == 3
    assert len(beta_layers) == 1
    assert all(lyr.name == "alpha" for lyr in alpha_layers)


# ---------------------------------------------------------------------------
# C3-12  list_layers — limit / offset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_layers_limit_offset(sess):
    for i in range(5):
        await svc.create_layer(sess, _req(name=f"paged-{i}", version="1"), created_by="u")

    page1 = await svc.list_layers(sess, is_admin=True, limit=3, offset=0)
    page2 = await svc.list_layers(sess, is_admin=True, limit=3, offset=3)
    assert len(page1) == 3
    # 나머지 (최소 2개)
    assert len(page2) >= 2
    # 중복 없음
    ids1 = {lyr.id for lyr in page1}
    ids2 = {lyr.id for lyr in page2}
    assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# C3-13  list_layers — 프로젝트 격리 (비관리자)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_layers_project_isolation(sess):
    # 공유 레이어 (project_id=None)
    shared = await svc.create_layer(sess, _req(name="shared-layer", version="1"), created_by="admin")
    # 프로젝트 A 레이어
    proj_a = await svc.create_layer(
        sess, _req(name="proj-a-layer", version="1", project_id="proj-a"), created_by="ua"
    )
    # 프로젝트 B 레이어
    await svc.create_layer(sess, _req(name="proj-b-layer", version="1", project_id="proj-b"), created_by="ub")

    # 프로젝트 A 비관리자 → 공유 + proj-a 만 보임
    result = await svc.list_layers(sess, project_id="proj-a", is_admin=False)
    ids = {lyr.id for lyr in result}
    assert shared.id in ids
    assert proj_a.id in ids
    assert not any(lyr.name == "proj-b-layer" for lyr in result)


# ---------------------------------------------------------------------------
# C3-14  list_layers — 관리자는 전체 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_layers_admin_sees_all(sess):
    await svc.create_layer(sess, _req(name="sys-layer", version="1"), created_by="admin")
    await svc.create_layer(
        sess, _req(name="tenant-layer", version="1", project_id="some-proj"), created_by="user"
    )

    all_layers = await svc.list_layers(sess, is_admin=True)
    names = {lyr.name for lyr in all_layers}
    assert "sys-layer" in names
    assert "tenant-layer" in names


# ---------------------------------------------------------------------------
# C3-15  delete_layer — 자식 있는 레이어 삭제 → ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_layer_with_child_raises(sess):
    parent = await svc.create_layer(sess, _req(name="del-parent", version="1"), created_by="u")
    await svc.seal_layer(sess, parent.id)
    child = await svc.create_layer(sess, _req(name="del-child", version="1", parent_id=parent.id), created_by="u")

    with pytest.raises(ValueError, match="하위 레이어"):
        await svc.delete_layer(sess, parent.id)

    # child는 여전히 존재
    assert await svc.get_layer(sess, child.id) is not None


# ---------------------------------------------------------------------------
# C3-16  delete_layer — leaf 레이어 삭제 성공
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_layer_leaf_succeeds(sess):
    layer = await svc.create_layer(sess, _req(name="deletable-leaf", version="1"), created_by="u")
    await svc.delete_layer(sess, layer.id)
    assert await svc.get_layer(sess, layer.id) is None


# ---------------------------------------------------------------------------
# C3-17  record_mount — mounted_at 설정
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_mount_sets_mounted_at(sess):
    layer = await svc.create_layer(sess, _req(name="mountable", version="1"), created_by="u")
    mount = await svc.record_mount(sess, user_id="user-1", vm_hostname="vm-001", leaf_layer_id=layer.id)

    assert mount.mounted_at is not None
    assert mount.unmounted_at is None
    assert mount.user_id == "user-1"
    assert mount.vm_hostname == "vm-001"


# ---------------------------------------------------------------------------
# C3-18  record_unmount — unmounted_at 설정
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_unmount_sets_unmounted_at(sess):
    layer = await svc.create_layer(sess, _req(name="unmountable", version="1"), created_by="u")
    mount = await svc.record_mount(sess, user_id="user-2", vm_hostname="vm-002", leaf_layer_id=layer.id)

    updated = await svc.record_unmount(sess, mount_id=mount.id, user_id="user-2")
    assert updated.unmounted_at is not None


# ---------------------------------------------------------------------------
# C3-19  record_unmount 두 번 → ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_unmount_twice_raises(sess):
    layer = await svc.create_layer(sess, _req(name="double-unmount", version="1"), created_by="u")
    mount = await svc.record_mount(sess, user_id="user-3", vm_hostname="vm-003", leaf_layer_id=layer.id)
    await svc.record_unmount(sess, mount_id=mount.id, user_id="user-3")

    with pytest.raises(ValueError, match="이미 해제"):
        await svc.record_unmount(sess, mount_id=mount.id, user_id="user-3")


# ---------------------------------------------------------------------------
# C3-20  max_concurrent_mounts 초과 → HTTPException(409)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_concurrent_mounts_enforced(sess):
    layer = await svc.create_layer(
        sess,
        _req(name="limited-layer", version="1", max_concurrent_mounts=2),
        created_by="u",
    )
    await svc.record_mount(sess, user_id="u1", vm_hostname="vm-1", leaf_layer_id=layer.id)
    await svc.record_mount(sess, user_id="u2", vm_hostname="vm-2", leaf_layer_id=layer.id)

    with pytest.raises(HTTPException) as exc_info:
        await svc.record_mount(sess, user_id="u3", vm_hostname="vm-3", leaf_layer_id=layer.id)
    assert exc_info.value.status_code == 409
