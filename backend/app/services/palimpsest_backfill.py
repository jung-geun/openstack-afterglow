"""기존 레이어 artifact 의 blob digest 백필.

백엔드 컨테이너는 Manila share 를 마운트하지 않으므로 `.sqsh` 바이트를 직접 읽을 수 없다.
**임시 Builder VM 한 대**(`builder_vm.create_ephemeral_vm`)를 띄워 share 를 RO 로 잠깐씩
마운트해 해시를 뜨고, 배치가 끝나면 VM 을 정리한다.

> 상주 Builder VM 을 쓰지 않는 이유: `builder_vm.py` 는 "Ephemeral(빌드별 임시) 경로만 지원"
> 하며 상주 경로는 코드에서 제거됐다. `afterglow.conf.example` 의 `[builder] persistent_server_id`
> / `ssh_host` / `ssh_private_key` 는 `config.py` 에 대응 필드가 없는 **낡은 문서**다.

원칙:
- 실패는 `digest_state='failed'` + 사유로 남기고 다음 artifact 로 넘어간다. 한 건의 실패가
  배치 전체를 죽이지 않는다.
- **digest 가 없어도 레이어 소비는 계속 가능해야 한다** — 백필은 허브/번들 자격을 줄 뿐이다.
- Manila 가 돌려주는 export path 는 외부 입력으로 취급한다(CLAUDE.md §1): 화이트리스트
  정규식 검증 + `shlex.quote` 이중 방어.
- access rule 과 VM 은 `finally` 에서 반드시 회수한다.
"""

from __future__ import annotations

import asyncio
import logging
import shlex

from sqlalchemy import select

from app.database import get_session_factory
from app.models.db import LayerArtifact
from app.services import manila, ssh_executor
from app.services.builder_vm import EphemeralBuilderVM, create_ephemeral_vm, delete_ephemeral_vm
from app.services.keystone import get_service_project_connection
from app.services.palimpsest_digest import (
    DIGEST_FAILED,
    DIGEST_PENDING,
    DIGEST_READY,
    parse_digest_sentinels,
)
from app.services.palimpsest_layers import recompute_descendant_chain_ids
from app.services.recipe_blocks import _NFS_EXPORT_RE, _SQSH_FILENAME_RE

_logger = logging.getLogger(__name__)

_SSH_TIMEOUT_SECONDS = 600
_MAX_BATCH = 100


class BackfillError(RuntimeError):
    """백필 전제 조건이 갖춰지지 않았거나 한 건의 해시가 실패했다."""


def build_hash_command(export_path: str, sqsh_filename: str, layer_name: str) -> str:
    """빌더 VM 에서 실행할 해시 명령. 출력은 빌드 경로와 **같은 sentinel 포맷**이다.

    포맷을 맞춰 `parse_digest_sentinels` 를 그대로 재사용한다 — 파서가 두 벌 존재하면
    한쪽만 고쳐지는 사고가 난다.

    export_path 는 Manila API 응답이고 sqsh_filename 은 DB 값이다. 둘 다 셸에 도달하므로
    화이트리스트 검증 후 `shlex.quote` 한다(CLAUDE.md §1 — 외부 시스템 반환값도 불신).
    """
    if not _NFS_EXPORT_RE.match(export_path):
        raise BackfillError(f"허용되지 않는 export path 형식: {export_path!r}")
    if not _SQSH_FILENAME_RE.match(sqsh_filename):
        raise BackfillError(f"허용되지 않는 sqsh 파일명: {sqsh_filename!r}")

    export = shlex.quote(export_path)
    sqsh = shlex.quote(sqsh_filename)
    layer = shlex.quote(layer_name)
    return (
        "set -euo pipefail; "
        'MP="$(mktemp -d /tmp/palimpsest-backfill.XXXXXX)"; '
        'cleanup() { sudo -n umount "$MP" 2>/dev/null || true; rmdir "$MP" 2>/dev/null || true; }; '
        "trap cleanup EXIT; "
        f'sudo -n mount -t nfs4 -o ro,nolock {export} "$MP"; '
        f'F="$MP/images/"{sqsh}; '
        'S="$(sha256sum "$F" | awk \'{print $1}\')"; '
        'M="$(md5sum "$F" | awk \'{print $1}\')"; '
        'Z="$(stat -c %s "$F")"; '
        f'echo "::AFTERGLOW::DIGEST::layer="{layer}" sha256=$S md5=$M size=$Z"'
    )


