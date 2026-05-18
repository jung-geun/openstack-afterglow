"""k3s 인증서 API — CA 다운로드, 만료 조회."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.deps import get_token_info
from app.models.k3s import CertificateExpiryResponse, CertificateInfo
from app.services import k3s_db
from app.services.cache import cached_call
from app.services.cache import keys as cache_keys

router = APIRouter()
_logger = logging.getLogger(__name__)

_CERT_EXPIRY_TTL = 3600  # 1h


async def _get_kubeconfig_for_user(project_id: str, cluster_id: str) -> str:
    """클러스터 접근 권한 확인 + kubeconfig 반환. 없으면 404."""
    cluster = await k3s_db.get_cluster(project_id, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다.")
    kc = await k3s_db.get_kubeconfig(project_id, cluster_id)
    if not kc:
        raise HTTPException(status_code=404, detail="kubeconfig를 찾을 수 없습니다. 클러스터가 아직 초기화 중일 수 있습니다.")
    return kc


@router.get("/{cluster_id}/ca-certificate")
async def download_ca_certificate(
    cluster_id: str,
    token_info: dict = Depends(get_token_info),
):
    """k3s 클러스터 CA 인증서 PEM 다운로드."""
    project_id = token_info["project_id"]
    kc = await _get_kubeconfig_for_user(project_id, cluster_id)

    from app.services.k3s_certs import extract_ca_pem

    try:
        pem = extract_ca_pem(kc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CA 인증서 추출 실패: {e}")

    cluster = await k3s_db.get_cluster(project_id, cluster_id)
    cluster_name = (cluster or {}).get("name", cluster_id)
    _logger.info("k3s CA 다운로드: cluster=%s project=%s", cluster_id, project_id)

    return Response(
        content=pem.encode(),
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f'attachment; filename="ca-{cluster_name}.pem"'},
    )


@router.get("/{cluster_id}/certificate-expiry", response_model=CertificateExpiryResponse)
async def get_certificate_expiry(
    cluster_id: str,
    token_info: dict = Depends(get_token_info),
):
    """k3s 클러스터 인증서 만료 조회 (CA, 클라이언트, 서버 TLS)."""
    project_id = token_info["project_id"]
    kc = await _get_kubeconfig_for_user(project_id, cluster_id)

    cache_key = cache_keys.project_key("k3s", project_id, cluster_id, sub="cert_expiry")

    async def _compute() -> dict:
        from app.services.k3s_certs import parse_kubeconfig_certs, probe_tls_server_cert

        certs = parse_kubeconfig_certs(kc)

        # 서버 IP 추출 → TLS 프로브
        server_via_tls: list[dict] = []
        try:
            import yaml

            parsed = yaml.safe_load(kc)
            server_url = parsed["clusters"][0]["cluster"]["server"]
            # https://<host>:<port>
            host = server_url.split("//")[-1].split(":")[0]
            port_str = server_url.split(":")[-1].split("/")[0]
            port = int(port_str) if port_str.isdigit() else 6443
            server_via_tls = await probe_tls_server_cert(host, port)
        except Exception as e:
            _logger.debug("TLS 프로브 실패: %s", e)

        return {
            "ca": certs.get("ca"),
            "client": certs.get("client"),
            "server_via_tls": server_via_tls,
        }

    data = await cached_call(cache_key, _CERT_EXPIRY_TTL, _compute)

    def _to_info(d: dict | None) -> CertificateInfo | None:
        if not d:
            return None
        return CertificateInfo(**d)

    return CertificateExpiryResponse(
        ca=_to_info(data.get("ca")),
        client=_to_info(data.get("client")),
        server_via_tls=[CertificateInfo(**s) for s in (data.get("server_via_tls") or [])],
    )
