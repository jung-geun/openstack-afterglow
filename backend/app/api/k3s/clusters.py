"""k3s 클러스터 CRUD + SSE 생성 엔드포인트."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio
import logging
import random
import string
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import InterfaceError, OperationalError
from starlette.requests import Request

from app.api.common.activity_recorder import rec
from app.api.deps import CacheMode, cache_mode, get_os_conn, get_token_info
from app.config import get_settings
from app.database import mark_db_unhealthy
from app.models.k3s import (
    CreateK3sClusterRequest,
    K3sAttachInterfaceRequest,
    K3sClusterInfo,
    K3sInterfaceInfo,
    K3sProgressMessage,
    K3sProgressStep,
    ScaleK3sClusterRequest,
)
from app.services import cinder, k3s_cloudinit, k3s_kube, keystone, neutron, nova, octavia
from app.services import k3s_db as k3s_cluster
from app.services.cache import cached_call, invalidate, ttl_normal, ttl_slow
from app.services.cache import invalidation as cache_invalidation
from app.services.cache import keys as cache_keys

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
_logger = logging.getLogger(__name__)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "Content-Encoding": "identity",
}


def _rand_suffix(length: int = 5) -> str:
    """K8s 스타일 랜덤 suffix (소문자+숫자). 매 생성마다 고유한 리소스 이름 보장."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _cluster_to_info(c: dict) -> K3sClusterInfo:
    agent_vm_ids = c.get("agent_vm_ids") or []
    if isinstance(agent_vm_ids, str):
        import json

        try:
            agent_vm_ids = json.loads(agent_vm_ids)
        except Exception:
            agent_vm_ids = []
    return K3sClusterInfo(
        id=c.get("id", ""),
        name=c.get("name", ""),
        status=c.get("status", ""),
        status_reason=c.get("status_reason") or None,
        server_vm_id=c.get("server_vm_id") or None,
        agent_vm_ids=agent_vm_ids,
        agent_count=int(c.get("agent_count") or 0),
        api_address=c.get("api_address") or None,
        server_ip=c.get("server_ip") or None,
        network_id=c.get("network_id") or None,
        key_name=c.get("key_name") or None,
        k3s_version=c.get("k3s_version") or None,
        created_at=c.get("created_at") or None,
        updated_at=c.get("updated_at") or None,
        deleted_at=c.get("deleted_at") or None,
        deleted_by_user_id=c.get("deleted_by_user_id") or None,
        deleted_reason=c.get("deleted_reason") or None,
        occm_enabled=bool(c.get("occm_enabled", False)),
        plugins_enabled=c.get("plugins_enabled") or {},
        api_lb_id=c.get("api_lb_id") or None,
        api_fip_id=c.get("api_fip_id") or None,
        api_fip_address=c.get("api_fip_address") or None,
        master_count=int(c.get("master_count") or 1),
        stampede_enabled=bool(c.get("stampede_enabled", False)),
    )


@router.get("", response_model=list[K3sClusterInfo])
async def list_k3s_clusters(
    token_info: dict = Depends(get_token_info),
    include_deleted: bool = Query(default=False),
    cm: CacheMode = Depends(cache_mode),
):
    project_id = token_info["project_id"]
    sub = "all" if include_deleted else None
    cache_key = cache_keys.project_key("k3s", project_id, "clusters", sub=sub)

    async def _fetch():
        try:
            clusters = await k3s_cluster.list_clusters(project_id, include_deleted=include_deleted)
        except (OperationalError, InterfaceError):
            _logger.warning("k3s 클러스터 목록 DB 조회 실패 — 빈 목록 반환", exc_info=True)
            mark_db_unhealthy()
            return []
        return [_cluster_to_info(c) for c in clusters]

    try:
        return await cached_call(cache_key, ttl_normal(), _fetch, enabled=cm.enabled, refresh=cm.refresh)
    except (OperationalError, InterfaceError):
        _logger.warning("k3s 클러스터 목록 DB 조회 실패 — 빈 목록 반환", exc_info=True)
        mark_db_unhealthy()
        return []


@router.get("/{cluster_id}", response_model=K3sClusterInfo)
async def get_k3s_cluster(
    cluster_id: str,
    token_info: dict = Depends(get_token_info),
    cm: CacheMode = Depends(cache_mode),
):
    project_id = token_info["project_id"]
    cache_key = cache_keys.project_key("k3s", project_id, "clusters", sub=cluster_id)

    async def _fetch():
        cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
        if not cluster:
            raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")
        return _cluster_to_info(cluster)

    return await cached_call(cache_key, ttl_normal(), _fetch, enabled=cm.enabled, refresh=cm.refresh)


@router.api_route("/{cluster_id}/kubeconfig", methods=["GET", "HEAD"])
async def download_kubeconfig(
    request: Request,
    cluster_id: str,
    token_info: dict = Depends(get_token_info),
    cm: CacheMode = Depends(cache_mode),
):
    """kubeconfig YAML 파일 다운로드. 아직 준비되지 않으면 404.

    매 호출마다 audit log 기록 — 토큰 탈취 시 다운로드 추적이 가능하도록.
    None 결과는 캐시하지 않는다 (초기화 중인 클러스터 UX 보호).
    """
    import json as _json

    from app.services.cache import get_backend

    project_id = token_info["project_id"]
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")

    cache_key = cache_keys.project_key("k3s", project_id, "clusters", sub=f"{cluster_id}:kubeconfig")
    kubeconfig: bytes | None = None

    # 캐시 조회 (캐시 활성 + 강제 갱신 아님일 때만)
    if cm.enabled and not cm.refresh:
        try:
            backend = get_backend()
            cached_raw = await backend.get(cache_key)
            if cached_raw is not None:
                kubeconfig = _json.loads(cached_raw).encode()
        except Exception:
            pass  # 캐시 장애 → fallthrough

    if kubeconfig is None:
        try:
            kubeconfig = await k3s_cluster.get_kubeconfig(project_id, cluster_id)
        except Exception as e:
            _logger.error("kubeconfig 복호화 실패: %s", e)
            raise HTTPException(status_code=500, detail="kubeconfig 복호화에 실패했습니다. 관리자에게 문의하세요.")

        # None이 아닐 때만, 캐시 활성 시에만 저장
        if kubeconfig is not None and cm.enabled:
            try:
                backend = get_backend()
                await backend.set(cache_key, _json.dumps(kubeconfig.decode()), ttl_slow())
            except Exception:
                pass  # 캐시 장애 → silent fail

    if not kubeconfig:
        raise HTTPException(
            status_code=404, detail="kubeconfig가 아직 준비되지 않았습니다. 클러스터가 초기화 중입니다."
        )

    cluster_name = cluster.get("name", cluster_id)

    # audit log — HEAD 는 보통 브라우저 사전 요청이라 GET 일 때만 기록
    if request.method == "GET":
        try:
            from app.rate_limit import _get_real_ip

            source_ip = _get_real_ip(request)
            await rec(
                token_info,
                None,
                resource_type="k3s_cluster",
                action="kubeconfig_download",
                resource_id=cluster_id,
                resource_name=cluster_name,
                extra={"source_ip": source_ip},
            )
        except Exception:
            _logger.warning("kubeconfig 다운로드 audit 기록 실패", exc_info=True)

    return Response(
        content=kubeconfig,
        media_type="application/yaml",
        headers={"Content-Disposition": f'attachment; filename="kubeconfig-{cluster_name}.yaml"'},
    )


