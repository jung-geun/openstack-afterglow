"""
라이브러리 파일 스토리지 자동 빌드 서비스.

Manila CephFS share 생성 → CephX access rule → 임시 VM(cloud-init) 자동 생성
→ VM 내부에서 패키지 설치 → VM SHUTOFF 감지 → 메타데이터 업데이트 → VM 삭제
"""
import asyncio
import base64
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import openstack

from app.config import get_settings
from app.services import manila, libraries as lib_svc

_logger = logging.getLogger(__name__)

# 빌드 중인 작업 추적 {library_id: {share_id, server_id, status}}
_active_builds: dict[str, dict] = {}

# 설치 스크립트 템플릿 (라이브러리별)
_INSTALL_SCRIPTS: dict[str, str] = {
    "python311": """
apt-get update -qq
apt-get install -y python3.11 python3.11-venv python3-pip
mkdir -p /mnt/share/usr_local
cp -a /usr/local/. /mnt/share/usr_local/
""",
    "torch": """
pip3 install --no-cache-dir --target=/mnt/share/usr_local/lib/python3/dist-packages \
    torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0
""",
    "vllm": """
pip3 install --no-cache-dir --target=/mnt/share/usr_local/lib/python3/dist-packages \
    vllm==0.6.0
""",
    "jupyter": """
pip3 install --no-cache-dir --target=/mnt/share/usr_local/lib/python3/dist-packages \
    jupyterlab==4.2.0 ipykernel
""",
}


def _generate_cloudinit(
    ceph_monitors: str,
    share_path: str,
    cephx_user: str,
    cephx_secret: str,
    library_id: str,
) -> str:
    """빌더 VM용 cloud-init 스크립트 생성."""
    install_script = _INSTALL_SCRIPTS.get(library_id, "echo 'Unknown library'")

    return f"""#!/bin/bash
set -ex
exec > /var/log/union-builder.log 2>&1

echo "[union-builder] Starting library build: {library_id}"

# CephFS 마운트를 위한 패키지 설치
apt-get update -qq
apt-get install -y ceph-common python3-pip

# CephFS 마운트
mkdir -p /mnt/share
echo "{cephx_secret}" > /tmp/ceph.secret
mount -t ceph {ceph_monitors}:{share_path} /mnt/share -o name={cephx_user},secretfile=/tmp/ceph.secret
rm -f /tmp/ceph.secret

echo "[union-builder] CephFS mounted, starting package installation"

# 패키지 설치
{install_script}

# 완료 마커 파일 작성
echo '{{"status": "ready", "built_at": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'", "library": "{library_id}"}}' > /mnt/share/.union_build_complete

# 동기화 및 언마운트
sync
umount /mnt/share

echo "[union-builder] Build complete, shutting down"
poweroff
"""


def get_active_builds() -> dict[str, dict]:
    """현재 진행 중인 빌드 목록 반환."""
    return dict(_active_builds)


