"""Union Mount 레이어 시스템 서비스 레이어.

MySQL 8.0+ WITH RECURSIVE CTE로 조상 체인을 해석한다.
"""

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import UnionLayer, UnionTemplate, UnionUserMount
from app.models.union import (
    AncestorChain,
    CreateLayerRequest,
    CreateTemplateRequest,
    ForkLayerRequest,
    LayerInfo,
    MountInfo,
    RestoreLayerRequest,
    SealLayerResponse,
    SnapshotLayerRequest,
    StorageStats,
    TemplateInfo,
)
from app.services import manila

_logger = logging.getLogger(__name__)


def _layer_to_info(layer: UnionLayer) -> LayerInfo:
    return LayerInfo(
        id=layer.id,
        name=layer.name,
        version=layer.version,
        created_at=layer.created_at,
        created_by=layer.created_by,
        sealed=layer.sealed,
        sealed_at=getattr(layer, "sealed_at", None),
        parent_id=layer.parent_id,
        parent_ids=getattr(layer, "parent_ids", None),
        project_id=getattr(layer, "project_id", None),
        ubuntu_base=layer.ubuntu_base,
        build_recipe=layer.build_recipe or {},
        installed_packages=layer.installed_packages or {},
        content_hash=layer.content_hash,
        size_bytes=layer.size_bytes,
        file_count=layer.file_count,
        license_type=getattr(layer, "license_type", None),
        max_concurrent_mounts=getattr(layer, "max_concurrent_mounts", None),
    )


def _is_multi_parent(layer: UnionLayer) -> bool:
    """multi 모드 분기 조건. parent_ids가 NOT NULL이고 2개 이상."""
    pids = getattr(layer, "parent_ids", None)
    return pids is not None and len(pids) >= 2


def _template_to_info(tmpl: UnionTemplate, stack: list[LayerInfo] | None = None) -> TemplateInfo:
    return TemplateInfo(
        name=tmpl.name,
        version=tmpl.version,
        created_at=tmpl.created_at,
        created_by=tmpl.created_by,
        parent_version=tmpl.parent_version,
        ubuntu_base=tmpl.ubuntu_base,
        leaf_layer_id=tmpl.leaf_layer_id,
        note=tmpl.note,
        resolved_stack=stack,
    )


# ---------------------------------------------------------------------------
# 레이어 CRUD
# ---------------------------------------------------------------------------


async def _validate_common_base(session: AsyncSession, parent_ids: list[str]) -> str | None:
    """모든 부모(직접 + 조상)의 root ubuntu_base가 일치하는지 검증.

    각 부모의 single-parent 조상 체인을 거슬러 root의 ubuntu_base를 수집한다.
    모두 동일하거나 모두 None이면 그 값(또는 None) 반환. 불일치 시 ValueError.
    """
    bases: dict[str, str | None] = {}
    for pid in parent_ids:
        cursor_id: str | None = pid
        last_base: str | None = None
        seen: set[str] = set()
        while cursor_id is not None:
            if cursor_id in seen:
                raise ValueError(f"조상 체인에 사이클이 감지됨: {cursor_id}")
            seen.add(cursor_id)
            node = await session.get(UnionLayer, cursor_id)
            if node is None:
                raise ValueError(f"부모 레이어 {cursor_id}를 찾을 수 없습니다")
            if node.ubuntu_base is not None:
                last_base = node.ubuntu_base
            cursor_id = node.parent_id  # multi 부모는 root에 도달할 때까지 single-parent로만 거슬러 올라감
        bases[pid] = last_base

    unique_bases = {b for b in bases.values() if b is not None}
    if len(unique_bases) > 1:
        raise ValueError(f"부모 레이어의 ubuntu_base가 일치하지 않습니다 ({sorted(unique_bases)})")
    return next(iter(unique_bases), None)


