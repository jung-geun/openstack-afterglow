"""Stampede Reconciler — k3s 노드 오토스케일 내부 루프.

drover worker.py에서 주기적으로 run_all()을 호출.
ACTIVE + stampede_enabled 클러스터의 각 노드그룹을 순회하며:
  - Unschedulable pod 감지 → fit-check → VM 추가 (scale-up)
  - 유휴 노드 감지 → cordon/drain/삭제 (scale-down)
"""

import asyncio
import logging
import time

from app.config import get_settings

_logger = logging.getLogger("drover.stampede")

# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _node_matches_nodegroup(pod: dict, nodegroup: dict) -> bool:
    """pod가 이 nodegroup에 스케줄 가능한지 기초 매칭.

    확인 항목:
      1. pod.nodeSelector 키가 nodegroup.labels에 모두 포함되는지
      2. pod.tolerations가 nodegroup.taints를 커버하는지 (NoSchedule/NoExecute)
    """
    ng_labels: dict = nodegroup.get("labels") or {}
    ng_taints: list = nodegroup.get("taints") or []

    # nodeSelector 체크
    node_selector: dict = pod.get("node_selector") or {}
    for k, v in node_selector.items():
        if ng_labels.get(k) != v:
            return False

    # taints 체크 (NoSchedule / NoExecute — pod가 tolerate해야 배포 가능)
    pod_tolerations: list = pod.get("tolerations") or []

    def _tolerates(taint: dict) -> bool:
        effect = taint.get("effect", "")
        if effect not in ("NoSchedule", "NoExecute", ""):
            return True  # PreferNoSchedule은 스케줄 차단 안 함
        t_key = taint.get("key", "")
        t_val = taint.get("value")
        for tol in pod_tolerations:
            if tol.get("operator") == "Exists":
                if not tol.get("key") or tol.get("key") == t_key:
                    return True
            elif tol.get("key") == t_key and (tol.get("value") is None or tol.get("value") == t_val):
                return True
        return False

    return all(not (isinstance(taint, dict) and not _tolerates(taint)) for taint in ng_taints)


def _is_pvc_issue(pod: dict) -> bool:
    """pod가 PVC 미바운드로 Unschedulable인지 추정."""
    msg: str = pod.get("message", "").lower()
    return "persistentvolumeclaim" in msg or "pvc" in msg or "volume" in msg


def _pod_fits_flavor(pod: dict, flavor: dict) -> bool:
    """pod의 resource requests가 flavor capacity에 맞는지."""
    req = pod.get("resource_requests", {})
    cpu_m = req.get("cpu_m", 0)
    mem = req.get("memory_bytes", 0)
    gpu = req.get("gpu", 0)
    if cpu_m > flavor.get("vcpus_m", 0):
        return False
    if mem > flavor.get("ram_bytes", 0):
        return False
    if gpu > flavor.get("gpu", 0):
        return False
    return True


