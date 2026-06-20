"""squashfs NFS 레이어 빌드 + 소비 인스턴스 오케스트레이터.

빌드 흐름:
  NFS RW share → Neutron port(IP 예약) → NFS access rule(RW) →
  cloud-init user_data(squashfs 빌드) → Nova server →
  SHUTOFF 폴링 → sentinel grep → 성공/실패 처리

소비 흐름:
  NFS RO share export 조회 → cloud-init(layer-activate.sh 주입) →
  Neutron port → NFS access rule(RO) → Nova server 생성 → DB 기록
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import textwrap
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.config import get_settings
from app.services import manila, neutron, nova
from app.services.builder_vm import _ensure_ephemeral_keypair
from app.services.cloud_init_builder import render_user_data
from app.services.keystone import get_service_project_connection
from app.services.recipe_blocks import squashfs_python_layer, squashfs_uv_layer

_logger = logging.getLogger(__name__)

_SHUTOFF_POLL_INTERVAL = 15
_SHUTOFF_MAX_WAIT = 3600
_SUCCESS_SENTINEL = "::AFTERGLOW::SUCCESS::"
_FAILURE_SENTINEL = "::AFTERGLOW::FAILURE::"

# 화이트리스트 정규식
_LAYER_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.+\-]*$")
_NFS_EXPORT_RE = re.compile(r"^[0-9a-zA-Z.\[\]:/_\-]+$")


# ---------------------------------------------------------------------------
# render_user_data 프로토콜을 충족하는 가상 레시피 (ORM 불필요)
# ---------------------------------------------------------------------------


@dataclass
class _LayerRecipe:
    """squashfs 빌드용 가상 레시피 — render_user_data 인터페이스 충족."""

    share_proto: str = "NFS"
    commands: list[dict] = field(default_factory=list)
    apt_packages: list[str] = field(default_factory=list)
    cephx_id: str | None = None
    cephx_key: str | None = None
    base_image_id: str | None = None


# ---------------------------------------------------------------------------
# layer-activate.sh 원본 (layers/vm/layer-activate.sh 와 동기화 유지)
# base64 인코딩 후 cloud-init write_files에 주입
# ---------------------------------------------------------------------------

_LAYER_ACTIVATE_SH = """\
#!/usr/bin/env bash
# layer-activate.sh — squashfs 레이어 마운트 + OverlayFS 합성 (VM 측)
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "사용법: $0 <profile-name>" >&2
    exit 1
fi

_validate_name() {
    local val="$1" kind="$2"
    if ! [[ "$val" =~ ^[a-z0-9][a-z0-9.+\\-]*$ ]]; then
        echo "오류: 유효하지 않은 ${kind}: '${val}'" >&2
        exit 1
    fi
}

PROFILE="$1"
_validate_name "$PROFILE" "profile-name"

NFS_MOUNT="${NFS_MOUNT:-/mnt/nfs-layers}"
SQSH_BASE="${SQSH_BASE:-/mnt/sqsh}"
CACHE_DIR="${CACHE_DIR:-/var/cache/layers}"
LOCAL_UPPER="${LOCAL_UPPER:-/var/lib/overlay/upper}"
LOCAL_WORK="${LOCAL_WORK:-/var/lib/overlay/work}"
OVERLAY_TARGET="${OVERLAY_TARGET:-/usr}"
LOCAL_PROFILE_DIR="${LOCAL_PROFILE_DIR:-/etc/afterglow/layers}"

LOG="/var/log/layer-activate.log"
exec >> "$LOG" 2>&1
echo "[$(date)] layer-activate 시작: profile=${PROFILE} target=${OVERLAY_TARGET}"

mkdir -p "$SQSH_BASE" "$CACHE_DIR" "$LOCAL_UPPER" "$LOCAL_WORK"

LOCAL_CONF="${LOCAL_PROFILE_DIR}/${PROFILE}.conf"
NFS_CONF="${NFS_MOUNT}/profiles/${PROFILE}.conf"
if [ -f "$LOCAL_CONF" ]; then
    PROFILE_FILE="$LOCAL_CONF"
elif [ -f "$NFS_CONF" ]; then
    PROFILE_FILE="$NFS_CONF"
else
    echo "[ERROR] 프로필 파일 없음: ${LOCAL_CONF} 및 ${NFS_CONF}" >&2; exit 1