async def create_layer(
    session: AsyncSession,
    data: CreateLayerRequest,
    created_by: str,
    project_id: str | None = None,
) -> LayerInfo:
    """새 레이어 등록. 부모가 있으면 봉인 여부 검증. multi-parent도 지원."""
    layer_id = (
        f"sha256:{data.content_hash[len('sha256:') :]}"
        if data.content_hash.startswith("sha256:")
        else data.content_hash
    )

    # 동일 id 중복 확인
    existing = await session.get(UnionLayer, layer_id)
    if existing:
        raise ValueError(f"레이어 {layer_id}는 이미 존재합니다")

    # 단일 부모 검증
    if data.parent_id:
        parent = await session.get(UnionLayer, data.parent_id)
        if parent is None:
            raise ValueError(f"부모 레이어 {data.parent_id}가 존재하지 않습니다")
        if not parent.sealed:
            raise ValueError(
                f"부모 레이어 {data.parent_id}가 아직 봉인되지 않았습니다. 봉인 후 자식 레이어를 생성하세요."
            )

    # 다중 부모 검증 (실험, opt-in)
    if data.parent_ids:
        if layer_id in data.parent_ids:
            raise ValueError("자기 자신을 부모로 지정할 수 없습니다")
        for pid in data.parent_ids:
            parent = await session.get(UnionLayer, pid)
            if parent is None:
                raise ValueError(f"부모 레이어 {pid}가 존재하지 않습니다")
            if not parent.sealed:
                raise ValueError(f"부모 레이어 {pid}가 아직 봉인되지 않았습니다. 봉인 후 자식 레이어를 생성하세요.")
        await _validate_common_base(session, data.parent_ids)

        # overwrite 금지: 동일 (name, version, parent_ids JSON) 슬롯에 봉인 레이어 존재 시 거부
        # JSON 직접 비교 — 봉인된 같은 슬롯 검색은 service 레벨에서 list 비교로 처리
        candidates = await session.execute(
            select(UnionLayer).where(
                UnionLayer.name == data.name,
                UnionLayer.version == data.version,
                UnionLayer.sealed.is_(True),
                UnionLayer.parent_ids.is_not(None),
            )
        )
        for cand in candidates.scalars():
            if cand.parent_ids == data.parent_ids:
                raise ValueError(
                    f"동일한 (name={data.name}, version={data.version}, parent_ids={data.parent_ids}) "
                    f"봉인 레이어가 이미 존재합니다 ({cand.id}). overwrite 금지."
                )

    # project_id: 요청에 명시된 값 > 인자로 받은 값 > None(공유 레이어)
    effective_project_id = data.project_id or project_id or None

    layer = UnionLayer(
        id=layer_id,
        name=data.name,
        version=data.version,
        created_at=datetime.now(UTC),
        created_by=created_by,
        sealed=False,
        parent_id=data.parent_id,  # multi 모드면 None 유지 (mirror 안 함)
        parent_ids=data.parent_ids,  # multi 모드면 list, single 모드면 None
        ubuntu_base=data.ubuntu_base,
        build_recipe=data.build_recipe,
        installed_packages=data.installed_packages,
        content_hash=data.content_hash,
        size_bytes=data.size_bytes,
        file_count=data.file_count,
        project_id=effective_project_id,
        sealed_at=None,
        license_type=data.license_type,
        max_concurrent_mounts=data.max_concurrent_mounts,
    )
    session.add(layer)
    await session.commit()
    await session.refresh(layer)
    return _layer_to_info(layer)


async def get_layer(session: AsyncSession, layer_id: str) -> LayerInfo | None:
    """단일 레이어 조회."""
    layer = await session.get(UnionLayer, layer_id)
    if layer is None:
        return None
    return _layer_to_info(layer)


