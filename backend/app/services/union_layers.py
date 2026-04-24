"""Union Mount 레이어 시스템 서비스 레이어.

MySQL 8.0+ WITH RECURSIVE CTE로 조상 체인을 해석한다.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import UnionLayer, UnionTemplate, UnionUserMount
from app.models.union import (
    AncestorChain,
    CreateLayerRequest,
    CreateTemplateRequest,
    LayerInfo,
    SealLayerResponse,
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
        parent_id=layer.parent_id,
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


async def create_layer(session: AsyncSession, data: CreateLayerRequest, created_by: str) -> LayerInfo:
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
    limit: int = 50,
    offset: int = 0,
) -> list[LayerInfo]:
    """레이어 목록 (최신순). name 필터 지원."""
    stmt = select(UnionLayer)
    if name:
        stmt = stmt.where(UnionLayer.name == name)
    stmt = stmt.order_by(UnionLayer.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return [_layer_to_info(row) for row in result.scalars()]


async def seal_layer(session: AsyncSession, layer_id: str) -> SealLayerResponse:
    """레이어 봉인 (sealed=True로 업데이트)."""
    layer = await session.get(UnionLayer, layer_id)
    if layer is None:
        raise KeyError(f"레이어 {layer_id}를 찾을 수 없습니다")
    if layer.sealed:
        raise ValueError(f"레이어 {layer_id}는 이미 봉인되어 있습니다")

    layer.sealed = True
    await session.commit()
    return SealLayerResponse(id=layer.id, sealed=True)


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
                parent_id, ubuntu_base, build_recipe, installed_packages,
                content_hash, size_bytes, file_count,
                0 AS depth
            FROM union_layers
            WHERE id = :leaf_id
            UNION ALL
            SELECT
                l.id, l.name, l.version, l.created_at, l.created_by, l.sealed,
                l.parent_id, l.ubuntu_base, l.build_recipe, l.installed_packages,
                l.content_hash, l.size_bytes, l.file_count,
                a.depth + 1
            FROM ancestors a
            JOIN union_layers l ON l.id = a.parent_id
        )
        SELECT
            id, name, version, created_at, created_by, sealed,
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


async def record_mount(session: AsyncSession, user_id: str, vm_hostname: str, leaf_layer_id: str) -> dict:
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
    return {
        "id": mount.id,
        "user_id": mount.user_id,
        "vm_hostname": mount.vm_hostname,
        "leaf_layer_id": mount.leaf_layer_id,
        "mounted_at": mount.mounted_at.isoformat(),
    }
