"""Palimpsest 레이어 계보(lineage)·digest 필드 해석 — DB 접근이 필요한 헬퍼.

순수 계산은 `palimpsest_digest`에 있고, 여기에는 세션이 필요한 것만 둔다.

계보 순서 규약(혼동 주의):
- `load_lineage()` 는 **child-first**(자기 자신 → 부모 → … → 루트). 기존
  `layer_ops._artifact_lineage_rows` 와 같은 순서이며 OverlayFS `lowerdir` 조립에 그대로 쓴다
  (`lowerdir` 는 왼쪽이 최상위).
- `load_ancestor_chain()` 는 **root-first**(루트 → … → 자기 자신). chain_id 재귀 계산과
  허브 번들의 `layers[]` 순서가 이쪽이다.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.models.db import LayerArtifact
from app.services.palimpsest_digest import (
    DIGEST_PENDING,
    DIGEST_READY,
    DigestReport,
    build_layer_config,
    compute_chain_id,
    compute_config_digest,
    normalize_digest,
)

_logger = logging.getLogger(__name__)


async def load_lineage(session, artifact) -> list[Any]:
    """직계 자신부터 `parent_id` 체인을 따라 child-first 로 반환한다(사이클 방어)."""
    lineage: list[Any] = []
    seen_ids: set[int] = set()
    current = artifact
    while current is not None:
        artifact_id = getattr(current, "id", None)
        if not isinstance(artifact_id, int) or artifact_id in seen_ids:
            break
        lineage.append(current)
        seen_ids.add(artifact_id)
        parent_id = getattr(current, "parent_id", None)
        if not isinstance(parent_id, int):
            break
        current = await session.get(LayerArtifact, parent_id)
    return lineage


async def load_ancestor_chain(session, artifact) -> list[Any]:
    """루트부터 자기 자신까지 root-first 로 반환한다."""
    return list(reversed(await load_lineage(session, artifact)))


async def resolve_digest_fields(
    session,
    *,
    report: DigestReport | None,
    parent_artifact_id: int | None,
    name: str,
    kind: str,
    ubuntu_base: str | None,
    python_version: str | None,
    pip_packages: list[str] | None,
    apt_packages: list[str] | None,
) -> dict[str, Any]:
    """새 `LayerArtifact` 에 넣을 digest 관련 컬럼 값을 만든다.

    digest 를 확보하지 못하면 `digest_state='pending'` 으로 두고 나머지를 None 으로 남긴다 —
    빌드는 이미 성공했고 digest 는 백필로 채울 수 있다. 여기서 예외를 던져 빌드 기록을
    날리지 않는다.

    부모의 `chain_id` 가 아직 없으면(부모가 백필 대기) 자식 `chain_id` 도 계산하지 않는다.
    임의로 루트 취급하면 서로 다른 스택이 같은 chain_id 를 갖게 되기 때문이다.
    """
    parent_digest: str | None = None
    parent_chain_id: str | None = None
    if parent_artifact_id is not None:
        parent = await session.get(LayerArtifact, parent_artifact_id)
        if parent is not None:
            parent_digest = normalize_digest(getattr(parent, "blob_digest", None))
            parent_chain_id = normalize_digest(getattr(parent, "chain_id", None))

    config_digest = compute_config_digest(
        build_layer_config(
            name=name,
            kind=kind,
            ubuntu_base=ubuntu_base,
            python_version=python_version,
            pip_packages=pip_packages,
            apt_packages=apt_packages,
            parent_digest=parent_digest,
        )
    )

    if report is None:
        return {
            "blob_digest": None,
            "blob_md5": None,
            "config_digest": config_digest,
            "chain_id": None,
            "digest_state": DIGEST_PENDING,
        }

    chain_id: str | None = None
    if parent_artifact_id is None:
        chain_id = compute_chain_id(None, report.blob_digest)
    elif parent_chain_id is not None:
        chain_id = compute_chain_id(parent_chain_id, report.blob_digest)

    return {
        "blob_digest": report.blob_digest,
        "blob_md5": report.blob_md5,
        "config_digest": config_digest,
        "chain_id": chain_id,
        "digest_state": DIGEST_READY,
    }


async def recompute_descendant_chain_ids(session, root_artifact_id: int) -> int:
    """`root_artifact_id` 의 자손들 `chain_id` 를 위에서 아래로 다시 계산한다.

    백필로 부모 digest 가 뒤늦게 채워졌을 때 자식들의 chain_id 를 메우는 용도.
    digest 가 없는 노드에서 하위 탐색을 멈춘다(계산 근거가 없으므로).
    반환값은 갱신한 행 수. 커밋은 호출자 책임.
    """
    updated = 0
    frontier = [root_artifact_id]
    seen: set[int] = set()
    while frontier:
        current_id = frontier.pop()
        if current_id in seen:
            continue
        seen.add(current_id)
        current = await session.get(LayerArtifact, current_id)
        if current is None or not current.chain_id:
            continue
        children = (
            (await session.execute(select(LayerArtifact).where(LayerArtifact.parent_id == current_id))).scalars().all()
        )
        for child in children:
            child_digest = normalize_digest(child.blob_digest)
            if child_digest is None:
                continue
            new_chain = compute_chain_id(current.chain_id, child_digest)
            if child.chain_id != new_chain:
                child.chain_id = new_chain
                updated += 1
            frontier.append(child.id)
    return updated
