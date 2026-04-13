"""k3s 클러스터 상태 관리 — Redis CRUD + 콜백 토큰 처리."""

import json
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.services.cache import _get_client
from app.services.k3s_crypto import encrypt_kubeconfig, decrypt_kubeconfig

_logger = logging.getLogger(__name__)

_CALLBACK_TTL = 1800  # 30분


# ---------------------------------------------------------------------------
# 키 헬퍼
# ---------------------------------------------------------------------------

def _cluster_key(project_id: str, cluster_id: str) -> str:
    return f"union:k3s:{project_id}:cluster:{cluster_id}"


def _clusters_set_key(project_id: str) -> str:
    return f"union:k3s:{project_id}:clusters"


def _kubeconfig_key(project_id: str, cluster_id: str) -> str:
    return f"union:k3s:{project_id}:kubeconfig:{cluster_id}"


def _callback_key(token: str) -> str:
    return f"union:k3s:callback:{token}"


# ---------------------------------------------------------------------------
# Cluster CRUD
# ---------------------------------------------------------------------------

async def create_cluster_record(project_id: str, cluster_id: str, data: dict) -> None:
    """클러스터 HASH 생성 + 프로젝트 SET에 ID 추가."""
    client = _get_client()
    key = _cluster_key(project_id, cluster_id)
    # HASH는 모든 값을 문자열로 저장
    str_data = {k: json.dumps(v) if isinstance(v, (list, dict)) else str(v) if v is not None else "" for k, v in data.items()}
    await client.hset(key, mapping=str_data)
    await client.sadd(_clusters_set_key(project_id), cluster_id)


async def get_cluster(project_id: str, cluster_id: str) -> Optional[dict]:
    """클러스터 HASH → dict 반환. 없으면 None."""
    client = _get_client()
    raw = await client.hgetall(_cluster_key(project_id, cluster_id))
    if not raw:
        return None
    result: dict = {}
    for k, v in raw.items():
        k_str = k.decode() if isinstance(k, bytes) else k
        v_str = v.decode() if isinstance(v, bytes) else v
        # agent_vm_ids는 JSON 배열로 저장
        if k_str == "agent_vm_ids":
            try:
                result[k_str] = json.loads(v_str) if v_str else []
            except Exception:
                result[k_str] = []
        else:
            result[k_str] = v_str if v_str != "" else None
    result["id"] = cluster_id
    return result


async def list_clusters(project_id: str) -> list[dict]:
    """프로젝트의 모든 클러스터 목록 반환."""
    client = _get_client()
    ids = await client.smembers(_clusters_set_key(project_id))
    clusters = []
    for cid_bytes in ids:
        cid = cid_bytes.decode() if isinstance(cid_bytes, bytes) else cid_bytes
        cluster = await get_cluster(project_id, cid)
        if cluster:
            clusters.append(cluster)
    clusters.sort(key=lambda c: c.get("created_at") or "", reverse=True)
    return clusters


async def update_cluster_status(
    project_id: str,
    cluster_id: str,
    status: str,
    status_reason: Optional[str] = None,
    **extra_fields,
) -> None:
    """클러스터 status + updated_at + 추가 필드 업데이트."""
    client = _get_client()
    key = _cluster_key(project_id, cluster_id)
    updates: dict = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if status_reason is not None:
        updates["status_reason"] = status_reason
    for k, v in extra_fields.items():
        if isinstance(v, (list, dict)):
            updates[k] = json.dumps(v)
        elif v is None:
            updates[k] = ""
        else:
            updates[k] = str(v)
    await client.hset(key, mapping=updates)


async def delete_cluster_record(project_id: str, cluster_id: str) -> None:
    """클러스터 HASH, kubeconfig 키, SET 항목 삭제."""
    client = _get_client()
    await client.delete(_cluster_key(project_id, cluster_id))
    await client.delete(_kubeconfig_key(project_id, cluster_id))
    await client.srem(_clusters_set_key(project_id), cluster_id)


# ---------------------------------------------------------------------------
# 콜백 토큰
# ---------------------------------------------------------------------------

async def create_callback_token(project_id: str, cluster_id: str) -> str:
    """일회성 콜백 토큰 생성 (TTL 30분)."""
    token = secrets.token_urlsafe(48)
    client = _get_client()
    payload = json.dumps({"project_id": project_id, "cluster_id": cluster_id})
    await client.setex(_callback_key(token), _CALLBACK_TTL, payload)
    return token


async def consume_callback_token(token: str) -> Optional[dict]:
    """콜백 토큰을 원자적으로 GET+DELETE. 없거나 만료되면 None."""
    client = _get_client()
    key = _callback_key(token)
    raw = await client.getdel(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Kubeconfig
# ---------------------------------------------------------------------------

async def store_kubeconfig(project_id: str, cluster_id: str, kubeconfig_yaml: str) -> None:
    """kubeconfig를 AES-256-GCM 암호화하여 Redis에 저장."""
    client = _get_client()
    encrypted = encrypt_kubeconfig(kubeconfig_yaml)
    await client.set(_kubeconfig_key(project_id, cluster_id), encrypted)


async def get_kubeconfig(project_id: str, cluster_id: str) -> Optional[str]:
    """Redis에서 kubeconfig를 복호화하여 반환. 없으면 None."""
    client = _get_client()
    raw = await client.get(_kubeconfig_key(project_id, cluster_id))
    if not raw:
        return None
    raw_str = raw.decode() if isinstance(raw, bytes) else raw
    return decrypt_kubeconfig(raw_str)


# ---------------------------------------------------------------------------
# 스테일 클러스터 정리
# ---------------------------------------------------------------------------

async def check_stale_clusters(timeout_minutes: int = 30) -> None:
    """CREATING 상태에서 timeout_minutes 초과한 클러스터를 ERROR로 변경."""
    client = _get_client()
    # 모든 프로젝트의 k3s 클러스터 SET 키 스캔
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    try:
        async for key in client.scan_iter("union:k3s:*:clusters"):
            key_str = key.decode() if isinstance(key, bytes) else key
            # union:k3s:{project_id}:clusters 형식에서 project_id 추출
            parts = key_str.split(":")
            if len(parts) != 4:
                continue
            project_id = parts[2]
            ids = await client.smembers(key_str)
            for cid_bytes in ids:
                cid = cid_bytes.decode() if isinstance(cid_bytes, bytes) else cid_bytes
                cluster = await get_cluster(project_id, cid)
                if not cluster or cluster.get("status") != "CREATING":
                    continue
                created_at_str = cluster.get("created_at")
                if not created_at_str:
                    continue
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    if created_at < cutoff:
                        await update_cluster_status(
                            project_id, cid, "ERROR",
                            "콜백 타임아웃: 서버 VM이 k3s 설치 후 응답하지 않았습니다."
                        )
                        _logger.warning("k3s cluster %s marked as ERROR (stale)", cid)
                except Exception:
                    pass
    except Exception as e:
        _logger.warning("k3s stale cluster check error: %s", e)