async def _hash_one(conn, vm: EphemeralBuilderVM, row: LayerArtifact) -> dict:
    """artifact 한 건의 digest 를 구한다. access rule 은 반드시 회수한다."""
    access_id: str | None = None
    try:
        rule = await asyncio.to_thread(
            manila.ensure_nfs_access_rule,
            conn,
            row.share_id,
            vm.internal_ip,
            "ro",
            root_squash=False,
            sec_flavor="sys",
        )
        access_id = rule["access_id"]
        exports = await asyncio.to_thread(manila.get_export_locations, conn, row.share_id)
        if not exports:
            raise BackfillError(f"share {row.share_id} 의 export location 이 없습니다")

        command = build_hash_command(exports[0], row.sqsh_filename, row.name)
        code, stdout, stderr = await ssh_executor.run_command(
            vm.host, vm.key_path, command, username=vm.username, timeout=_SSH_TIMEOUT_SECONDS
        )
        if code != 0:
            raise BackfillError(f"빌더 VM 해시 명령 실패(exit={code}): {stderr.strip()[:200]}")

        report = parse_digest_sentinels(stdout).get(row.name)
        if report is None:
            raise BackfillError("빌더 VM 출력에서 digest sentinel 을 찾지 못했습니다")
        return {"ok": True, "report": report}
    except Exception as exc:  # noqa: BLE001 — 한 건 실패가 배치를 죽이지 않는다
        _logger.warning("[palimpsest_backfill] artifact=%s 실패: %s", row.id, exc)
        return {"ok": False, "error": str(exc)[:255]}
    finally:
        if access_id:
            try:
                await asyncio.to_thread(manila.revoke_access_rule, conn, row.share_id, access_id)
            except Exception:
                _logger.warning(
                    "[palimpsest_backfill] access rule 회수 실패: share=%s access=%s",
                    row.share_id,
                    access_id,
                    exc_info=True,
                )


async def _refresh_chain_ids(factory) -> int:
    """digest 가 채워진 루트부터 chain_id 를 아래로 다시 흘려보낸다."""
    updated = 0
    async with factory() as session:
        roots = (
            (
                await session.execute(
                    select(LayerArtifact).where(
                        LayerArtifact.parent_id.is_(None),
                        LayerArtifact.blob_digest.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for root in roots:
            if not root.chain_id:
                root.chain_id = root.blob_digest
                updated += 1
            updated += await recompute_descendant_chain_ids(session, root.id)
        await session.commit()
    return updated


async def backfill_digests(*, limit: int = 20, retry_failed: bool = False) -> dict:
    """`digest_state='pending'` artifact 들의 digest 를 채운다.

    `retry_failed=True` 면 이전에 실패한 건도 다시 시도한다.
    반환: `{"scanned", "updated", "failed", "chain_updated", "details"}`
    """
    limit = max(1, min(int(limit), _MAX_BATCH))
    factory = get_session_factory()
    if factory is None:
        raise BackfillError("DB 연결이 초기화되지 않았습니다")

    states = [DIGEST_PENDING, DIGEST_FAILED] if retry_failed else [DIGEST_PENDING]
    async with factory() as session:
        target_ids = list(
            (
                await session.execute(
                    select(LayerArtifact.id)
                    .where(LayerArtifact.digest_state.in_(states))
                    .order_by(LayerArtifact.id)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    if not target_ids:
        return {"scanned": 0, "updated": 0, "failed": 0, "chain_updated": 0, "details": []}

    conn = await asyncio.to_thread(get_service_project_connection)
    vm: EphemeralBuilderVM | None = None
    details: list[dict] = []
    updated = 0
    failed = 0
    try:
        # 배치 전체를 VM 한 대로 처리한다 — artifact 마다 VM 을 띄우면 비용이 선형으로 는다.
        vm = await create_ephemeral_vm(conn)
        _logger.info("[palimpsest_backfill] 임시 빌더 VM 준비: %s (%d건 대상)", vm.server_id, len(target_ids))

        for artifact_id in target_ids:
            async with factory() as session:
                row = await session.get(LayerArtifact, artifact_id)
                if row is None:
                    continue
                result = await _hash_one(conn, vm, row)
                if result["ok"]:
                    report = result["report"]
                    row.blob_digest = report.blob_digest
                    row.blob_md5 = report.blob_md5
                    if report.size_bytes is not None:
                        row.size_bytes = report.size_bytes
                    row.digest_state = DIGEST_READY
                    updated += 1
                    details.append({"artifact_id": artifact_id, "name": row.name, "digest": report.blob_digest})
                else:
                    row.digest_state = DIGEST_FAILED
                    failed += 1
                    details.append({"artifact_id": artifact_id, "name": row.name, "error": result["error"]})
                await session.commit()
    finally:
        if vm is not None:
            await delete_ephemeral_vm(conn, vm.server_id, vm.fip_id)

    chain_updated = await _refresh_chain_ids(factory)

    _logger.info(
        "[palimpsest_backfill] scanned=%d updated=%d failed=%d chain_updated=%d",
        len(target_ids),
        updated,
        failed,
        chain_updated,
    )
    return {
        "scanned": len(target_ids),
        "updated": updated,
        "failed": failed,
        "chain_updated": chain_updated,
        "details": details,
    }