async def start_build(
    conn: openstack.connection.Connection,
    library_id: str,
) -> dict:
    """라이브러리 파일 스토리지 자동 빌드 시작.

    Returns: {file_storage_id, server_id, status}
    """
    settings = get_settings()

    if library_id in _active_builds:
        raise RuntimeError(f"이미 빌드 중인 라이브러리: {library_id}")

    lib = lib_svc.get_by_id(library_id)

    # 빌더 설정 확인
    image_id = settings.builder_image_id
    flavor_id = settings.builder_flavor_id
    network_id = settings.builder_network_id or settings.default_network_id
    if not image_id or not flavor_id:
        raise RuntimeError("빌더 VM 설정이 없습니다 (config.toml [builder] image_id, flavor_id 필요)")

    # 1. Manila share 생성
    _logger.info("[builder] Manila share 생성 시작: %s", library_id)
    file_storage = await asyncio.to_thread(
        manila.create_file_storage,
        conn,
        name=f"union-prebuilt-{library_id}",
        size_gb=_get_lib_size(library_id),
        share_network_id=settings.os_manila_share_network_id,
        share_type=settings.os_manila_share_type,
        metadata={
            "union_type": "prebuilt",
            "union_library": library_id,
            "union_version": lib.version,
            "union_status": "building",
        },
    )
    share_id = file_storage.id
    _logger.info("[builder] Share 생성 완료: %s", share_id)

    # 2. CephX access rule 생성
    cephx_user = f"union-builder-{library_id}"
    access_rule = await asyncio.to_thread(
        manila.create_access_rule,
        conn, share_id, cephx_user, "rw", "cephx",
    )
    cephx_secret = access_rule["access_key"]
    _logger.info("[builder] CephX access rule 생성: user=%s", cephx_user)

    # 3. Export location 조회
    export_locations = await asyncio.to_thread(
        manila.get_export_locations, conn, share_id,
    )
    if not export_locations:
        raise RuntimeError(f"Share {share_id}의 export location을 찾을 수 없습니다")
    # CephFS export path: "mon1,mon2,mon3:/volumes/_nogroup/xxx"
    # 모니터 주소와 경로를 분리
    export_path = export_locations[0]
    if ":" in export_path:
        ceph_mons, share_path = export_path.rsplit(":", 1)
    else:
        ceph_mons = settings.ceph_monitors
        share_path = export_path

    # 4. cloud-init 스크립트 생성
    userdata = _generate_cloudinit(
        ceph_monitors=ceph_mons,
        share_path=share_path,
        cephx_user=cephx_user,
        cephx_secret=cephx_secret,
        library_id=library_id,
    )
    userdata_b64 = base64.b64encode(userdata.encode()).decode()

    # 5. 임시 VM 생성 (이미지에서 직접 부팅)
    _logger.info("[builder] 빌더 VM 생성 시작")
    server = await asyncio.to_thread(
        _create_builder_vm, conn, library_id, image_id, flavor_id, network_id, userdata_b64,
    )
    server_id = server.id
    _logger.info("[builder] 빌더 VM 생성 완료: %s", server_id)

    # 빌드 상태 기록
    build_info = {
        "library_id": library_id,
        "file_storage_id": share_id,
        "server_id": server_id,
        "cephx_user": cephx_user,
        "status": "building",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _active_builds[library_id] = build_info

    # 6. 백그라운드 모니터링 시작
    asyncio.create_task(_monitor_build(conn, library_id, share_id, server_id))

    return {
        "file_storage_id": share_id,
        "server_id": server_id,
        "status": "building",
        "library": library_id,
    }


def _get_lib_size(library_id: str) -> int:
    """라이브러리별 적정 share 크기 (GB)."""
    sizes = {"python311": 5, "torch": 20, "vllm": 15, "jupyter": 5}
    return sizes.get(library_id, 20)


def _create_builder_vm(
    conn: openstack.connection.Connection,
    library_id: str,
    image_id: str,
    flavor_id: str,
    network_id: str,
    userdata_b64: str,
) -> object:
    """이미지에서 직접 부팅하는 임시 VM 생성."""
    server = conn.compute.create_server(
        name=f"union-builder-{library_id}",
        image_id=image_id,
        flavor_id=flavor_id,
        networks=[{"uuid": network_id}],
        user_data=userdata_b64,
        metadata={"union_type": "builder", "union_library": library_id},
    )
    # ACTIVE 상태까지 대기 (최대 10분)
    server = conn.compute.wait_for_server(server, status="ACTIVE", wait=600)
    return server


async def _monitor_build(
    conn: openstack.connection.Connection,
    library_id: str,
    share_id: str,
    server_id: str,
):
    """빌더 VM 상태를 모니터링하고 완료 시 정리."""
    _logger.info("[builder] 모니터링 시작: library=%s, server=%s", library_id, server_id)
    try:
        # 최대 30분 대기
        for _ in range(180):
            await asyncio.sleep(10)
            try:
                server = await asyncio.to_thread(conn.compute.get_server, server_id)
                status = server.status
            except Exception:
                _logger.warning("[builder] VM 상태 조회 실패: %s", server_id, exc_info=True)
                continue

            if status == "SHUTOFF":
                _logger.info("[builder] 빌더 VM SHUTOFF 감지, 빌드 완료: %s", library_id)
                # 메타데이터 업데이트
                await asyncio.to_thread(
                    manila.update_share_metadata, conn, share_id,
                    {
                        "union_status": "ready",
                        "union_built_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                # CephX access rule 정리 (빌더용)
                try:
                    rules = await asyncio.to_thread(
                        manila.list_access_rules, conn, share_id,
                    )
                    for rule in rules:
                        if rule.get("access_to", "").startswith("union-builder-"):
                            await asyncio.to_thread(
                                manila.revoke_access_rule, conn, share_id, rule["id"],
                            )
                except Exception:
                    _logger.warning("[builder] CephX rule 정리 실패", exc_info=True)

                # VM 삭제
                try:
                    await asyncio.to_thread(conn.compute.delete_server, server_id, force=True)
                    _logger.info("[builder] 빌더 VM 삭제 완료: %s", server_id)
                except Exception:
                    _logger.warning("[builder] VM 삭제 실패: %s", server_id, exc_info=True)

                if library_id in _active_builds:
                    _active_builds[library_id]["status"] = "complete"
                    del _active_builds[library_id]
                return

            if status == "ERROR":
                _logger.error("[builder] 빌더 VM ERROR 상태: %s", server_id)
                await asyncio.to_thread(
                    manila.update_share_metadata, conn, share_id,
                    {"union_status": "error"},
                )
                try:
                    await asyncio.to_thread(conn.compute.delete_server, server_id, force=True)
                except Exception:
                    pass
                if library_id in _active_builds:
                    _active_builds[library_id]["status"] = "error"
                    del _active_builds[library_id]
                return

        # 타임아웃
        _logger.error("[builder] 빌드 타임아웃 (30분): %s", library_id)
        await asyncio.to_thread(
            manila.update_share_metadata, conn, share_id,
            {"union_status": "timeout"},
        )
        try:
            await asyncio.to_thread(conn.compute.delete_server, server_id, force=True)
        except Exception:
            pass
        if library_id in _active_builds:
            del _active_builds[library_id]

    except Exception:
        _logger.error("[builder] 모니터링 예외: %s", library_id, exc_info=True)
        if library_id in _active_builds:
            del _active_builds[library_id]