@router.post("/async")
@limiter.limit("5/minute")
async def create_k3s_cluster_async(
    request: Request,
    req: CreateK3sClusterRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """k3s 클러스터 생성 — SSE 스트리밍 진행률 반환."""
    token_info_obj = getattr(request.state, "token_info", None)
    project_id = conn._afterglow_project_id
    s = get_settings()

    # 설정 검증
    os_type = req.os_type  # "ubuntu" | "fcos"
    if os_type == "fcos":
        server_image_id = s.k3s_fcos_image_id
        if not server_image_id:
            raise HTTPException(
                status_code=503, detail="FCOS 이미지가 설정되지 않았습니다 (k3s_fcos_image_id). 관리자에게 문의하세요."
            )
    else:
        server_image_id = s.k3s_server_image_id
    server_flavor_id = s.k3s_server_flavor_id
    if not server_image_id or not server_flavor_id:
        raise HTTPException(
            status_code=503, detail="k3s 서버 이미지 또는 플레이버가 설정되지 않았습니다. 관리자에게 문의하세요."
        )

    agent_flavor_id = req.agent_flavor_id or s.k3s_default_agent_flavor_id
    if req.agent_count > 0 and not agent_flavor_id:
        raise HTTPException(status_code=503, detail="에이전트 플레이버가 설정되지 않았습니다. 관리자에게 문의하세요.")

    # Default 네트워크 결정
    network_id = req.network_id
    if not network_id:
        if s.default_network_enabled:
            try:
                from app.services.default_network import ensure_default_network as _ensure_net

                default_net = await _ensure_net(
                    conn,
                    project_id,
                    external_network_id=s.default_network_external_id or None,
                    cidr=s.default_network_cidr,
                )
                network_id = default_net.id
            except Exception:
                import logging as _log

                _log.getLogger(__name__).warning("Default 네트워크 조회 실패, 설정값 폴백", exc_info=True)
                network_id = s.default_network_id
        else:
            network_id = s.default_network_id

    # 템플릿 적용 (지정 시 기본값 병합, 요청 본문 값이 있으면 override)
    _template_snapshot: dict | None = None
    if req.template_id:
        from app.services import k3s_template as _tmpl_svc

        _tmpl = await _tmpl_svc.get_template(req.template_id)
        if not _tmpl:
            raise HTTPException(status_code=400, detail=f"템플릿을 찾을 수 없습니다: {req.template_id}")
        _template_snapshot = dict(_tmpl)
        # 요청 본문에 명시적 값이 없으면 템플릿 기본값 적용
        if req.agent_count == 1 and _tmpl.get("default_node_count") is not None:
            req = req.model_copy(update={"agent_count": _tmpl["default_node_count"]})
        if not req.agent_flavor_id and _tmpl.get("default_agent_flavor_id"):
            req = req.model_copy(update={"agent_flavor_id": _tmpl["default_agent_flavor_id"]})
        if req.os_type == "ubuntu" and _tmpl.get("os_type") and _tmpl["os_type"] != "ubuntu":
            req = req.model_copy(update={"os_type": _tmpl["os_type"]})

    k3s_version = s.k3s_version
    boot_volume_size = s.k3s_boot_volume_size_gb
    cluster_id = str(uuid.uuid4())

    # flavor 이름 → ID 해석 (이름으로 설정된 경우)
    def _resolve_flavor(conn_obj, flavor_ref: str) -> str:
        if not flavor_ref:
            return flavor_ref
        try:
            f = conn_obj.compute.find_flavor(flavor_ref)
            return f.id if f else flavor_ref
        except Exception:
            return flavor_ref

    server_flavor_id = _resolve_flavor(conn, server_flavor_id)
    if agent_flavor_id:
        agent_flavor_id = _resolve_flavor(conn, agent_flavor_id)

    async def progress_generator() -> AsyncGenerator[str, None]:
        _start_time = time.monotonic()

        def event(step: K3sProgressStep, progress: int, message: str, **kw) -> str:
            elapsed = round(time.monotonic() - _start_time, 1)
            msg = K3sProgressMessage(step=step, progress=progress, message=message, elapsed_seconds=elapsed, **kw)
            return f"data: {msg.model_dump_json()}\n\n"

        # 프록시/CDN 버퍼 우회: 첫 chunk를 즉시 flush하기 위한 SSE 주석 패딩
        yield ": " + " " * 2048 + "\n\n"

        # 롤백 추적
        sg_id: str | None = None
        boot_volume_id: str | None = None
        server_vm_id: str | None = None
        app_credential_id: str | None = None
        ha_lb_id: str | None = None
        ha_lb_pool_id: str | None = None
        ha_fip_id: str | None = None
        ha_fip_address: str | None = None

        try:
            # --- Step 1: 보안 그룹 생성 ---
            yield event(K3sProgressStep.SECURITY_GROUP, 5, "k3s 보안 그룹 생성 중...")
            sg_name = f"k3s-{req.name}-{cluster_id[:8]}"
            sg = await asyncio.to_thread(
                neutron.create_security_group, conn, sg_name, f"k3s cluster {req.name} security group"
            )
            sg_id = sg["id"]

            # 보안 그룹 규칙 추가
            # SSH/K3s API는 allowed_cidrs가 있으면 해당 CIDR만, 없으면 0.0.0.0/0 허용
            mgmt_cidrs = req.allowed_cidrs or ["0.0.0.0/0"]
            rules = []
            for cidr in mgmt_cidrs:
                # SSH
                rules.append(
                    dict(
                        direction="ingress", protocol="tcp", port_range_min=22, port_range_max=22, remote_ip_prefix=cidr
                    )
                )
                # k3s API server
                rules.append(
                    dict(
                        direction="ingress",
                        protocol="tcp",
                        port_range_min=6443,
                        port_range_max=6443,
                        remote_ip_prefix=cidr,
                    )
                )
            rules += [
                # Kubelet (SG 내부)
                dict(
                    direction="ingress",
                    protocol="tcp",
                    port_range_min=10250,
                    port_range_max=10250,
                    remote_group_id=sg_id,
                ),
                # VXLAN (SG 내부)
                dict(
                    direction="ingress", protocol="udp", port_range_min=8472, port_range_max=8472, remote_group_id=sg_id
                ),
                # WireGuard (SG 내부)
                dict(
                    direction="ingress",
                    protocol="udp",
                    port_range_min=51820,
                    port_range_max=51820,
                    remote_group_id=sg_id,
                ),
                # HTTP (Traefik)
                dict(
                    direction="ingress",
                    protocol="tcp",
                    port_range_min=80,
                    port_range_max=80,
                    remote_ip_prefix="0.0.0.0/0",
                ),
                # HTTPS (Traefik)
                dict(
                    direction="ingress",
                    protocol="tcp",
                    port_range_min=443,
                    port_range_max=443,
                    remote_ip_prefix="0.0.0.0/0",
                ),
                # NodePort
                dict(
                    direction="ingress",
                    protocol="tcp",
                    port_range_min=30000,
                    port_range_max=32767,
                    remote_ip_prefix="0.0.0.0/0",
                ),
            ]
            for rule_kwargs in rules:
                await asyncio.to_thread(neutron.create_security_group_rule, conn, sg_id, **rule_kwargs)
            yield event(K3sProgressStep.SECURITY_GROUP, 10, "보안 그룹 생성 완료")

            extra_tls_sans: list[str] = []

            # --- Step 1-B: HA LB + FIP 생성 (master_count >= 3) ---
            if req.master_count >= 3:
                yield event(K3sProgressStep.SERVER_HA_BOOTSTRAP, 12, "HA API LB 생성 중...")
                subnets_for_lb = await asyncio.to_thread(lambda: list(conn.network.subnets(network_id=network_id)))
                lb_subnet_id = subnets_for_lb[0].id if subnets_for_lb else None
                ha_lb = await asyncio.to_thread(
                    octavia.create_load_balancer,
                    conn,
                    f"k3s-ha-{req.name}-{cluster_id[:8]}",
                    *(lb_subnet_id,) if lb_subnet_id else (),
                    vip_network_id=s.k3s_api_lb_vip_network_id or None,
                )
                ha_lb_id = ha_lb["id"]
                await asyncio.to_thread(octavia.wait_for_load_balancer, conn, ha_lb_id)
                listener = await asyncio.to_thread(
                    octavia.create_listener, conn, ha_lb_id, "TCP", 6443, name=f"k3s-ha-{req.name}-6443"
                )
                ha_lb_pool_id_raw = await asyncio.to_thread(
                    octavia.create_pool,
                    conn,
                    ha_lb_id,
                    "TCP",
                    name=f"k3s-ha-{req.name}-pool",
                    listener_id=listener["id"],
                )
                ha_lb_pool_id = ha_lb_pool_id_raw["id"]

                # FIP 할당 (모드 B: floating network)
                _fip_net = s.k3s_api_lb_floating_network_id or s.k3s_occm_floating_network_id or ""
                if _fip_net:
                    _lb_vip_port = ha_lb.get("vip_port_id")
                    _fip = await asyncio.to_thread(
                        lambda: conn.network.create_ip(
                            floating_network_id=_fip_net,
                            port_id=_lb_vip_port,
                        )
                    )
                    ha_fip_id = _fip["id"]
                    ha_fip_address = _fip["floating_ip_address"]
                    extra_tls_sans.append(ha_fip_address)
                    yield event(K3sProgressStep.SERVER_HA_BOOTSTRAP, 18, f"HA API LB 준비 완료 (FIP: {ha_fip_address})")
                else:
                    yield event(K3sProgressStep.SERVER_HA_BOOTSTRAP, 18, "HA API LB 준비 완료")

            # --- Step 2: 서버 부트 볼륨 생성 ---
            # K8s 스타일: 매 생성마다 고유한 suffix로 이름 충돌 방지
            server_suffix = _rand_suffix()
            server_vm_name = f"{req.name}-{server_suffix}"
            yield event(K3sProgressStep.SERVER_VOLUME, 28, "서버 노드 부트 볼륨 생성 중...")
            boot_vol = await asyncio.to_thread(
                cinder.create_volume_from_image,
                conn,
                f"{server_vm_name}-boot",
                server_image_id,
                boot_volume_size,
            )
            boot_volume_id = boot_vol.id
            yield event(K3sProgressStep.SERVER_VOLUME, 35, "서버 부트 볼륨 생성 완료")

            # --- Step 3: 콜백 토큰 + cloud-init 생성 ---
            yield event(K3sProgressStep.SERVER_CREATING, 40, "서버 VM cloud-init 생성 중...")
            # 공개키 미리 조회 (에이전트 VM은 admin conn으로 생성하므로 cloud-init에 직접 주입)
            ssh_public_key = ""
            if req.key_name:
                try:
                    kp = await asyncio.to_thread(conn.compute.find_keypair, req.key_name)
                    if kp:
                        ssh_public_key = kp.public_key or ""
                except Exception:
                    pass
            callback_token = await k3s_cluster.create_callback_token(project_id, cluster_id)
            callback_url = s.k3s_callback_base_url.rstrip("/")

            # 플러그인 레지스트리로 활성 플러그인 집계
            from app.services import k3s_plugins
            from app.services import keystone as _keystone

            _internal_network_name = ""
            try:
                _net_obj = await asyncio.to_thread(lambda: conn.network.get_network(network_id))
                _internal_network_name = _net_obj.name or ""
            except Exception:
                pass
            cloud_conf = k3s_plugins.aggregate_cloud_conf(project_id, s, internal_network_name=_internal_network_name)
            active_plugins = k3s_plugins.get_active_plugin_names(s)
            occm_active = active_plugins.get("occm", False)

            # PR1 — KMS 또는 Octavia Ingress 활성 시 cluster 별 App Credential 발급 (1회).
            # KMS plugin 의 cloud.conf 에 admin password 대신 app cred 사용 → 노드 한 대
            # compromise 시 OpenStack admin 권한 노출 방지.
            app_cred: dict | None = None
            needs_app_cred = active_plugins.get("octavia_ingress", False) or active_plugins.get("barbican_kms", False)
            if needs_app_cred:
                yield event(K3sProgressStep.SERVER_CREATING, 38, "App Credential 발급 중...")
                app_cred = await _keystone.create_app_credential_for_cluster(project_id, req.name)
                app_credential_id = app_cred["id"]

            # PR2 — KMS 활성 시 project owner Barbican 에서 KEK 조회/발급 (per-project 공유).
            # 글로벌 settings.k3s_barbican_kms_kek_id 가 있으면 fallback (lazy migration).
            kek_id: str | None = None
            if active_plugins.get("barbican_kms", False):
                yield event(K3sProgressStep.SERVER_CREATING, 39, "KEK (Barbican) 조회/발급 중...")
                from app.services import barbican as _barbican

                try:
                    kek_id = await _barbican.ensure_project_kek(project_id)
                except Exception:
                    _logger.warning("ensure_project_kek 실패 — 글로벌 fallback 사용", exc_info=True)
                    kek_id = s.k3s_barbican_kms_kek_id or None

            # Octavia Ingress 만 — subnet 도출 + manifest_kwargs 추가
            manifest_kwargs: dict = {}
            if active_plugins.get("octavia_ingress", False):
                subnets = await asyncio.to_thread(lambda: list(conn.network.subnets(network_id=network_id)))
                if not subnets:
                    raise RuntimeError(
                        f"네트워크 {network_id}에 subnet이 없습니다. Octavia Ingress를 위한 subnet 도출 실패."
                    )
                cluster_subnet_id = subnets[0].id
                manifest_kwargs = {
                    "subnet_id": cluster_subnet_id,
                    "app_credential": app_cred,
                    "floating_network_id": s.k3s_octavia_ingress_floating_network_id or None,
                }

            plugin_manifests, manifest_failures = k3s_plugins.aggregate_manifests(
                req.name, project_id, s, **manifest_kwargs
            )
            if manifest_failures:
                err_msg = f"플러그인 매니페스트 생성 실패: {', '.join(manifest_failures)}"
                _logger.error("k3s cluster %s: %s", cluster_id, err_msg)
                await rec(
                    token_info_obj or {},
                    conn,
                    resource_type="k3s_cluster",
                    action="create",
                    status="failed",
                    resource_name=req.name,
                    error_message=err_msg[:500],
                )
                yield event(K3sProgressStep.FAILED, 0, err_msg, cluster_id=cluster_id)
                return
            extra_server_args = k3s_plugins.aggregate_server_args(s)
            extra_write_files = k3s_plugins.aggregate_extra_write_files(
                project_id, req.name, s, app_credential=app_cred, kek_id=kek_id
            )

            userdata_result = k3s_cloudinit.generate_server_userdata(
                cluster_name=req.name,
                k3s_version=k3s_version,
                callback_url=callback_url,
                callback_token=callback_token,
                cloud_conf=cloud_conf,
                plugin_manifests=plugin_manifests,
                extra_server_args=extra_server_args,
                extra_write_files=extra_write_files,
                extra_tls_sans=extra_tls_sans,
                needs_external_cloud_provider=k3s_plugins.needs_external_cloud_provider(s),
                os_type=os_type,
                server_node_name=server_vm_name,
                barbican_kms_enabled=any(p.name == "barbican_kms" for p in k3s_plugins.get_active_plugins(s)),
                cluster_init=req.master_count >= 3,
            )

            # --- Step 4: 서버 VM 생성 ---
            yield event(K3sProgressStep.SERVER_CREATING, 48, "서버 VM 생성 중 (완료까지 수 분 소요)...")
            server_vm = await asyncio.to_thread(
                nova.create_server,
                conn,
                server_vm_name,
                server_flavor_id,
                network_id,
                boot_volume_id,
                userdata=userdata_result.data,
                key_name=req.key_name,
                metadata={
                    "k3s_horse_generator_role": "k3s_server",
                    "k3s_horse_generator_cluster_id": cluster_id,
                    "k3s_horse_generator_cluster_name": req.name,
                },
                delete_boot_volume_on_termination=True,
                security_groups=[sg_id],
                config_drive=userdata_result.config_drive,
            )
            server_vm_id = server_vm.id
            yield event(K3sProgressStep.SERVER_CREATING, 60, f"서버 VM 생성 완료: {server_vm_id}")

            # --- Step 5: Redis에 클러스터 레코드 저장 ---
            yield event(K3sProgressStep.WAITING_CALLBACK, 65, "k3s 초기화 대기 중 (서버 VM에서 k3s 설치 중)...")
            now = datetime.now(UTC).isoformat()
            # 생성자 정보 추출
            _creator_user_id = conn._afterglow_user_id if hasattr(conn, "_afterglow_user_id") else None
            _creator_username = None
            if token_info_obj and isinstance(token_info_obj, dict):
                _creator_user_id = _creator_user_id or token_info_obj.get("user_id")
                _creator_username = token_info_obj.get("username")
            await k3s_cluster.create_cluster_record(
                project_id,
                cluster_id,
                {
                    "name": req.name,
                    "status": "CREATING",
                    "status_reason": "",
                    "server_vm_id": server_vm_id,
                    "agent_vm_ids": [],
                    "agent_count": req.agent_count,
                    "server_flavor_id": server_flavor_id,
                    "agent_flavor_id": agent_flavor_id,
                    "network_id": network_id,
                    "security_group_id": sg_id,
                    "server_ip": "",
                    "api_address": "",
                    "key_name": req.key_name or "",
                    "ssh_public_key": ssh_public_key,
                    "k3s_version": k3s_version,
                    "occm_enabled": occm_active,
                    "plugins_enabled": active_plugins,
                    "created_by_user_id": _creator_user_id or "",
                    "created_by_username": _creator_username or "",
                    "created_at": now,
                    "updated_at": now,
                    "api_lb_id": ha_lb_id or "",
                    "api_lb_pool_id": ha_lb_pool_id or "",
                    "api_fip_id": ha_fip_id or "",
                    "api_fip_address": ha_fip_address or "",
                    "master_count": req.master_count,
                    "os_type": os_type,
                    "server_vm_name": server_vm_name,
                    "app_credential_id": app_credential_id or "",
                    "template_id": req.template_id or None,
                    "template_snapshot": _template_snapshot,
                    "stampede_enabled": req.stampede_enabled,
                },
            )
            try:
                await invalidate(f"afterglow:k3s:{project_id}:*")
                await cache_invalidation.invalidate_mutation_count("k3s", project_id)
            except Exception:
                pass

            await rec(
                token_info_obj or {},
                conn,
                resource_type="k3s_cluster",
                action="create",
                status="success",
                resource_id=cluster_id,
                resource_name=req.name,
            )
            yield event(
                K3sProgressStep.COMPLETED,
                100,
                f"클러스터 생성 요청 완료. 서버 VM이 k3s를 설치한 후 에이전트 {req.agent_count}개가 자동으로 생성됩니다.",
                cluster_id=cluster_id,
            )

        except Exception as e:
            _logger.error("k3s cluster creation failed: %s", e, exc_info=True)
            await rec(
                token_info_obj or {},
                conn,
                resource_type="k3s_cluster",
                action="create",
                status="failed",
                resource_name=req.name,
                error_message=str(e)[:500],
            )
            yield event(K3sProgressStep.FAILED, 0, f"클러스터 생성 실패: {e}", error=str(e))
            # 롤백
            await _rollback(
                conn,
                server_vm_id,
                boot_volume_id,
                sg_id,
                app_credential_id,
                project_id,
                lb_id=ha_lb_id,
                fip_id=ha_fip_id,
            )

    return StreamingResponse(
        progress_generator(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _rollback(
    conn: openstack.connection.Connection,
    server_vm_id: str | None,
    boot_volume_id: str | None,
    sg_id: str | None,
    app_credential_id: str | None = None,
    project_id: str | None = None,
    lb_id: str | None = None,
    fip_id: str | None = None,
) -> None:
    """생성 실패 시 리소스 역순 삭제."""
    if server_vm_id:
        try:
            await asyncio.to_thread(nova.delete_server, conn, server_vm_id)
        except Exception as e:
            _logger.warning("Rollback: delete server %s failed: %s", server_vm_id, e)
    if boot_volume_id:
        try:
            await asyncio.sleep(3)
            await asyncio.to_thread(cinder.delete_volume, conn, boot_volume_id)
        except Exception as e:
            _logger.warning("Rollback: delete volume %s failed: %s", boot_volume_id, e)
    if fip_id:
        try:
            await asyncio.to_thread(lambda: conn.network.delete_ip(fip_id, ignore_missing=True))
        except Exception as e:
            _logger.warning("Rollback: delete FIP %s failed: %s", fip_id, e)
    if lb_id:
        try:
            await asyncio.to_thread(octavia.delete_load_balancer, conn, lb_id, cascade=True)
        except Exception as e:
            _logger.warning("Rollback: delete LB %s failed: %s", lb_id, e)
    if sg_id:
        try:
            await asyncio.to_thread(neutron.delete_security_group, conn, sg_id)
        except Exception as e:
            _logger.warning("Rollback: delete SG %s failed: %s", sg_id, e)
    if app_credential_id and project_id:
        try:
            from app.services import keystone as _keystone

            await _keystone.delete_app_credential(project_id, app_credential_id)
        except Exception as e:
            _logger.warning("Rollback: delete app credential %s failed: %s", app_credential_id, e)


@router.patch("/{cluster_id}/scale")
@limiter.limit("10/minute")
async def scale_k3s_cluster(
    request: Request,
    cluster_id: str,
    req: ScaleK3sClusterRequest,
    token_info: dict = Depends(get_token_info),
):
    """에이전트 수 변경. 현재 ACTIVE 상태에서만 허용."""
    project_id = token_info["project_id"]
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")
    if cluster["status"] != "ACTIVE":
        raise HTTPException(status_code=409, detail="ACTIVE 상태의 클러스터만 스케일링할 수 있습니다")

    current_agent_ids: list[str] = cluster.get("agent_vm_ids") or []
    if isinstance(current_agent_ids, str):
        import json as _json

        try:
            current_agent_ids = _json.loads(current_agent_ids)
        except Exception:
            current_agent_ids = []

    desired = req.agent_count
    current = len(current_agent_ids)

    if desired == current:
        return {"message": "변경 없음", "agent_count": current}

    await k3s_cluster.update_cluster_status(project_id, cluster_id, "SCALING")
    try:
        await invalidate(f"afterglow:k3s:{project_id}:*")
        await cache_invalidation.invalidate_mutation_count("k3s", project_id)
    except Exception:
        pass
    asyncio.create_task(_scale_agents(project_id, cluster_id, current_agent_ids, desired))
    await rec(
        token_info,
        None,
        resource_type="k3s_cluster",
        action="scale",
        resource_id=cluster_id,
        extra={"desired_count": desired},
    )
    return {"message": f"스케일링 시작: {current} → {desired}", "agent_count": desired}


async def _scale_agents(
    project_id: str,
    cluster_id: str,
    current_agent_ids: list[str],
    desired_count: int,
) -> None:
    """에이전트 스케일링 백그라운드 태스크."""
    from app.config import get_settings
    from app.services import k3s_plugins

    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        return

    node_token = await k3s_cluster.get_cluster_node_token(project_id, cluster_id)
    server_ip = cluster.get("server_ip") or ""
    s = get_settings()

    current_count = len(current_agent_ids)

    if desired_count > current_count:
        # 스케일 업
        add_count = desired_count - current_count
        agent_flavor_id = cluster.get("agent_flavor_id") or s.k3s_default_agent_flavor_id
        network_id = cluster.get("network_id") or ""
        ssh_public_key = cluster.get("ssh_public_key") or None
        cluster_name = cluster.get("name") or cluster_id
        k3s_version = cluster.get("k3s_version") or s.k3s_version
        scale_os_type = cluster.get("os_type") or "ubuntu"
        image_id = s.k3s_fcos_image_id if scale_os_type == "fcos" else s.k3s_server_image_id
        boot_volume_size = s.k3s_boot_volume_size_gb
        sg_id = cluster.get("security_group_id") or None

        try:
            conn = keystone.get_admin_connection_for_project(project_id)
        except Exception as e:
            _logger.error("k3s scale up: cannot get OpenStack connection: %s", e)
            await k3s_cluster.update_cluster_status(project_id, cluster_id, "ACTIVE", f"스케일 업 실패: {e}")
            return

        # network_id 폴백: DB → 설정값
        if not network_id:
            if s.default_network_enabled:
                try:
                    from app.services.default_network import ensure_default_network as _ensure_net

                    _default_net = await _ensure_net(
                        conn,
                        project_id,
                        external_network_id=s.default_network_external_id or None,
                        cidr=s.default_network_cidr,
                    )
                    network_id = _default_net.id
                except Exception:
                    _logger.warning("스케일 업: Default 네트워크 조회 실패, 설정값 폴백", exc_info=True)
                    network_id = s.default_network_id
            else:
                network_id = s.default_network_id

        new_entries: list[dict] = []
        for _i in range(add_count):
            agent_name = f"{cluster_name}-{_rand_suffix()}"
            try:
                vol = await asyncio.to_thread(
                    cinder.create_volume_from_image, conn, f"{agent_name}-boot", image_id, boot_volume_size
                )
                _agent_args = k3s_plugins.aggregate_agent_args(s)
                if not _agent_args and cluster.get("occm_enabled"):
                    _agent_args = ["--kubelet-arg=cloud-provider=external"]
                scale_userdata = k3s_cloudinit.generate_agent_userdata(
                    cluster_name=cluster_name,
                    k3s_version=k3s_version,
                    server_ip=server_ip,
                    node_token=node_token or "",
                    ssh_public_key=ssh_public_key,
                    extra_agent_args=_agent_args,
                    os_type=scale_os_type,
                )
                vm = await asyncio.to_thread(
                    nova.create_server,
                    conn,
                    agent_name,
                    agent_flavor_id,
                    network_id,
                    vol.id,
                    userdata=scale_userdata.data,
                    metadata={"k3s_horse_generator_role": "k3s_agent", "k3s_horse_generator_cluster_id": cluster_id},
                    delete_boot_volume_on_termination=True,
                    security_groups=[sg_id] if sg_id else None,
                    config_drive=scale_userdata.config_drive,
                )
                new_entries.append({"vm_id": vm.id, "name": agent_name})
                _logger.info("k3s scale up: agent %s created: %s", agent_name, vm.id)
            except Exception as e:
                _logger.error("k3s scale up: agent %s failed: %s", agent_name, e)

        if new_entries:
            await k3s_cluster.add_agent_vms(cluster_id, new_entries)
            from app.services import k3s_nodegroup

            default_agent_id = await k3s_nodegroup.get_default_agent_nodegroup_id(cluster_id)
            if default_agent_id:
                await k3s_nodegroup.add_nodegroup_vms(default_agent_id, cluster_id, new_entries)
                await k3s_nodegroup.set_nodegroup_count(cluster_id, default_agent_id, desired_count)

    else:
        # 스케일 다운: K8s 노드 제거 후 VM 삭제
        remove_ids = current_agent_ids[desired_count:]

        # K8s 노드 삭제 (VM 삭제 전 먼저 수행, best-effort)
        vm_name_map = await k3s_cluster.get_agent_vm_names(cluster_id, remove_ids)
        node_names = [name for name in vm_name_map.values() if name]
        if node_names:
            _logger.info("k3s scale down: K8s 노드 삭제 시작: %s", node_names)
            await k3s_kube.delete_k8s_nodes(cluster_id, node_names)

        try:
            conn = keystone.get_admin_connection_for_project(project_id)
        except Exception as e:
            _logger.error("k3s scale down: cannot get OpenStack connection: %s", e)
            await k3s_cluster.update_cluster_status(project_id, cluster_id, "ACTIVE", f"스케일 다운 실패: {e}")
            return

        for vm_id in remove_ids:
            try:
                await asyncio.to_thread(nova.delete_server, conn, vm_id)
                _logger.info("k3s scale down: agent VM %s deleted", vm_id)
            except Exception as e:
                _logger.warning("k3s scale down: delete VM %s failed: %s", vm_id, e)

        await k3s_cluster.remove_agent_vms(cluster_id, remove_ids)
        from app.services import k3s_nodegroup

        default_agent_id = await k3s_nodegroup.get_default_agent_nodegroup_id(cluster_id)
        if default_agent_id:
            await k3s_nodegroup.remove_nodegroup_vms(default_agent_id, remove_ids)
            await k3s_nodegroup.set_nodegroup_count(cluster_id, default_agent_id, desired_count)

    await k3s_cluster.update_agent_count(project_id, cluster_id, desired_count)
    await k3s_cluster.update_cluster_status(project_id, cluster_id, "ACTIVE", "")
    _logger.info("k3s cluster %s scaled to %d agents", cluster_id, desired_count)


async def _delete_cluster_progress(
    conn: openstack.connection.Connection,
    project_id: str,
    cluster: dict,
    token_info: dict | None,
) -> AsyncGenerator[K3sProgressMessage, None]:
    """k3s 클러스터 삭제 단계별 진행. 각 단계 진입 시 K3sProgressMessage 를 yield."""
    import json

    cluster_id: str = cluster["id"]
    cluster_name: str = cluster.get("name") or ""

    yield K3sProgressMessage(step=K3sProgressStep.DELETE_INIT, progress=5, message="클러스터 삭제 준비 중...")
    await k3s_cluster.update_cluster_status(project_id, cluster_id, "DELETING")

    # API LB + FIP 정리
    yield K3sProgressMessage(
        step=K3sProgressStep.DELETE_LB_CLEANUP, progress=15, message="API LoadBalancer / Floating IP 정리 중..."
    )
    _api_lb_id = cluster.get("api_lb_id") or ""
    _api_fip_id = cluster.get("api_fip_id") or ""
    if _api_lb_id:
        try:
            await asyncio.to_thread(octavia.delete_load_balancer, conn, _api_lb_id, cascade=True)
            _logger.info("Deleted API LB %s for cluster %s", _api_lb_id, cluster_id)
        except Exception as e:
            _logger.warning("Delete API LB %s failed: %s", _api_lb_id, e)
    if _api_fip_id:
        try:
            await asyncio.to_thread(neutron.delete_floating_ip, conn, _api_fip_id)
            _logger.info("Deleted API FIP %s for cluster %s", _api_fip_id, cluster_id)
        except Exception as e:
            _logger.warning("Delete API FIP %s failed: %s", _api_fip_id, e)

    # OCCM/Ingress가 생성한 Octavia LB 정리
    plugins_enabled = cluster.get("plugins_enabled") or {}
    occm_enabled = cluster.get("occm_enabled") or plugins_enabled.get("occm", False)
    ingress_enabled = plugins_enabled.get("octavia_ingress", False)
    if occm_enabled or ingress_enabled:
        lb_prefixes = []
        if occm_enabled:
            lb_prefixes.append(f"kube_service_{cluster_name}_")
        if ingress_enabled:
            lb_prefixes.append(f"kube_ingress_{cluster_name}_")
        try:
            all_lbs = await asyncio.to_thread(octavia.list_load_balancers, conn)
            for lb in all_lbs:
                lb_name = lb.get("name", "")
                if any(lb_name.startswith(p) for p in lb_prefixes):
                    try:
                        await asyncio.to_thread(octavia.delete_load_balancer, conn, lb["id"], cascade=True)
                        _logger.info("Deleted LB %s (%s) for cluster %s", lb["id"], lb_name, cluster_id)
                    except Exception as e:
                        _logger.warning("Delete LB %s failed: %s", lb["id"], e)
        except Exception as e:
            _logger.warning("Failed to list/delete LBs for cluster %s: %s", cluster_id, e)

    # App Credential 회수
    yield K3sProgressMessage(
        step=K3sProgressStep.DELETE_APP_CREDENTIAL, progress=25, message="App Credential 회수 중..."
    )
    _app_cred_id = cluster.get("app_credential_id") or ""
    if _app_cred_id:
        try:
            from app.services import keystone as _keystone

            await _keystone.delete_app_credential(project_id, _app_cred_id)
            _logger.info("Deleted App Credential %s for cluster %s", _app_cred_id, cluster_id)
        except Exception as e:
            _logger.warning("Delete App Credential %s failed: %s", _app_cred_id, e)

    # 에이전트 VM id 파싱
    agent_vm_ids = cluster.get("agent_vm_ids") or []
    if isinstance(agent_vm_ids, str):
        try:
            agent_vm_ids = json.loads(agent_vm_ids)
        except Exception:
            agent_vm_ids = []

    # K8s 노드 삭제 (VM 삭제 전 먼저 수행, best-effort)
    yield K3sProgressMessage(step=K3sProgressStep.DELETE_K8S_NODES, progress=35, message="Kubernetes 노드 정리 중...")
    all_node_names: list[str] = []
    if agent_vm_ids:
        vm_name_map = await k3s_cluster.get_agent_vm_names(cluster_id, agent_vm_ids)
        all_node_names.extend([name for name in vm_name_map.values() if name])
    server_node_name = cluster.get("server_vm_name") or ""
    if server_node_name:
        all_node_names.append(server_node_name)
    if all_node_names:
        _logger.info("k3s delete: K8s 노드 삭제 시작: %s", all_node_names)
        try:
            await k3s_kube.delete_k8s_nodes(cluster_id, all_node_names)
        except Exception as e:
            _logger.warning("k3s delete: K8s 노드 삭제 중 오류 (무시): %s", e)

    # 에이전트 VM 병렬 삭제
    n_agents = len(agent_vm_ids)
    yield K3sProgressMessage(
        step=K3sProgressStep.DELETE_AGENT_VMS,
        progress=55,
        message=f"에이전트 VM 삭제 중 ({n_agents}개)...",
    )

    async def _del_vm_and_wait(vm_id: str) -> None:
        try:
            await asyncio.to_thread(nova.delete_server, conn, vm_id)
        except Exception as e:
            _logger.warning("Delete agent VM %s failed: %s", vm_id, e)
            return
        try:
            await asyncio.to_thread(nova.wait_server_deleted, conn, vm_id)
            _logger.info("k3s delete: VM %s fully deleted", vm_id)
        except TimeoutError as e:
            _logger.warning("k3s delete: VM %s 삭제 대기 타임아웃 (계속 진행): %s", vm_id, e)
        except Exception as e:
            _logger.warning("k3s delete: VM %s 대기 중 오류 (계속 진행): %s", vm_id, e)

    await asyncio.gather(*[_del_vm_and_wait(vid) for vid in agent_vm_ids], return_exceptions=True)

    # 서버 VM 삭제 + 완료 대기
    yield K3sProgressMessage(step=K3sProgressStep.DELETE_SERVER_VM, progress=80, message="서버 VM 삭제 중...")
    server_vm_id = cluster.get("server_vm_id")
    if server_vm_id:
        try:
            await asyncio.to_thread(nova.delete_server, conn, server_vm_id)
        except Exception as e:
            _logger.warning("Delete server VM %s failed: %s", server_vm_id, e)
        else:
            try:
                await asyncio.to_thread(nova.wait_server_deleted, conn, server_vm_id)
                _logger.info("k3s delete: server VM %s fully deleted", server_vm_id)
            except TimeoutError as e:
                _logger.warning("k3s delete: server VM %s 삭제 대기 타임아웃 (계속 진행): %s", server_vm_id, e)
            except Exception as e:
                _logger.warning("k3s delete: server VM %s 대기 중 오류 (계속 진행): %s", server_vm_id, e)

    # 보안 그룹 삭제 (VM 삭제 완료 후, 재시도 포함)
    yield K3sProgressMessage(step=K3sProgressStep.DELETE_SECURITY_GROUP, progress=92, message="보안 그룹 삭제 중...")
    sg_id = cluster.get("security_group_id")
    if sg_id:
        for attempt in range(3):
            try:
                if attempt > 0:
                    await asyncio.sleep(5)
                await asyncio.to_thread(neutron.delete_security_group, conn, sg_id)
                _logger.info("k3s delete: SG %s deleted", sg_id)
                break
            except Exception as e:
                _logger.warning("Delete SG %s attempt %d failed: %s", sg_id, attempt + 1, e)

    # soft-delete: 상태를 DELETED로 기록
    yield K3sProgressMessage(step=K3sProgressStep.DELETE_RECORD, progress=98, message="삭제 이력 기록 중...")
    user_id = token_info.get("user_id") if isinstance(token_info, dict) else None
    await k3s_cluster.delete_cluster_record(project_id, cluster_id, user_id=user_id, reason="사용자 삭제 요청")
    if token_info is not None:
        await rec(token_info, conn, resource_type="k3s_cluster", action="delete", resource_id=cluster_id)

    yield K3sProgressMessage(
        step=K3sProgressStep.COMPLETED,
        progress=100,
        message=f'클러스터 "{cluster_name}" 삭제 완료',
    )


@router.delete("/{cluster_id}", status_code=204)
@limiter.limit("5/minute")
async def delete_k3s_cluster(
    request: Request,
    cluster_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """k3s 클러스터 삭제: VM → SG 정리 후 soft-delete 처리."""
    project_id = conn._afterglow_project_id
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")

    if cluster.get("deleted_at"):
        return

    try:
        await invalidate(f"afterglow:k3s:{project_id}:*")
        await cache_invalidation.invalidate_mutation_count("k3s", project_id)
    except Exception:
        pass

    async for _msg in _delete_cluster_progress(conn, project_id, cluster, token_info):
        pass


@router.post("/{cluster_id}/delete-async")
@limiter.limit("5/minute")
async def delete_k3s_cluster_async(
    request: Request,
    cluster_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """k3s 클러스터 삭제 — SSE 스트리밍 진행률 반환."""
    project_id = conn._afterglow_project_id
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")

    try:
        await invalidate(f"afterglow:k3s:{project_id}:*")
        await cache_invalidation.invalidate_mutation_count("k3s", project_id)
    except Exception:
        pass

    async def gen() -> AsyncGenerator[str, None]:
        yield ": " + " " * 2048 + "\n\n"
        start = time.monotonic()
        if cluster.get("deleted_at"):
            msg = K3sProgressMessage(
                step=K3sProgressStep.COMPLETED,
                progress=100,
                message="이미 삭제된 클러스터입니다",
                elapsed_seconds=0.0,
            )
            yield f"data: {msg.model_dump_json()}\n\n"
            return
        try:
            async for msg in _delete_cluster_progress(conn, project_id, cluster, token_info):
                msg.elapsed_seconds = round(time.monotonic() - start, 1)
                yield f"data: {msg.model_dump_json()}\n\n"
        except Exception as e:
            _logger.error("k3s cluster %s async delete failed: %s", cluster_id, e, exc_info=True)
            fail = K3sProgressMessage(
                step=K3sProgressStep.FAILED,
                progress=0,
                message=f"삭제 실패: {e}",
                error=str(e),
                elapsed_seconds=round(time.monotonic() - start, 1),
            )
            yield f"data: {fail.model_dump_json()}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


# ---------------------------------------------------------------------------
# 노드 네트워크 인터페이스 attach / detach
# ---------------------------------------------------------------------------


def _assert_vm_in_cluster(vm_id: str, cluster: dict) -> str:
    """vm_id 가 해당 클러스터에 속하면 'server'|'agent' 반환, 아니면 HTTPException 403."""
    if cluster.get("server_vm_id") == vm_id:
        return "server"
    if vm_id in (cluster.get("agent_vm_ids") or []):
        return "agent"
    raise HTTPException(status_code=403, detail="해당 VM은 이 클러스터에 속하지 않습니다")


@router.get("/{cluster_id}/nodes/{vm_id}/interfaces")
async def list_node_interfaces(
    cluster_id: str,
    vm_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    project_id = conn._afterglow_project_id
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")
    node_role = _assert_vm_in_cluster(vm_id, cluster)
    ifaces = await asyncio.to_thread(lambda: list(conn.compute.server_interfaces(vm_id)))
    return [
        K3sInterfaceInfo(
            port_id=i.port_id,
            net_id=i.net_id,
            fixed_ips=i.fixed_ips or [],
            vm_id=vm_id,
            node_role=node_role,
        )
        for i in ifaces
    ]


@router.post("/{cluster_id}/nodes/{vm_id}/interfaces", status_code=201)
async def attach_node_interface(
    cluster_id: str,
    vm_id: str,
    body: K3sAttachInterfaceRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    project_id = conn._afterglow_project_id
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")
    node_role = _assert_vm_in_cluster(vm_id, cluster)
    try:
        result = await asyncio.to_thread(nova.attach_interface, conn, vm_id, body.net_id)
        await invalidate(f"afterglow:neutron:{project_id}:ports:{vm_id}")
        await invalidate(f"afterglow:neutron:{project_id}:port_mac_map")
        await invalidate(f"afterglow:k3s:{project_id}:cluster:{cluster_id}")
        await rec(
            token_info,
            conn,
            resource_type="k3s_cluster",
            action="k3s.attach_interface",
            status="success",
            resource_id=cluster_id,
            extra={"vm_id": vm_id, "net_id": body.net_id, "node_role": node_role},
        )
        return K3sInterfaceInfo(
            port_id=result["port_id"],
            net_id=result["net_id"],
            fixed_ips=result["fixed_ips"],
            vm_id=vm_id,
            node_role=node_role,
        )
    except HTTPException:
        raise
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="k3s_cluster",
            action="k3s.attach_interface",
            status="failed",
            resource_id=cluster_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="인터페이스 attach 실패")


@router.delete("/{cluster_id}/nodes/{vm_id}/interfaces/{port_id}", status_code=204)
async def detach_node_interface(
    cluster_id: str,
    vm_id: str,
    port_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    project_id = conn._afterglow_project_id
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")
    node_role = _assert_vm_in_cluster(vm_id, cluster)
    try:
        await asyncio.to_thread(nova.detach_interface, conn, vm_id, port_id)
        await invalidate(f"afterglow:neutron:{project_id}:ports:{vm_id}")
        await invalidate(f"afterglow:neutron:{project_id}:port_mac_map")
        await invalidate(f"afterglow:k3s:{project_id}:cluster:{cluster_id}")
        await rec(
            token_info,
            conn,
            resource_type="k3s_cluster",
            action="k3s.detach_interface",
            status="success",
            resource_id=cluster_id,
            extra={"vm_id": vm_id, "port_id": port_id, "node_role": node_role},
        )
    except HTTPException:
        raise
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="k3s_cluster",
            action="k3s.detach_interface",
            status="failed",
            resource_id=cluster_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="인터페이스 detach 실패")


# ---------------------------------------------------------------------------
# Stampede 오토스케일 API
# ---------------------------------------------------------------------------


@router.post("/{cluster_id}/stampede/enable", status_code=200)
async def enable_stampede(
    cluster_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """클러스터의 Stampede 오토스케일 모드를 활성화한다."""

    project_id = conn._afterglow_project_id
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")

    if not get_settings().k3s_stampede_enabled:
        raise HTTPException(status_code=400, detail="Stampede 기능이 서버에서 비활성화 상태입니다")

    await k3s_cluster.update_cluster_status(project_id, cluster_id, cluster["status"], "")
    # stampede_enabled 컬럼 갱신
    from sqlalchemy import select as _select

    from app.database import get_session_factory, is_db_available
    from app.models.db import K3sCluster

    if is_db_available():
        factory = get_session_factory()
        async with factory() as session:
            stmt = _select(K3sCluster).where(K3sCluster.id == cluster_id)
            result = await session.execute(stmt)
            c = result.scalar_one_or_none()
            if c:
                c.stampede_enabled = True
                await session.commit()

    await invalidate(f"afterglow:k3s:{project_id}:cluster:{cluster_id}")
    await rec(
        token_info,
        conn,
        resource_type="k3s_cluster",
        action="k3s.stampede_enable",
        status="success",
        resource_id=cluster_id,
    )
    return {"message": "Stampede 모드가 활성화되었습니다", "cluster_id": cluster_id}


@router.post("/{cluster_id}/stampede/disable", status_code=200)
async def disable_stampede(
    cluster_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """클러스터의 Stampede 오토스케일 모드를 비활성화한다."""
    project_id = conn._afterglow_project_id
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")

    from sqlalchemy import select as _select

    from app.database import get_session_factory, is_db_available
    from app.models.db import K3sCluster

    if is_db_available():
        factory = get_session_factory()
        async with factory() as session:
            stmt = _select(K3sCluster).where(K3sCluster.id == cluster_id)
            result = await session.execute(stmt)
            c = result.scalar_one_or_none()
            if c:
                c.stampede_enabled = False
                await session.commit()

    await invalidate(f"afterglow:k3s:{project_id}:cluster:{cluster_id}")
    await rec(
        token_info,
        conn,
        resource_type="k3s_cluster",
        action="k3s.stampede_disable",
        status="success",
        resource_id=cluster_id,
    )
    return {"message": "Stampede 모드가 비활성화되었습니다", "cluster_id": cluster_id}


@router.get("/{cluster_id}/stampede")
async def get_stampede_status(
    cluster_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """클러스터의 Stampede 오토스케일 상태를 조회한다."""
    from app.services import k3s_nodegroup as _k3s_ng

    project_id = conn._afterglow_project_id
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")

    all_ngs = await _k3s_ng.list_nodegroups(cluster_id)
    stampede_ngs = []
    for ng in all_ngs:
        state = ng.get("stampede_state") or {}
        stampede_ngs.append(
            {
                "id": ng["id"],
                "name": ng["name"],
                "role": ng.get("role"),
                "flavor_id": ng.get("flavor_id"),
                "stampede_enabled": ng["stampede_enabled"],
                "min_size": ng["min_size"],
                "max_size": ng["max_size"],
                "node_count": ng["node_count"],
                "in_flight": int(state.get("in_flight_count", 0) or 0),
                "capacity": state.get("capacity") or {},
                "pending_assignments": state.get("pending_assignments") or [],
                "blocked_reasons": state.get("blocked_reasons") or [],
                "last_decision": state.get("last_decision") or "",
                "last_blocked_reason": state.get("last_blocked_reason") or "",
                "flavor_summary": state.get("flavor_summary") or {},
                "quota_state": state.get("quota_state") or {},
                "stampede_state": state,
            }
        )

    return {
        "cluster_id": cluster_id,
        "stampede_enabled": bool(cluster.get("stampede_enabled", False)),
        "global_stampede_enabled": get_settings().k3s_stampede_enabled,
        "nodegroups": stampede_ngs,
    }


@router.get("/{cluster_id}/stampede/events")
async def get_stampede_events(
    cluster_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """Stampede 스케일 이벤트 이력 조회 (최신순)."""
    from sqlalchemy import desc
    from sqlalchemy import select as _select

    from app.database import get_session_factory, is_db_available
    from app.models.activity import ActivityLog

    project_id = conn._afterglow_project_id
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")

    if not is_db_available():
        return []

    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            _select(ActivityLog)
            .where(
                ActivityLog.resource_type == "k3s_stampede",
                ActivityLog.resource_id == cluster_id,
            )
            .order_by(desc(ActivityLog.created_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
            "action": r.action,
            "status": r.status,
            "nodegroup_id": r.resource_name,
            "extra": r.extra or {},
        }
        for r in rows
    ]