fi

LAYERS=()
while IFS= read -r line; do
    line="${line%%#*}"
    line="${line//[[:space:]]/}"
    [ -z "$line" ] && continue
    _validate_name "$line" "layer"
    LAYERS+=("$line")
done < "$PROFILE_FILE"

[ "${#LAYERS[@]}" -eq 0 ] && echo "[ERROR] 레이어 없음" >&2 && exit 1
echo "[$(date)] 레이어 목록: ${LAYERS[*]}"

LOWER_DIRS=""
for LAYER in "${LAYERS[@]}"; do
    SQSH_NFS="${NFS_MOUNT}/images/${LAYER}.sqsh"
    SQSH_CACHE="${CACHE_DIR}/${LAYER}.sqsh"
    MOUNT_POINT="${SQSH_BASE}/${LAYER}"

    if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        LOWER_DIRS="${LOWER_DIRS:+${LOWER_DIRS}:}${MOUNT_POINT}"; continue
    fi
    mkdir -p "$MOUNT_POINT"

    if [ -f "$SQSH_NFS" ]; then
        _nfs_size="$(stat -c%s "$SQSH_NFS" 2>/dev/null || echo 0)"
        _cache_size="$(stat -c%s "$SQSH_CACHE" 2>/dev/null || echo -1)"
        if [ ! -f "$SQSH_CACHE" ] || \\
           [ "$SQSH_NFS" -nt "$SQSH_CACHE" ] || \\
           [ "$_nfs_size" != "$_cache_size" ]; then
            cp "$SQSH_NFS" "${SQSH_CACHE}.tmp" 2>/dev/null \\
                && mv "${SQSH_CACHE}.tmp" "$SQSH_CACHE" || true
        fi
    fi

    if [ -f "$SQSH_CACHE" ]; then
        SQSH_SRC="$SQSH_CACHE"
    elif [ -f "$SQSH_NFS" ]; then
        SQSH_SRC="$SQSH_NFS"
    else
        echo "[ERROR] 이미지 없음: ${LAYER}" >&2; exit 1
    fi

    mount -t squashfs "$SQSH_SRC" "$MOUNT_POINT" -o ro
    echo "[$(date)] 마운트 완료: ${LAYER} → ${MOUNT_POINT}"
    LOWER_DIRS="${LOWER_DIRS:+${LOWER_DIRS}:}${MOUNT_POINT}"
done

if mountpoint -q "$OVERLAY_TARGET" 2>/dev/null; then
    _ft="$(findmnt -n -o FSTYPE "$OVERLAY_TARGET" 2>/dev/null || true)"
    if [ "$_ft" = "overlay" ]; then
        echo "[$(date)] 이미 overlay 활성 — 스킵"; exit 0
    fi
fi

[ -d "$LOCAL_WORK" ] && rm -rf "${LOCAL_WORK:?}/"* "${LOCAL_WORK:?}/".* 2>/dev/null || true

mount -t overlay overlay \\
    -o "lowerdir=${LOWER_DIRS}:/,upperdir=${LOCAL_UPPER},workdir=${LOCAL_WORK},metacopy=on" \\
    "$OVERLAY_TARGET"

