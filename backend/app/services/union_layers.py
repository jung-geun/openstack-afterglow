"""Union Mount 레이어 시스템 서비스 레이어.

MySQL 8.0+ WITH RECURSIVE CTE로 조상 체인을 해석한다.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import UnionLayer, UnionTemplate, UnionUserMount
from app.models.union import (
    AncestorChain,
    CreateLayerRequest,
    CreateTemplateRequest,
    LayerInfo,
    MountInfo,
    SealLayerResponse,
    StorageStats,
    TemplateInfo,
)

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
        project_id=getattr(layer, "project_id", None),
        ubuntu_base=layer.ubuntu_base,
        build_recipe=layer.build_recipe or {},
        installed_packages=layer.installed_packages or {},
        content_hash=layer.content_hash,
        size_bytes=layer.size_bytes,
        file_count=layer.file_count,
    )


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


async def create_layer(
    session: AsyncSession,
    data: CreateLayerRequest,
    created_by: str,
    project_id: str | None = None,
) -> LayerInfo:
    """새 레이어 등록. 부모가 있으면 봉인 여부 검증."""
    layer_id = (
        f"sha256:{data.content_hash[len('sha256:') :]}"
        if data.content_hash.startswith("sha256:")
        else data.content_hash
    )

    # 동일 id 중복 확인
    existing = await session.get(UnionLayer, layer_id)
    if existing:
        raise ValueError(f"레이어 {layer_id}는 이미 존재합니다")

    # 부모 검증: 존재 + 봉인 여부
    if data.parent_id:
        parent = await session.get(UnionLayer, data.parent_id)
        if parent is None:
            raise ValueError(f"부모 레이어 {data.parent_id}가 존재하지 않습니다")
        if not parent.sealed:
            raise ValueError(
                f"부모 레이어 {data.parent_id}가 아직 봉인되지 않았습니다. 봉인 후 자식 레이어를 생성하세요."
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
        parent_id=data.parent_id,
        ubuntu_base=data.ubuntu_base,
        build_recipe=data.build_recipe,
        installed_packages=data.installed_packages,
        content_hash=data.content_hash,
        size_bytes=data.size_bytes,
        file_count=data.file_count,
        project_id=effective_project_id,
        sealed_at=None,
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
    """레이어 봉인 (sealed=True + sealed_at 기록)."""
    layer = await session.get(UnionLayer, layer_id)
    if layer is None:
        raise KeyError(f"레이어 {layer_id}를 찾을 수 없습니다")
    if layer.sealed:
        raise ValueError(f"레이어 {layer_id}는 이미 봉인되어 있습니다")

    now = datetime.now(UTC)
    layer.sealed = True
    layer.sealed_at = now
    await session.commit()
    return SealLayerResponse(id=layer.id, sealed=True, sealed_at=now)


async def get_ancestors(session: AsyncSession, layer_id: str) -> AncestorChain:
    """WITH RECURSIVE CTE로 조상 체인 조회 (base-first 순서).

    MySQL 8.0+ 필수.
    """
    # 먼저 leaf 존재 확인
    leaf = await session.get(UnionLayer, layer_id)
    if leaf is None:
        raise KeyError(f"레이어 {layer_id}를 찾을 수 없습니다")

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
            build_recipe=row["build_recipe"] or {},
            installed_packages=row["installed_packages"] or {},
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
    """직접 자식 레이어 목록 (최신순). 부모 레이어 미존재 시 KeyError."""
    parent = await session.get(UnionLayer, layer_id)
    if parent is None:
        raise KeyError(f"레이어 {layer_id}를 찾을 수 없습니다")
    stmt = select(UnionLayer).where(UnionLayer.parent_id == layer_id).order_by(UnionLayer.created_at.desc())
    result = await session.execute(stmt)
    return [_layer_to_info(row) for row in result.scalars()]


async def delete_layer(session: AsyncSession, layer_id: str) -> None:
    """레이어 삭제 (GC). 자식/템플릿 참조/활성 마운트가 있으면 ValueError."""
    from sqlalchemy import func

    layer = await session.get(UnionLayer, layer_id)
    if layer is None:
        raise KeyError(f"레이어 {layer_id}를 찾을 수 없습니다")

    # 자식 레이어 확인
    child_count_result = await session.execute(
        select(func.count()).select_from(UnionLayer).where(UnionLayer.parent_id == layer_id)
    )
    if child_count_result.scalar_one() > 0:
        raise ValueError("하위 레이어가 존재하여 삭제할 수 없습니다")

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
    """마운트 기록 추가."""
    leaf = await session.get(UnionLayer, leaf_layer_id)
    if leaf is None:
        raise ValueError(f"레이어 {leaf_layer_id}가 존재하지 않습니다")

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