def _select_flavor(
    pending_pods: list[dict],
    node_pods: list[dict],
    available_flavors: list[dict],
    nodegroup: dict,
    headroom_factor: float,
) -> dict | None:
    """가중치 기반 flavor 자동 선택.

    target = Σ(pending pod requests) × (1 + α × 기존_부하_비율)
    → target 이상 capacity를 가진 최소 flavor 반환.
    """
    if not available_flavors:
        return None

    # pending pod requests 합산 (이 nodegroup에 할당될 pod만)
    total_cpu_m = sum(p["resource_requests"]["cpu_m"] for p in pending_pods)
    total_mem = sum(p["resource_requests"]["memory_bytes"] for p in pending_pods)
    needs_gpu = any(p["resource_requests"].get("gpu", 0) > 0 for p in pending_pods)

    # 기존 부하 비율 계산 (nodegroup 노드들의 평균 사용률)
    ng_node_names = {v["name"] for v in nodegroup.get("vms", []) if v.get("name")}
    ng_pods = [p for p in node_pods if p.get("node") in ng_node_names]

    existing_cpu_m = sum(p["cpu_m"] for p in ng_pods)
    existing_mem = sum(p["memory_bytes"] for p in ng_pods)

    # 노드그룹 총 allocatable (간략 추정: node_count × 첫 flavor capacity)
    node_count = nodegroup.get("node_count", 0)
    if node_count > 0 and available_flavors:
        ref = available_flavors[0]
        ng_total_cpu_m = node_count * ref.get("vcpus_m", 1)
        ng_total_mem = node_count * ref.get("ram_bytes", 1)
        existing_cpu_frac = min(existing_cpu_m / ng_total_cpu_m, 1.0) if ng_total_cpu_m else 0.0
        existing_mem_frac = min(existing_mem / ng_total_mem, 1.0) if ng_total_mem else 0.0
    else:
        existing_cpu_frac = 0.0
        existing_mem_frac = 0.0

    # 헤드룸 적용
    target_cpu_m = int(total_cpu_m * (1 + headroom_factor * existing_cpu_frac))
    target_mem = int(total_mem * (1 + headroom_factor * existing_mem_frac))

    # 최소 1 pod를 수용할 수 있는 후보 필터
    max_pod_cpu_m = max((p["resource_requests"]["cpu_m"] for p in pending_pods), default=0)
    max_pod_mem = max((p["resource_requests"]["memory_bytes"] for p in pending_pods), default=0)
    max_pod_gpu = max((p["resource_requests"].get("gpu", 0) for p in pending_pods), default=0)

    candidates = [
        f for f in available_flavors
        if f.get("vcpus_m", 0) >= max(max_pod_cpu_m, target_cpu_m)
        and f.get("ram_bytes", 0) >= max(max_pod_mem, target_mem)
        and (not needs_gpu or f.get("gpu", 0) >= max_pod_gpu)
    ]

    if not candidates:
        # target을 맞출 수 없으면 최소한 한 pod라도 담을 수 있는 것 선택
        candidates = [
            f for f in available_flavors
            if f.get("vcpus_m", 0) >= max_pod_cpu_m
            and f.get("ram_bytes", 0) >= max_pod_mem
            and (not needs_gpu or f.get("gpu", 0) >= max_pod_gpu)
        ]

    if not candidates:
        return None

    # 최소 flavor (비용 최소화)
    return min(candidates, key=lambda f: (f.get("vcpus_m", 0), f.get("ram_bytes", 0)))


async def _get_available_flavors(project_id: str) -> list[dict]:
    """OpenStack flavor 목록 → Stampede용 구조로 변환."""
    from app.services import keystone

    try:
        conn = keystone.get_admin_connection_for_project(project_id)
        flavors_raw = list(conn.compute.flavors())
        result = []
        for f in flavors_raw:
            vcpus = getattr(f, "vcpus", 0) or 0
            ram_mb = getattr(f, "ram", 0) or 0
            extra_specs = getattr(f, "extra_specs", {}) or {}
            gpu = 0
            for k, v in extra_specs.items():
                if "pci_passthrough:alias" in k or "alias" in k:
                    try:
                        # 형식: "RTX3090:1" → gpu=1
                        gpu += int(str(v).split(":")[-1])
                    except (ValueError, IndexError):
                        pass
            result.append({
                "id": f.id,
                "name": f.name,
                "vcpus_m": vcpus * 1000,
                "ram_bytes": ram_mb * 1024 * 1024,
                "gpu": gpu,
            })
        return result
    except Exception as e:
        _logger.warning("_get_available_flavors 오류 (project=%s): %s", project_id, e)
        return []


async def _update_stampede_state(nodegroup_id: str, cluster_id: str, updates: dict) -> None:
    """nodegroup.stampede_state 를 원자적으로 갱신 (merge patch)."""
    from app.services import k3s_nodegroup

    current = await k3s_nodegroup.get_nodegroup(cluster_id, nodegroup_id)
    if not current:
        return
    state = dict(current.get("stampede_state") or {})
    state.update(updates)
    await k3s_nodegroup.update_nodegroup(cluster_id, nodegroup_id, {"stampede_state": state})