echo "[$(date)] OverlayFS 활성화 완료: ${OVERLAY_TARGET} ← ${LAYERS[*]}"
"""


# ---------------------------------------------------------------------------
# DB 업데이트 헬퍼
# ---------------------------------------------------------------------------


async def _update_build_db(
    build_id: int | None,
    *,
    status: str | None = None,
    cloud_init_status: str | None = None,
    progress_step: str | None = None,
    progress_pct: int | None = None,
    server_id: str | None = None,
    port_id: str | None = None,
    build_token: str | None = None,
    error_message: str | None = None,
    console_log_excerpt: str | None = None,
    completed: bool = False,
) -> None:
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.db import LayerBuild

    if build_id is None:
        return
    factory = get_session_factory()
    if factory is None:
        return

    async with factory() as session:
        row = (await session.execute(select(LayerBuild).where(LayerBuild.id == build_id))).scalar_one_or_none()
        if row is None:
            return
        terminal = {"complete", "error", "timeout", "cancelled"}
        if row.status in terminal and not completed:
            return
        if status is not None:
            row.status = status
        if cloud_init_status is not None:
            row.cloud_init_status = cloud_init_status
        if progress_step is not None:
            row.progress_step = progress_step
        if progress_pct is not None:
            row.progress_pct = progress_pct
        if server_id is not None:
            row.server_id = server_id
        if port_id is not None:
            row.port_id = port_id
        if build_token is not None:
            row.build_token = build_token
        if error_message is not None:
            row.error_message = error_message
        if console_log_excerpt is not None:
            row.console_log_excerpt = console_log_excerpt
        if completed:
            row.completed_at = datetime.now(UTC)
        await session.commit()


async def _update_consume_db(
    consume_id: int | None,
    *,
    status: str | None = None,
    server_id: str | None = None,
    port_id: str | None = None,
    error_message: str | None = None,
    completed: bool = False,
) -> None:
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.db import LayerConsume

    if consume_id is None:
        return
    factory = get_session_factory()
    if factory is None:
        return

    async with factory() as session:
        row = (await session.execute(select(LayerConsume).where(LayerConsume.id == consume_id))).scalar_one_or_none()
        if row is None:
            return
        if status is not None:
            row.status = status
        if server_id is not None:
            row.server_id = server_id
        if port_id is not None:
            row.port_id = port_id
        if error_message is not None:
            row.error_message = error_message
        if completed:
            row.completed_at = datetime.now(UTC)
        await session.commit()


# ---------------------------------------------------------------------------
# SHUTOFF 폴링 (ephemeral_build._wait_for_shutoff와 동일 패턴)
# ---------------------------------------------------------------------------


async def _wait_for_shutoff(conn, server_id: str, build_db_id: int | None, build_token: str) -> tuple[bool, bool]:
    """VM이 SHUTOFF 될 때까지 폴링. (early_success, early_failure) 반환."""
    waited = 0
    early_success = False
    early_failure = False
    success_tok = f"{_SUCCESS_SENTINEL}{build_token}"
    failure_tok = f"{_FAILURE_SENTINEL}{build_token}"

    while waited < _SHUTOFF_MAX_WAIT:
        await asyncio.sleep(_SHUTOFF_POLL_INTERVAL)
        waited += _SHUTOFF_POLL_INTERVAL

        server = await asyncio.to_thread(conn.compute.get_server, server_id)
        status = (server.status or "").upper()

        if status in ("SHUTOFF", "ERROR"):
            _logger.info("[layer_build] VM %s 상태: %s (elapsed=%ds)", server_id, status, waited)
            return (early_success, early_failure)

        if status == "ACTIVE" and waited > 60:
            try:
                partial = await asyncio.to_thread(nova.get_console_output, conn, server_id, 200)
                if success_tok in partial:
                    early_success = True
                elif failure_tok in partial:
                    early_failure = True
            except Exception:
                pass

        cloud_status = "booting" if waited < 120 else "installing"
        await _update_build_db(build_db_id, cloud_init_status=cloud_status)

    raise TimeoutError(f"VM {server_id}이 {_SHUTOFF_MAX_WAIT}s 내에 SHUTOFF 되지 않았습니다")


# ---------------------------------------------------------------------------
# 소비 VM cloud-init 렌더러
# ---------------------------------------------------------------------------


def render_layer_consume_user_data(
    profile_name: str,
    export_path: str,
    layers: list[str],
) -> str:
    """소비 VM cloud-init YAML 문자열을 반환한다.

    Args:
        profile_name: 레이어 프로필 이름 (^[a-z0-9][a-z0-9.+-]*$). 개행 불허.
        export_path:  Manila NFS share export 경로 (예: 10.30.0.1:/volumes/abc123).
                      개행·셸 메타문자 불허 — 화이트리스트 검증 적용.
        layers:       프로필에 포함된 레이어 이름 목록.
    """
    # 입력 검증 — cloud-init YAML / fstab 개행 주입 방어
    if not _LAYER_NAME_RE.match(profile_name):
        raise ValueError(f"유효하지 않은 프로필 이름: {profile_name!r}")
    if "\n" in profile_name or "\r" in profile_name:
        raise ValueError("프로필 이름에 개행 문자 불허")
    if not _NFS_EXPORT_RE.match(export_path):
        raise ValueError(f"유효하지 않은 NFS export 경로: {export_path!r}")
    if "\n" in export_path or "\r" in export_path:
        raise ValueError("NFS export 경로에 개행 문자 불허")

    activate_b64 = base64.b64encode(_LAYER_ACTIVATE_SH.encode()).decode()

    # layer-activate-auto.sh — /etc/layer-profile 에서 프로필 읽어 activate 실행
    auto_sh = textwrap.dedent("""\
        #!/usr/bin/env bash
        set -euo pipefail
        PROFILE="$(cat /etc/layer-profile | tr -d '[:space:]')"
        exec /usr/local/bin/layer-activate.sh "$PROFILE"
    """)
    auto_b64 = base64.b64encode(auto_sh.encode()).decode()

    # systemd unit (x-systemd.automount 후 실행)
    unit = textwrap.dedent("""\
        [Unit]
        Description=Activate squashfs overlay layers
        After=network-online.target mnt-nfs\\x2dlayers.mount
        Requires=network-online.target mnt-nfs\\x2dlayers.mount
        Before=multi-user.target

        [Service]
        Type=oneshot
        RemainAfterExit=yes
        ExecStart=/usr/local/bin/layer-activate-auto.sh
        StandardOutput=journal
        StandardError=journal

        [Install]
        WantedBy=multi-user.target
    """)
    unit_b64 = base64.b64encode(unit.encode()).decode()

    # fstab 항목 — 화이트리스트 검증된 값만 삽입
    fstab_line = f"{export_path}  /mnt/nfs-layers  nfs4  ro,hard,timeo=50,retrans=3,_netdev,x-systemd.automount  0  0\n"
    fstab_b64 = base64.b64encode(fstab_line.encode()).decode()

    # /etc/layer-profile 내용
    profile_b64 = base64.b64encode((profile_name + "\n").encode()).decode()

    # layers 검증 — 각 레이어 이름 화이트리스트
    for layer in layers:
        if not _LAYER_NAME_RE.match(layer):
            raise ValueError(f"유효하지 않은 레이어 이름: {layer!r}")
        if "\n" in layer or "\r" in layer:
            raise ValueError("레이어 이름에 개행 불허")
    # 로컬 conf 내용: 개행으로 구분된 레이어 이름 목록
    local_conf_content = "\n".join(layers) + "\n"
    local_conf_b64 = base64.b64encode(local_conf_content.encode()).decode()

    parts = [
        "#cloud-config",
        "package_update: true",
        "package_upgrade: false",
        "packages:",
        "  - nfs-common",
        "  - squashfs-tools",
        "write_files:",
        "  - path: /usr/local/bin/layer-activate.sh",
        "    encoding: b64",
        f"    content: {activate_b64}",
        '    permissions: "0755"',
        "  - path: /usr/local/bin/layer-activate-auto.sh",
        "    encoding: b64",
        f"    content: {auto_b64}",
        '    permissions: "0755"',
        "  - path: /etc/layer-profile",
        "    encoding: b64",
        f"    content: {profile_b64}",
        f"  - path: /etc/afterglow/layers/{profile_name}.conf",
        "    encoding: b64",
        f"    content: {local_conf_b64}",
        "  - path: /etc/systemd/system/layer-activate.service",
        "    encoding: b64",
        f"    content: {unit_b64}",
        "  - path: /etc/fstab",
        "    encoding: b64",
        "    append: true",
        f"    content: {fstab_b64}",
        "runcmd:",
        "  - mkdir -p /etc/afterglow/layers",
        "  - mkdir -p /mnt/nfs-layers /mnt/sqsh /var/cache/layers /var/lib/overlay/upper /var/lib/overlay/work",
        "  - systemctl daemon-reload",
        "  - systemctl enable layer-activate.service",
    ]

    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# 메인 빌드 오케스트레이터
# ---------------------------------------------------------------------------


async def run_layer_build(
    build_db_id: int | None,
    layer_name: str,
    kind: str,
    python_version: str | None,
    pip_packages: list[str],
) -> None:
    """squashfs 레이어 빌드 백그라운드 태스크.

    kind="uv"  : uv 바이너리 전용 레이어 빌드.
    kind="python" : CPython 전용 레이어 빌드.
    빌드 성공 시 LayerArtifact DB 레코드를 생성한다.
    """
    settings = get_settings()

    rw_share_id = settings.union_layer_store_rw_share_id
    if not rw_share_id:
        raise RuntimeError(
            "layer-store-rw share ID가 설정되지 않았습니다. config.toml [union] layer_store_rw_share_id 를 설정하세요."
        )

    conn = await asyncio.to_thread(get_service_project_connection)
    build_token = uuid.uuid4().hex
    await _update_build_db(build_db_id, build_token=build_token)

    port_id: str | None = None
    server_id: str | None = None
    rw_access_id: str | None = None

    try:
        # ── 1. 이미지·네트워크 설정 확인 ────────────────────────────────
        image_id = settings.builder_image_id
        if not image_id:
            raise RuntimeError("빌드 이미지 ID가 설정되지 않았습니다 (config.toml [builder] image_id 필요)")
        flavor_id = settings.builder_flavor_id
        if not flavor_id:
            raise RuntimeError("빌드 플레이버 ID가 설정되지 않았습니다 (config.toml [builder] flavor_id 필요)")

        network_id = settings.builder_network_id or settings.default_network_id
        if not network_id:
            raise RuntimeError("빌드 네트워크 ID가 설정되지 않았습니다 (config.toml [builder] network_id 필요)")

        # ── 2. Neutron port 생성 (IP 예약) ────────────────────────────
        await _update_build_db(build_db_id, status="creating_access", progress_step="Neutron port 생성", progress_pct=5)
        port_info = await asyncio.to_thread(
            neutron.create_port, conn, network_id, f"afterglow-layer-build-{build_token[:8]}"
        )
        port_id = port_info["id"]
        fixed_ip = port_info["fixed_ip"]
        await _update_build_db(build_db_id, port_id=port_id)
        _logger.info("[layer_build] port 생성: %s (%s)", port_id, fixed_ip)

        # ── 3. NFS RW access rule 생성 ────────────────────────────────
        rule = await asyncio.to_thread(
            manila.ensure_nfs_access_rule,
            conn,
            rw_share_id,
            fixed_ip,
            "rw",
            root_squash=False,
            sec_flavor="sys",
        )
        rw_access_id = rule["access_id"]
        _logger.info("[layer_build] NFS RW access rule 생성: %s", rw_access_id)

        # ── 4. Export location 조회 ───────────────────────────────────
        export_locations = await asyncio.to_thread(manila.get_export_locations, conn, rw_share_id)
        if not export_locations:
            raise RuntimeError(f"Share {rw_share_id}의 export location이 없습니다")
        export_path = export_locations[0]

        mount_spec = {"share_proto": "NFS", "export_path": export_path}

        # ── 5. cloud-init 렌더 ────────────────────────────────────────
        await _update_build_db(build_db_id, status="creating_vm", progress_step="VM 생성", progress_pct=15)

        if kind == "uv":
            build_script = squashfs_uv_layer(layer_name)
        else:
            build_script = squashfs_python_layer(layer_name, python_version or "", pip_packages or [])
        recipe = _LayerRecipe(
            share_proto="NFS",
            apt_packages=["nfs-common", "squashfs-tools", "curl"],
            commands=[
                {
                    "step": "squashfs_build",
                    "progress_pct": 80,
                    "script": build_script,
                }
            ],
        )
        user_data_str = render_user_data(recipe, mount_spec, build_token)
        user_data_b64 = base64.b64encode(user_data_str.encode()).decode()

        keypair_name = await _ensure_ephemeral_keypair(conn, settings.builder_ssh_key_path)

        # ── 6. Builder VM 생성 ────────────────────────────────────────
        vm_name = f"afterglow-layer-build-{layer_name}-{build_token[:8]}"
        server = await asyncio.to_thread(
            conn.compute.create_server,
            name=vm_name,
            image_id=image_id,
            flavor_id=flavor_id,
            networks=[{"port": port_id}],
            user_data=user_data_b64,
            key_name=keypair_name,
            metadata={
                "union_type": "layer-build",
                "layer_name": layer_name,
                "afterglow_managed": "true",
            },
        )
        server_id = server.id
        await _update_build_db(
            build_db_id,
            server_id=server_id,
            cloud_init_status="booting",
            progress_step="VM 부팅 중",
            progress_pct=20,
        )
        _logger.info("[layer_build] VM 생성: %s (%s)", vm_name, server_id)

        # ── 7. SHUTOFF 폴링 ───────────────────────────────────────────
        await _update_build_db(build_db_id, status="building", progress_step="cloud-init 실행 중", progress_pct=25)
        early_success, early_failure = await _wait_for_shutoff(conn, server_id, build_db_id, build_token)

        # ── 8. sentinel 검증 ──────────────────────────────────────────
        await _update_build_db(build_db_id, cloud_init_status="finalizing", progress_step="결과 검증", progress_pct=90)

        console = ""
        try:
            console = await asyncio.to_thread(nova.get_console_output, conn, server_id, None)
        except Exception:
            _logger.warning("[layer_build] console_output 조회 실패 (early sentinel fallback: %s)", early_success)

        excerpt = console[-2000:] if len(console) > 2000 else console
        await _update_build_db(build_db_id, console_log_excerpt=excerpt)

        success_tok = f"{_SUCCESS_SENTINEL}{build_token}"
        failure_tok = f"{_FAILURE_SENTINEL}{build_token}"

        if success_tok in console or early_success:
            # RW access rule 회수 (레이어 store는 유지, rule만 회수)
            if rw_access_id:
                try:
                    await asyncio.to_thread(manila.revoke_access_rule, conn, rw_share_id, rw_access_id)
                    rw_access_id = None
                    _logger.info("[layer_build] RW access rule 회수 완료")
                except Exception:
                    _logger.warning("[layer_build] RW access rule 회수 실패", exc_info=True)
            await _update_build_db(
                build_db_id,
                status="complete",
                cloud_init_status="success",
                progress_step="빌드 완료",
                progress_pct=100,
                completed=True,
            )
            _logger.info("[layer_build] 빌드 성공: layer=%s", layer_name)

            # LayerArtifact DB 기록
            try:
                from app.database import get_session_factory
                from app.models.db import LayerArtifact

                sqsh_filename = f"{layer_name}-latest.sqsh"  # latest 심링크 파일명
                async with get_session_factory()() as _art_session:
                    artifact = LayerArtifact(
                        name=layer_name,
                        kind=kind,
                        python_version=python_version if kind == "python" else None,
                        sqsh_filename=sqsh_filename,
                        share_id=rw_share_id,
                        build_id=build_db_id,
                    )
                    _art_session.add(artifact)
                    await _art_session.commit()
                _logger.info("[layer_build] LayerArtifact 기록: layer=%s kind=%s", layer_name, kind)
            except Exception:
                _logger.warning("[layer_build] LayerArtifact 기록 실패 (빌드는 성공)", exc_info=True)

        elif failure_tok in console or early_failure:
            raise RuntimeError("cloud-init FAILURE sentinel 감지 — console_log_excerpt 참조")
        else:
            _logger.error("[layer_build] sentinel 부재 (indeterminate): layer=%s", layer_name)
            await _update_build_db(
                build_db_id,
                status="error",
                cloud_init_status="indeterminate",
                progress_step="sentinel 부재",
                error_message="console_output에서 sentinel을 찾을 수 없습니다",
                completed=True,
            )

    except Exception as exc:
        _logger.error("[layer_build] 빌드 실패: layer=%s", layer_name, exc_info=True)
        await _update_build_db(
            build_db_id,
            status="error",
            cloud_init_status="failure",
            progress_step="빌드 실패",
            error_message=str(exc)[:1000],
            completed=True,
        )

    finally:
        # RW access rule 잔여분 회수 (예외 경로)
        if rw_access_id:
            try:
                await asyncio.to_thread(manila.revoke_access_rule, conn, rw_share_id, rw_access_id)
            except Exception:
                _logger.warning("[layer_build] finally: RW rule 회수 실패", exc_info=True)
        # server + port 정리
        if server_id:
            try:
                await asyncio.to_thread(conn.compute.delete_server, server_id)
                _logger.info("[layer_build] server 삭제: %s", server_id)
            except Exception:
                _logger.warning("[layer_build] server 삭제 실패: %s", server_id, exc_info=True)
        if port_id:
            try:
                await asyncio.to_thread(neutron.delete_port, conn, port_id)
                _logger.info("[layer_build] port 삭제: %s", port_id)
            except Exception:
                _logger.warning("[layer_build] port 삭제 실패: %s", port_id, exc_info=True)


# ---------------------------------------------------------------------------
# 소비 인스턴스 생성
# ---------------------------------------------------------------------------


async def run_layer_consume(
    consume_db_id: int | None,
    profile_name: str,
    server_name: str,
    flavor_id: str,
    image_id: str | None = None,
    network_id: str | None = None,
) -> str:
    """소비 인스턴스를 생성하고 server_id를 반환한다.

    NFS RO share에서 레이어를 마운트(OverlayFS)해 즉시 사용 가능한 VM을 생성한다.
    빌드와 달리 sentinel/폴링 없이 VM 생성 후 즉시 반환 — 진행상태는 Nova 인스턴스 상태로 확인.
    """
    settings = get_settings()

    ro_share_id = settings.union_layer_store_ro_share_id
    if not ro_share_id:
        raise RuntimeError(
            "layer-store-ro share ID가 설정되지 않았습니다. config.toml [union] layer_store_ro_share_id 를 설정하세요."
        )

    effective_image_id = image_id or settings.server_image_id
    if not effective_image_id:
        raise RuntimeError("이미지 ID가 설정되지 않았습니다 (config.toml server_image_id 필요)")

    effective_network_id = network_id or settings.default_network_id
    if not effective_network_id:
        raise RuntimeError("네트워크 ID가 설정되지 않았습니다 (config.toml default_network_id 필요)")

    conn = await asyncio.to_thread(get_service_project_connection)

    port_id: str | None = None
    server_id: str | None = None

    try:
        await _update_consume_db(consume_db_id, status="creating")

        # RO share export location 조회
        export_locations = await asyncio.to_thread(manila.get_export_locations, conn, ro_share_id)
        if not export_locations:
            raise RuntimeError(f"RO share {ro_share_id}의 export location이 없습니다")
        export_path = export_locations[0]

        # Neutron port 생성 (IP 예약)
        token = uuid.uuid4().hex[:8]
        port_info = await asyncio.to_thread(
            neutron.create_port, conn, effective_network_id, f"afterglow-layer-consume-{token}"
        )
        port_id = port_info["id"]
        fixed_ip = port_info["fixed_ip"]
        await _update_consume_db(consume_db_id, port_id=port_id)

        # NFS RO access rule 생성
        await asyncio.to_thread(
            manila.ensure_nfs_access_rule,
            conn,
            ro_share_id,
            fixed_ip,
            "ro",
            root_squash=False,
            sec_flavor="sys",
        )

        # 소비 cloud-init 렌더 — LayerProfile DB에서 레이어 목록 조회
        from sqlalchemy import select as _select

        from app.database import get_session_factory
        from app.models.db import LayerProfile

        profile_layers: list[str] = []
        try:
            async with get_session_factory()() as _prof_session:
                _prof_row = (
                    await _prof_session.execute(_select(LayerProfile).where(LayerProfile.name == profile_name))
                ).scalar_one_or_none()
                if _prof_row is not None:
                    profile_layers = list(_prof_row.layers)
        except Exception:
            _logger.warning("[layer_build] LayerProfile 조회 실패, 빈 레이어로 진행", exc_info=True)

        user_data_str = render_layer_consume_user_data(profile_name, export_path, profile_layers)
        user_data_b64 = base64.b64encode(user_data_str.encode()).decode()

        # 소비 VM 생성
        server = await asyncio.to_thread(
            conn.compute.create_server,
            name=server_name,
            image_id=effective_image_id,
            flavor_id=flavor_id,
            networks=[{"port": port_id}],
            user_data=user_data_b64,
            metadata={
                "union_type": "layer-consumer",
                "layer_profile": profile_name,
                "afterglow_managed": "true",
            },
        )
        server_id = server.id
        await _update_consume_db(consume_db_id, server_id=server_id, status="active", completed=True)
        _logger.info("[layer_build] 소비 VM 생성: %s (%s), profile=%s", server_name, server_id, profile_name)
        return server_id

    except Exception as exc:
        _logger.error("[layer_build] 소비 VM 생성 실패: %s", profile_name, exc_info=True)
        await _update_consume_db(
            consume_db_id,
            status="error",
            error_message=str(exc)[:1000],
            completed=True,
        )
        # 실패 시 port 정리 (server는 아직 없거나 생성 도중 실패)
        if port_id and not server_id:
            try:
                await asyncio.to_thread(neutron.delete_port, conn, port_id)
            except Exception:
                _logger.warning("[layer_build] 소비 VM 실패 후 port 정리 실패", exc_info=True)
        raise