async def list_layers(
    session: AsyncSession,
    name: str | None = None,
    project_id: str | None = None,
    is_admin: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[LayerInfo]:
    """레이어 목록 (최신순). name 필터 + 프로젝트 격리 지원.

    격리 규칙:
    - is_admin=True: 전체 레이어 반환
    - is_admin=False: project_id=NULL(공유) + 자신의 project_id 레이어만 반환
    """
    stmt = select(UnionLayer)
    if name:
        stmt = stmt.where(UnionLayer.name == name)
    if not is_admin and project_id:
        stmt = stmt.where((UnionLayer.project_id.is_(None)) | (UnionLayer.project_id == project_id))
    elif not is_admin:
        # project_id 없는 비관리자 → 공유 레이어만
        stmt = stmt.where(UnionLayer.project_id.is_(None))
    stmt = stmt.order_by(UnionLayer.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return [_layer_to_info(row) for row in result.scalars()]


async def seal_layer(session: AsyncSession, layer_id: str) -> SealLayerResponse:
    """레이어 봉인 (sealed=True + sealed_at 기록).

    동일 (name, version, parent_id) 조합의 봉인 레이어가 이미 존재하면 overwrite 금지 정책에 의해 거부된다.
    """
    layer = await session.get(UnionLayer, layer_id)
    if layer is None:
        raise KeyError(f"레이어 {layer_id}를 찾을 수 없습니다")
    if layer.sealed:
        raise ValueError(f"레이어 {layer_id}는 이미 봉인되어 있습니다")

    # overwrite 금지: 동일 (name, version, parent_id) 슬롯에 봉인 레이어가 이미 있으면 거부
    dup_stmt = select(UnionLayer).where(
        UnionLayer.name == layer.name,
        UnionLayer.version == layer.version,
        UnionLayer.parent_id == layer.parent_id,
        UnionLayer.sealed.is_(True),
        UnionLayer.id != layer_id,
    )
    dup_result = await session.execute(dup_stmt)
    duplicate = dup_result.scalar_one_or_none()
    if duplicate:
        raise ValueError(
            f"동일한 (name={layer.name}, version={layer.version}, parent={layer.parent_id}) "
            f"봉인 레이어가 이미 존재합니다 ({duplicate.id}). overwrite 금지 정책에 의해 seal이 거부됩니다."
        )

    now = datetime.now(UTC)
    layer.sealed = True
    layer.sealed_at = now
    await session.commit()
    return SealLayerResponse(id=layer.id, sealed=True, sealed_at=now)


async def fork_layer(
    session: AsyncSession,
    source_layer_id: str,
    req: ForkLayerRequest,
    created_by: str,
    project_id: str | None = None,
) -> LayerInfo:
    """봉인된 레이어에서 새 RW 레이어를 파생(fork)한다.

    소스 레이어는 반드시 sealed=True여야 한다.
    생성된 레이어는 source_layer_id를 parent_id로 가지며 sealed=False(RW)로 시작한다.
    """
    source = await session.get(UnionLayer, source_layer_id)
    if source is None:
        raise KeyError(f"레이어 {source_layer_id}를 찾을 수 없습니다")
    if not source.sealed:
        raise ValueError(f"레이어 {source_layer_id}는 봉인되지 않았습니다. 봉인된 레이어만 fork할 수 있습니다")

    new_id = (
        f"sha256:{req.content_hash[len('sha256:') :]}" if req.content_hash.startswith("sha256:") else req.content_hash
    )
    existing = await session.get(UnionLayer, new_id)
    if existing:
        raise ValueError(f"레이어 {new_id}는 이미 존재합니다")

    forked = UnionLayer(
        id=new_id,
        name=req.name or source.name,
        version=req.version,
        created_at=datetime.now(UTC),
        created_by=created_by,
        sealed=False,
        parent_id=source_layer_id,
        ubuntu_base=source.ubuntu_base,
        build_recipe={},
        installed_packages={},
        content_hash=req.content_hash,
        size_bytes=None,
        file_count=None,
        project_id=project_id,
        sealed_at=None,
        license_type=source.license_type,
        max_concurrent_mounts=source.max_concurrent_mounts,
    )
    session.add(forked)
    await session.commit()
    await session.refresh(forked)
    return _layer_to_info(forked)


async def snapshot_layer(
    session: AsyncSession,
    layer_id: str,
    req: SnapshotLayerRequest,
    conn,
) -> dict:
    """레이어 Manila share 스냅샷을 생성한다.

    레이어가 존재해야 한다. share_id는 요청에서 명시적으로 전달받는다.
    """
    import asyncio

    layer = await session.get(UnionLayer, layer_id)
    if layer is None:
        raise KeyError(f"레이어 {layer_id}를 찾을 수 없습니다")

    snap_name = req.name or f"union-layer-{layer_id[:20]}"
    return await asyncio.to_thread(manila.create_share_snapshot, conn, req.share_id, snap_name, req.description)


async def restore_layer(
    session: AsyncSession,
    layer_id: str,
    req: RestoreLayerRequest,
    conn,
) -> None:
    """레이어 Manila share를 지정한 스냅샷으로 복원(revert)한다.

    레이어가 존재해야 하며 복원 후 sealed=False로 재설정한다(수정 가능 상태 복귀).
    """
    import asyncio

    layer = await session.get(UnionLayer, layer_id)
    if layer is None:
        raise KeyError(f"레이어 {layer_id}를 찾을 수 없습니다")

    await asyncio.to_thread(manila.revert_to_snapshot, conn, req.share_id, req.snapshot_id)

    if layer.sealed:
        layer.sealed = False
        layer.sealed_at = None
        await session.commit()


async def _get_ancestors_multi(session: AsyncSession, leaf_id: str) -> AncestorChain:
    """multi-parent DAG 순회 (BFS + Kahn toposort, dedup, 선언 순서 결정성).

    base-first 순으로 반환. overlayfs lowerdir 조립 시 reverse(leftmost=leaf).
    """
    # BFS로 모든 노드 수집 (dedup) + edges 구성
    visited: dict[str, UnionLayer] = {}
    edges: dict[str, list[str]] = {}  # child -> [parents]
    queue = [leaf_id]
    while queue:
        cur_id = queue.pop(0)
        if cur_id in visited:
            continue
        node = await session.get(UnionLayer, cur_id)
        if node is None:
            raise KeyError(f"레이어 {cur_id}를 찾을 수 없습니다 (조상 체인 누락)")
        visited[cur_id] = node
        parents: list[str] = []
        if node.parent_ids:
            parents = list(node.parent_ids)
        elif node.parent_id:
            parents = [node.parent_id]
        edges[cur_id] = parents
        for p in parents:
            if p not in visited:
                queue.append(p)

    # Kahn toposort: in_degree 계산 (parent → child 방향)
    in_degree: dict[str, int] = {nid: 0 for nid in visited}
    for child, parents in edges.items():
        in_degree[child] = len(parents)  # 자식의 in-degree = 부모 수

    # 0-degree 노드(부모가 없는 root)부터 시작 — 결정성을 위해 visited 등록 순(=BFS 발견 순) 우선
    discovery_order = list(visited.keys())  # BFS 순서 = 선언 순서 보존
    order: list[str] = []
    ready = [nid for nid in discovery_order if in_degree[nid] == 0]
    while ready:
        # 선언 순서 우선 — discovery_order 인덱스로 정렬
        ready.sort(key=discovery_order.index)
        cur = ready.pop(0)
        order.append(cur)
        # cur가 부모인 자식들의 in_degree 감소
        for child, parents in edges.items():
            if cur in parents:
                in_degree[child] -= 1
                if in_degree[child] == 0 and child not in order and child not in ready:
                    ready.append(child)

    if len(order) != len(visited):
        raise ValueError(f"조상 체인 토폴로지 정렬 실패 (사이클 가능성): leaf={leaf_id}")

    # base-first 순서: order는 root → leaf 순 (Kahn은 그렇게 동작)
    return AncestorChain(layers=[_layer_to_info(visited[nid]) for nid in order])


async def get_ancestors(session: AsyncSession, layer_id: str) -> AncestorChain:
    """조상 체인 조회 (base-first 순서). MySQL 8.0+ CTE for single, Python BFS for multi."""
    # 먼저 leaf 존재 확인
    leaf = await session.get(UnionLayer, layer_id)
    if leaf is None:
        raise KeyError(f"레이어 {layer_id}를 찾을 수 없습니다")

    # multi-parent 모드면 별도 경로
    if _is_multi_parent(leaf):
        return await _get_ancestors_multi(session, layer_id)

    sql = text("""
        WITH RECURSIVE ancestors AS (
            SELECT
                id, name, version, created_at, created_by, sealed,
                sealed_at, project_id,
                parent_id, ubuntu_base, build_recipe, installed_packages,
                content_hash, size_bytes, file_count,
                0 AS depth
            FROM union_layers
            WHERE id = :leaf_id
            UNION ALL
            SELECT
                l.id, l.name, l.version, l.created_at, l.created_by, l.sealed,
                l.sealed_at, l.project_id,
                l.parent_id, l.ubuntu_base, l.build_recipe, l.installed_packages,
                l.content_hash, l.size_bytes, l.file_count,
                a.depth + 1
            FROM ancestors a
            JOIN union_layers l ON l.id = a.parent_id
        )
        SELECT
            id, name, version, created_at, created_by, sealed,
            sealed_at, project_id,
            parent_id, ubuntu_base, build_recipe, installed_packages,
            content_hash, size_bytes, file_count, depth
        FROM ancestors
        ORDER BY depth DESC
    """)

    result = await session.execute(sql, {"leaf_id": layer_id})
    rows = result.mappings().all()

    layers = [
        LayerInfo(
            id=row["id"],
            name=row["name"],
            version=row["version"],
            created_at=row["created_at"],
            created_by=row["created_by"],
            sealed=bool(row["sealed"]),
            sealed_at=row.get("sealed_at"),
            project_id=row.get("project_id"),
            parent_id=row["parent_id"],
            ubuntu_base=row["ubuntu_base"],
            build_recipe=json.loads(row["build_recipe"])
            if isinstance(row["build_recipe"], str)
            else (row["build_recipe"] or {}),
            installed_packages=json.loads(row["installed_packages"])
            if isinstance(row["installed_packages"], str)
            else (row["installed_packages"] or {}),
            content_hash=row["content_hash"],
            size_bytes=row["size_bytes"],
            file_count=row["file_count"],
        )
        for row in rows
    ]
    return AncestorChain(layers=layers)


# ---------------------------------------------------------------------------
# 템플릿 CRUD
# ---------------------------------------------------------------------------


async def create_template(session: AsyncSession, data: CreateTemplateRequest, created_by: str) -> TemplateInfo:
    """새 템플릿 생성. leaf_layer_id가 존재하고 봉인되어 있어야 한다."""
    # leaf 레이어 검증
    leaf = await session.get(UnionLayer, data.leaf_layer_id)
    if leaf is None:
        raise ValueError(f"leaf 레이어 {data.leaf_layer_id}가 존재하지 않습니다")
    if not leaf.sealed:
        raise ValueError(f"leaf 레이어 {data.leaf_layer_id}가 봉인되지 않았습니다. 봉인 후 템플릿을 생성하세요.")

    # (name, version) 중복 확인
    stmt = select(UnionTemplate).where(UnionTemplate.name == data.name, UnionTemplate.version == data.version)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        raise ValueError(f"템플릿 {data.name}@{data.version}은 이미 존재합니다")

    tmpl = UnionTemplate(
        name=data.name,
        version=data.version,
        created_at=datetime.now(UTC),
        created_by=created_by,
        parent_version=data.parent_version,
        ubuntu_base=data.ubuntu_base,
        leaf_layer_id=data.leaf_layer_id,
        note=data.note,
    )
    session.add(tmpl)
    await session.commit()
    await session.refresh(tmpl)
    return _template_to_info(tmpl)


async def list_templates(session: AsyncSession) -> list[TemplateInfo]:
    """템플릿 목록 (이름 오름차순, 버전 내림차순)."""
    stmt = select(UnionTemplate).order_by(UnionTemplate.name.asc(), UnionTemplate.version.desc())
    result = await session.execute(stmt)
    return [_template_to_info(tmpl) for tmpl in result.scalars()]


async def get_dependents(session: AsyncSession, layer_id: str) -> list[LayerInfo]:
    """직접 자식 레이어 목록 (최신순). single + multi 모두 검색.

    single 자식: parent_id == layer_id (parent_ids IS NULL)
    multi 자식: JSON_CONTAINS(parent_ids, '"layer_id"')  (parent_id IS NULL)
    """
    parent = await session.get(UnionLayer, layer_id)
    if parent is None:
        raise KeyError(f"레이어 {layer_id}를 찾을 수 없습니다")

    # single 자식
    single_stmt = select(UnionLayer).where(UnionLayer.parent_id == layer_id)
    single_result = await session.execute(single_stmt)
    children = list(single_result.scalars())

    # multi 자식 — JSON 배열 포함 검색
    multi_candidates = await session.execute(select(UnionLayer).where(UnionLayer.parent_ids.is_not(None)))
    for cand in multi_candidates.scalars():
        if cand.parent_ids and layer_id in cand.parent_ids:
            children.append(cand)

    children.sort(key=lambda c: c.created_at, reverse=True)
    return [_layer_to_info(row) for row in children]


async def delete_layer(session: AsyncSession, layer_id: str) -> None:
    """레이어 삭제 (GC). 자식(single+multi)/템플릿 참조/활성 마운트가 있으면 ValueError.

    multi 자식의 경우 parent_ids 배열에 layer_id가 포함된 모든 레이어가 차단 사유 —
    즉 부모 두 개 모두 삭제 차단됨.
    """
    from sqlalchemy import func

    layer = await session.get(UnionLayer, layer_id)
    if layer is None:
        raise KeyError(f"레이어 {layer_id}를 찾을 수 없습니다")

    # single 자식 확인 (parent_ids IS NULL인 자식)
    single_count_result = await session.execute(
        select(func.count()).select_from(UnionLayer).where(UnionLayer.parent_id == layer_id)
    )
    if single_count_result.scalar_one() > 0:
        raise ValueError("하위 레이어가 존재하여 삭제할 수 없습니다")

    # multi 자식 확인 (JSON 배열에 layer_id 포함). MySQL/MariaDB JSON_CONTAINS 사용.
    multi_count_result = await session.execute(
        select(func.count())
        .select_from(UnionLayer)
        .where(func.json_contains(UnionLayer.parent_ids, json.dumps(layer_id)))
    )
    if multi_count_result.scalar_one() > 0:
        raise ValueError("멀티-부모 하위 레이어가 본 레이어를 참조하여 삭제할 수 없습니다")

    # 템플릿 참조 확인
    tmpl_count_result = await session.execute(
        select(func.count()).select_from(UnionTemplate).where(UnionTemplate.leaf_layer_id == layer_id)
    )
    if tmpl_count_result.scalar_one() > 0:
        raise ValueError("템플릿이 참조하여 삭제할 수 없습니다")

    # 활성 마운트 확인
    mount_count_result = await session.execute(
        select(func.count())
        .select_from(UnionUserMount)
        .where(UnionUserMount.leaf_layer_id == layer_id, UnionUserMount.unmounted_at.is_(None))
    )
    if mount_count_result.scalar_one() > 0:
        raise ValueError("활성 마운트가 존재하여 삭제할 수 없습니다")

    await session.delete(layer)
    await session.commit()


async def get_template(session: AsyncSession, name: str, version: int) -> TemplateInfo | None:
    """템플릿 상세 + 조상 체인 포함."""
    stmt = select(UnionTemplate).where(UnionTemplate.name == name, UnionTemplate.version == version)
    tmpl = (await session.execute(stmt)).scalar_one_or_none()
    if tmpl is None:
        return None

    # resolved_stack: leaf → 조상 체인
    try:
        chain = await get_ancestors(session, tmpl.leaf_layer_id)
        stack = chain.layers
    except Exception:
        stack = None

    return _template_to_info(tmpl, stack=stack)


async def delete_template(session: AsyncSession, name: str, version: int) -> bool:
    """템플릿 삭제. 미존재 시 False(멱등), 삭제 성공 시 True.

    템플릿은 마운트와 직접 연결되지 않으므로(마운트는 leaf_layer_id를 직접 참조)
    삭제 차단 사유가 없다. 멱등 처리하여 cleanup 흐름을 단순화한다.
    """
    stmt = select(UnionTemplate).where(UnionTemplate.name == name, UnionTemplate.version == version)
    tmpl = (await session.execute(stmt)).scalar_one_or_none()
    if tmpl is None:
        return False
    await session.delete(tmpl)
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# 사용자 마운트 추적
# ---------------------------------------------------------------------------


def _mount_to_info(mount: UnionUserMount) -> MountInfo:
    return MountInfo(
        id=mount.id,
        user_id=mount.user_id,
        vm_hostname=mount.vm_hostname,
        leaf_layer_id=mount.leaf_layer_id,
        mounted_at=mount.mounted_at,
        unmounted_at=mount.unmounted_at,
    )


async def record_mount(session: AsyncSession, user_id: str, vm_hostname: str, leaf_layer_id: str) -> MountInfo:
    """마운트 기록 추가. max_concurrent_mounts 초과 시 HTTPException(409) 발생."""
    from fastapi import HTTPException

    leaf = await session.get(UnionLayer, leaf_layer_id)
    if leaf is None:
        raise ValueError(f"레이어 {leaf_layer_id}가 존재하지 않습니다")

    if leaf.max_concurrent_mounts is not None:
        active_count_result = await session.execute(
            select(func.count())
            .select_from(UnionUserMount)
            .where(UnionUserMount.leaf_layer_id == leaf_layer_id, UnionUserMount.unmounted_at.is_(None))
        )
        if active_count_result.scalar_one() >= leaf.max_concurrent_mounts:
            raise HTTPException(status_code=409, detail="concurrent mount limit reached")

    mount = UnionUserMount(
        user_id=user_id,
        vm_hostname=vm_hostname,
        leaf_layer_id=leaf_layer_id,
        mounted_at=datetime.now(UTC),
    )
    session.add(mount)
    await session.commit()
    await session.refresh(mount)
    return _mount_to_info(mount)


async def record_unmount(session: AsyncSession, mount_id: int, user_id: str) -> MountInfo:
    """마운트 해제 기록 (unmounted_at 설정)."""
    mount = await session.get(UnionUserMount, mount_id)
    if mount is None:
        raise KeyError(f"마운트 {mount_id}를 찾을 수 없습니다")
    if mount.user_id != user_id:
        raise PermissionError("본인의 마운트만 해제할 수 있습니다")
    if mount.unmounted_at is not None:
        raise ValueError("이미 해제된 마운트입니다")

    mount.unmounted_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(mount)
    return _mount_to_info(mount)


async def get_storage_stats(session: AsyncSession) -> StorageStats:
    """레이어 스토리지 사용량 집계 (전체)."""
    result = await session.execute(
        select(
            func.count(UnionLayer.id).label("total_layers"),
            func.sum(case((UnionLayer.sealed == True, 1), else_=0)).label("sealed_layers"),  # noqa: E712
            func.coalesce(func.sum(UnionLayer.size_bytes), 0).label("total_size_bytes"),
            func.coalesce(func.sum(UnionLayer.file_count), 0).label("total_file_count"),
        )
    )
    row = result.one()
    return StorageStats(
        total_layers=row.total_layers or 0,
        sealed_layers=row.sealed_layers or 0,
        total_size_bytes=row.total_size_bytes or 0,
        total_file_count=row.total_file_count or 0,
    )