async def _get_stampede_state(nodegroup: dict) -> dict:
    return dict(nodegroup.get("stampede_state") or {})


# ---------------------------------------------------------------------------
# scale-up
# ---------------------------------------------------------------------------


async def _scale_up_nodegroup(
    cluster_id: str,
    project_id: str,
    nodegroup: dict,
    pending_pods: list[dict],
    node_pods: list[dict],
    node_capacities: list[dict],
    s,
) -> None:
    """nodegroup에 노드를 추가한다."""
    from app.services import k3s_nodegroup

    ng_id = nodegroup["id"]
    max_size = nodegroup.get("max_size", 5)
    node_count = nodegroup.get("node_count", 0)
    state = await _get_stampede_state(nodegroup)

    # 쿨다운 체크
    last_up = state.get("last_scale_up", 0)
    cooldown = s.k3s_stampede_scale_up_cooldown
    if time.time() - last_up < cooldown:
        _logger.debug("stampede: nodegroup %s scale-up 쿨다운 중 (%.0fs 남음)",
                      ng_id, cooldown - (time.time() - last_up))
        return

    # in-flight 노드 수 (아직 Ready 안 된 것)
    in_flight = state.get("in_flight_count", 0)
    # in-flight TTL: 40분 초과 시 stale로 간주해 0으로 리셋
    in_flight_since = state.get("in_flight_since", 0)
    if in_flight > 0 and time.time() - in_flight_since > 2400:  # 40분
        _logger.warning("stampede: nodegroup %s in-flight stale, 리셋", ng_id)
        in_flight = 0
        await _update_stampede_state(ng_id, cluster_id, {"in_flight_count": 0, "in_flight_since": 0})

    # 현재 노드의 가용 capacity 계산
    ng_node_names = {v["name"] for v in nodegroup.get("vms", []) if v.get("name")}
    ng_nodes = [n for n in node_capacities if n["name"] in ng_node_names and n["ready"]]
    ng_node_pod_map: dict[str, dict] = {n["name"]: n for n in ng_nodes}

    # 노드별 사용 중인 리소스 계산
    node_used: dict[str, dict] = {}
    for p in node_pods:
        nn = p.get("node", "")
        if nn not in ng_node_pod_map:
            continue
        if nn not in node_used:
            node_used[nn] = {"cpu_m": 0, "memory_bytes": 0}
        node_used[nn]["cpu_m"] += p["cpu_m"]
        node_used[nn]["memory_bytes"] += p["memory_bytes"]

    # 기존 노드에 스케줄 가능한 pod는 scale-up 필요 없음
    unresolvable_pods = []
    for pod in pending_pods:
        schedulable_on_existing = False
        for node in ng_nodes:
            used = node_used.get(node["name"], {"cpu_m": 0, "memory_bytes": 0})
            alloc = node["allocatable"]
            free_cpu = alloc["cpu_m"] - used["cpu_m"]
            free_mem = alloc["memory_bytes"] - used["memory_bytes"]
            req = pod["resource_requests"]
            if req["cpu_m"] <= free_cpu and req["memory_bytes"] <= free_mem:
                schedulable_on_existing = True
                break
        if not schedulable_on_existing:
            unresolvable_pods.append(pod)

    if not unresolvable_pods:
        _logger.debug("stampede: nodegroup %s — pending pod 없음 또는 기존 노드로 해결 가능", ng_id)
        return

    # max 초과 체크
    if node_count + in_flight >= max_size:
        _logger.warning(
            "stampede: nodegroup %s — max_size(%d) 도달, scale-up 중단. "
            "pending pod %d개 해결 불가",
            ng_id, max_size, len(unresolvable_pods)
        )
        return

    # flavor 선택
    available_flavors = await _get_available_flavors(project_id)
    if not available_flavors:
        _logger.warning("stampede: nodegroup %s — flavor 목록 조회 실패, scale-up 중단", ng_id)
        return

    ng_flavor_id = nodegroup.get("flavor_id")
    if ng_flavor_id:
        # nodegroup에 지정된 flavor 사용
        flavor = next((f for f in available_flavors if f["id"] == ng_flavor_id), None)
    else:
        # 가중치 기반 자동 선택
        flavor = _select_flavor(
            unresolvable_pods,
            node_pods,
            available_flavors,
            nodegroup,
            s.k3s_stampede_resource_headroom_factor,
        )

    if not flavor:
        _logger.warning(
            "stampede: nodegroup %s — 적합한 flavor 없음 (pod requests 초과?). "
            "pending pod: cpu=%dm mem=%dMi",
            ng_id,
            max((p["resource_requests"]["cpu_m"] for p in unresolvable_pods), default=0),
            max((p["resource_requests"]["memory_bytes"] for p in unresolvable_pods), default=0) // (1024**2),
        )
        return

    # 필요한 노드 수 계산: unresolvable_pods를 한 노드에 몇 개나 담을 수 있는지
    max_fit = max(1, flavor["vcpus_m"] // max(p["resource_requests"]["cpu_m"] for p in unresolvable_pods
                                               if p["resource_requests"]["cpu_m"] > 0)
                  if any(p["resource_requests"]["cpu_m"] > 0 for p in unresolvable_pods) else 1)
    add_count = min(
        max(1, -(-len(unresolvable_pods) // max_fit)),  # ceil division
        max_size - node_count - in_flight,
    )

    _logger.info(
        "stampede: nodegroup %s scale-up %d개 (flavor=%s, unresolvable_pods=%d, in_flight=%d)",
        ng_id, add_count, flavor["name"], len(unresolvable_pods), in_flight
    )

    # in-flight 증가 (즉시 DB 갱신 → 다음 루프에서 중복 scale-up 방지)
    await _update_stampede_state(ng_id, cluster_id, {
        "in_flight_count": in_flight + add_count,
        "in_flight_since": time.time(),
        "last_scale_up": time.time(),
    })
    # node_count도 즉시 증가
    await k3s_nodegroup.update_nodegroup(cluster_id, ng_id, {
        "node_count": node_count + add_count,
    })

    # 비동기 VM 프로비저닝 시작 (fire-and-forget, in-flight 해소는 태스크 완료 시)
    asyncio.create_task(
        _provision_and_track(
            project_id=project_id,
            cluster_id=cluster_id,
            nodegroup_id=ng_id,
            add_count=add_count,
            flavor_id=flavor["id"],
            image_id=nodegroup.get("image_id"),
            labels=nodegroup.get("labels"),
            taints=nodegroup.get("taints"),
        )
    )


async def _provision_and_track(
    project_id: str,
    cluster_id: str,
    nodegroup_id: str,
    add_count: int,
    flavor_id: str,
    image_id: str | None,
    labels: dict | None,
    taints: list | None,
) -> None:
    """VM 프로비저닝 후 Ready 대기, in-flight 카운터 감소."""
    from app.services import k3s_autoscale, k3s_kube, k3s_nodegroup

    new_vms = await k3s_autoscale.provision_nodegroup_vms(
        project_id=project_id,
        cluster_id=cluster_id,
        nodegroup_id=nodegroup_id,
        add_count=add_count,
        flavor_id=flavor_id,
        image_id=image_id,
        labels=labels,
        taints=taints,
    )

    # VM Ready 대기 (최대 40분)
    for vm in new_vms:
        node_name = vm.get("name", "")
        if node_name:
            ready = await k3s_kube.wait_node_ready(cluster_id, node_name, timeout=2400.0)
            if ready:
                await k3s_nodegroup.update_nodegroup(cluster_id, nodegroup_id, {})  # updated_at 갱신
                _logger.info("stampede: node %s Ready 확인됨", node_name)
            else:
                _logger.warning("stampede: node %s Ready 대기 timeout (40분)", node_name)

    # 실제 생성된 수만큼 in-flight 감소 (실패한 것 포함 보정)
    ng = await k3s_nodegroup.get_nodegroup(cluster_id, nodegroup_id)
    if ng:
        state = dict(ng.get("stampede_state") or {})
        current_in_flight = max(0, state.get("in_flight_count", 0) - len(new_vms))
        await _update_stampede_state(nodegroup_id, cluster_id, {
            "in_flight_count": current_in_flight,
        })


# ---------------------------------------------------------------------------
# scale-down
# ---------------------------------------------------------------------------


async def _scale_down_nodegroup(
    cluster_id: str,
    project_id: str,
    nodegroup: dict,
    node_pods: list[dict],
    node_capacities: list[dict],
    s,
) -> None:
    """nodegroup의 유휴 노드를 cordon→drain→삭제한다."""
    from app.services import k3s_autoscale, k3s_nodegroup

    ng_id = nodegroup["id"]
    min_size = nodegroup.get("min_size", 0)
    node_count = nodegroup.get("node_count", 0)
    state = await _get_stampede_state(nodegroup)

    if node_count <= min_size:
        return

    # 쿨다운 체크
    last_down = state.get("last_scale_down", 0)
    cooldown = s.k3s_stampede_scale_down_cooldown
    if time.time() - last_down < cooldown:
        return

    threshold = s.k3s_stampede_scale_down_threshold
    window = s.k3s_stampede_scale_down_window
    interval = s.k3s_stampede_interval

    ng_node_names = {v["name"] for v in nodegroup.get("vms", []) if v.get("name")}
    ng_nodes = [n for n in node_capacities if n["name"] in ng_node_names and n["ready"]]

    # 노드별 사용률 계산
    node_used: dict[str, dict] = {}
    for p in node_pods:
        nn = p.get("node", "")
        if nn not in {n["name"] for n in ng_nodes}:
            continue
        if nn not in node_used:
            node_used[nn] = {"cpu_m": 0, "memory_bytes": 0}
        node_used[nn]["cpu_m"] += p["cpu_m"]
        node_used[nn]["memory_bytes"] += p["memory_bytes"]

    # 유휴 노드 후보 (사용률 < threshold)
    idle_nodes = []
    for node in ng_nodes:
        alloc = node["allocatable"]
        used = node_used.get(node["name"], {"cpu_m": 0, "memory_bytes": 0})
        if alloc["cpu_m"] <= 0:
            continue
        utilization = used["cpu_m"] / alloc["cpu_m"]
        if utilization < threshold:
            idle_nodes.append(node)

    if not idle_nodes:
        # 유휴 노드 없음 → consecutive_idle_checks 리셋
        await _update_stampede_state(ng_id, cluster_id, {"consecutive_idle_checks": 0})
        return

    # stabilization window: 연속 유휴 체크 횟수
    consecutive = state.get("consecutive_idle_checks", 0) + 1
    await _update_stampede_state(ng_id, cluster_id, {"consecutive_idle_checks": consecutive})

    if consecutive * interval < window:
        _logger.debug(
            "stampede: nodegroup %s — 유휴 노드 %d개, stabilization window 대기 (%d/%ds)",
            ng_id, len(idle_nodes), consecutive * interval, window,
        )
        return

    # 삭제 대상: 빈 노드 우선 (DaemonSet/mirror pod만 있는 노드)
    # reverse fit-check: drain할 pod들이 다른 노드에 배치 가능한지
    remove_node = idle_nodes[0]  # Phase 1: 가장 유휴인 노드 1개씩 제거
    remove_name = remove_node["name"]

    # 해당 노드 VM 찾기
    vm_entry = next(
        (v for v in nodegroup.get("vms", []) if v.get("name") == remove_name),
        None,
    )
    if not vm_entry:
        _logger.warning("stampede: scale-down — %s VM 레코드 없음", remove_name)
        return

    _logger.info("stampede: nodegroup %s scale-down — node %s 제거 시작", ng_id, remove_name)

    # node_count 감소 + 쿨다운 갱신
    await k3s_nodegroup.update_nodegroup(cluster_id, ng_id, {
        "node_count": max(min_size, node_count - 1),
    })
    await _update_stampede_state(ng_id, cluster_id, {
        "last_scale_down": time.time(),
        "consecutive_idle_checks": 0,
    })

    # 비동기 삭제
    asyncio.create_task(
        k3s_autoscale.delete_nodegroup_vms(
            project_id=project_id,
            cluster_id=cluster_id,
            nodegroup_id=ng_id,
            vm_entries=[vm_entry],
        )
    )


# ---------------------------------------------------------------------------
# 메인 reconcile 루프
# ---------------------------------------------------------------------------


async def reconcile_cluster(cluster: dict) -> None:
    """클러스터 1개의 Stampede nodegroup을 순회해 scale-up/down 판단."""
    from app.services import k3s_kube, k3s_nodegroup

    cluster_id = cluster.get("id") or cluster.get("cluster_id", "")
    project_id = cluster.get("project_id", "")

    if not cluster_id or not project_id:
        return

    s = get_settings()

    # 클러스터의 stampede nodegroup 목록
    all_nodegroups = await k3s_nodegroup.list_nodegroups(cluster_id)
    stampede_ngs = [ng for ng in all_nodegroups if ng.get("stampede_enabled")]

    if not stampede_ngs:
        return

    # K8s 상태 조회 (1회 조회 후 재사용)
    try:
        pending_pods = await k3s_kube.list_unschedulable_pods(cluster_id)
        node_capacities = await k3s_kube.get_node_capacity(cluster_id)
        node_pods = await k3s_kube.get_pod_resource_usage(cluster_id)
    except Exception as e:
        _logger.warning("stampede: cluster %s K8s API 조회 실패: %s", cluster_id, e)
        return

    for ng in stampede_ngs:
        ng_id = ng["id"]
        try:
            # 이 노드그룹에 할당될 pending pod 필터
            ng_pending = [
                p for p in pending_pods
                if _node_matches_nodegroup(p, ng) and not _is_pvc_issue(p)
            ]

            if ng_pending:
                await _scale_up_nodegroup(
                    cluster_id=cluster_id,
                    project_id=project_id,
                    nodegroup=ng,
                    pending_pods=ng_pending,
                    node_pods=node_pods,
                    node_capacities=node_capacities,
                    s=s,
                )
            else:
                await _scale_down_nodegroup(
                    cluster_id=cluster_id,
                    project_id=project_id,
                    nodegroup=ng,
                    node_pods=node_pods,
                    node_capacities=node_capacities,
                    s=s,
                )
        except Exception:
            _logger.exception("stampede: nodegroup %s reconcile 오류", ng_id)


async def run_all() -> None:
    """모든 ACTIVE + stampede_enabled 클러스터를 순회해 reconcile 실행."""
    from app.services import k3s_db

    s = get_settings()
    if not s.k3s_stampede_enabled:
        return

    try:
        all_clusters = await k3s_db.list_all_clusters(include_deleted=False)
    except Exception as e:
        _logger.warning("stampede: 클러스터 목록 조회 실패: %s", e)
        return

    active_stampede = [
        c for c in all_clusters
        if c.get("status") == "ACTIVE" and c.get("stampede_enabled")
    ]

    if not active_stampede:
        return

    _logger.info("stampede: reconcile 시작 — %d개 클러스터", len(active_stampede))

    tasks = [reconcile_cluster(c) for c in active_stampede]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for c, r in zip(active_stampede, results, strict=False):
        if isinstance(r, Exception):
            _logger.error("stampede: cluster %s reconcile 예외: %s", c.get("id"), r)
