"""
cloud-init userdata 생성 엔진.

Jinja2 템플릿을 이용해 CephX 크리덴셜과 OverlayFS 구성을 담은
cloud-init YAML을 생성한다.

지원 프로토콜: CephFS, NFS
OverlayFS 구조: /opt/layers/{lower,upper,work,merged}
"""

import base64
import re
import shlex
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.services import libraries as lib_svc

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_jinja = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    # 출력은 YAML/Bash 라 HTML autoescape 는 의미 없음 — 명시적으로 비활성하고,
    # 모든 사용자 입력은 템플릿 측에서 반드시 `| shlex_quote` 를 거치도록 한다.
    autoescape=False,
)
# shell 인자로 안전하게 사용하기 위한 이스케이프 필터
_jinja.filters["shlex_quote"] = shlex.quote

# 라이브러리별 패키지 버전 기본값
_VERSIONS = {
    "torch": "2.4.0",
    "torchvision": "0.19.0",
    "torchaudio": "2.4.0",
    "vllm": "0.6.0",
    "jupyter": "4.2.0",
}

_DCGM_EXPORTER_VERSION = "4.2.0-4.1.0"

# cloud-init YAML에 보간되는 값의 형식 검증 — 개행/특수문자로 YAML 구조가
# 파괴되어 임의 write_files/runcmd가 주입되는 것을 차단한다 (심층 방어).
_CEPHX_KEY_RE = re.compile(r"^[A-Za-z0-9+/=]{1,128}$")
_CEPHX_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_CEPH_MONITORS_RE = re.compile(r"^[0-9A-Za-z.,:\[\]_-]+$")


def _validate_cloudinit_inputs(file_storages: list[dict], ceph_monitors: str) -> None:
    """cloud-init 템플릿 보간 값 형식 검증. 불일치 시 ValueError."""
    for fs in file_storages:
        if fs.get("share_proto", "CEPHFS") != "CEPHFS":
            continue
        cephx_id = fs.get("cephx_id", "")
        cephx_key = fs.get("cephx_key", "")
        if cephx_id and not _CEPHX_ID_RE.match(cephx_id):
            raise ValueError(f"유효하지 않은 cephx_id 형식: {cephx_id!r}")
        if cephx_key and not _CEPHX_KEY_RE.match(cephx_key):
            raise ValueError("유효하지 않은 cephx_key 형식 (base64 문자만 허용)")
    if ceph_monitors and not _CEPH_MONITORS_RE.match(ceph_monitors):
        raise ValueError(f"유효하지 않은 ceph_monitors 형식: {ceph_monitors!r}")


def generate_userdata(
    libraries: list[str],
    strategy: str,
    file_storages: list[dict],
    upper_device: str,
    ceph_monitors: str,
    gpu_available: bool = False,
    instance_id: str = "",
    report_url: str = "",
    report_token: str = "",
    union_ro_share_export: str | None = None,
    union_manifest_share_export: str | None = None,
    union_cephx_rotate_hours: int = 0,
    data_mounts: list[dict] | None = None,
) -> str:
    """
    cloud-init userdata 문자열(YAML) 생성.

    Args:
        libraries: 선택된 라이브러리 ID 목록 (의존성 포함, 토폴로지 정렬)
        strategy: "prebuilt" | "dynamic"
        file_storages: [{name, share_proto, export_path, cephx_id, cephx_key,
                         nfs_export_location, mount_options}]
        upper_device: Cinder upper 볼륨 장치 경로 (예: /dev/vdb)
        ceph_monitors: 쉼표 구분 모니터 주소
        gpu_available: GPU 플레이버 여부 (PyTorch CUDA 인덱스 선택)
        instance_id: Nova 인스턴스 ID (헬스 리포트용)
        report_url: 백엔드 베이스 URL (헬스 리포트용)
        report_token: 헬스 리포트 토큰 (헬스 리포트용)
    """
    _validate_cloudinit_inputs(file_storages, ceph_monitors)
    _data_mounts = data_mounts or []
    for dm in _data_mounts:
        if dm.get("share_proto", "CEPHFS") == "CEPHFS":
            cephx_id = dm.get("cephx_id", "")
            cephx_key = dm.get("cephx_key", "")
            if cephx_id and not _CEPHX_ID_RE.match(cephx_id):
                raise ValueError(f"data_mounts: 유효하지 않은 cephx_id 형식: {cephx_id!r}")
            if cephx_key and not _CEPHX_KEY_RE.match(cephx_key):
                raise ValueError("data_mounts: 유효하지 않은 cephx_key 형식 (base64 문자만 허용)")

    resolved_libs = lib_svc.resolve_with_deps(libraries)

    # lowerdir 체인 생성 (의존성이 높은 라이브러리가 앞에 오도록)
    # 역순으로 정렬하여 가장 구체적인(의존성이 높은) 라이브러리가 맨 앞에 오도록 함
    # 예: vllm:torch:python311 → lowerdir=vllm:torch:python311
    lowerdir_paths = [f"/opt/layers/lower_{s['name']}" for s in file_storages]

    # PYTHONPATH 동적 생성
    python_version = "3.11"  # 기본 Python 버전
    for lib in resolved_libs:
        if lib == "python311":
            python_version = "3.11"
            break
    pythonpath = f"/opt/layers/merged/usr/local/lib/python{python_version}/site-packages"

    overlay_script = _jinja.get_template("overlay_setup.sh.j2").render(
        file_storages=file_storages,
        upper_device=upper_device,
        lowerdirs=":".join(lowerdir_paths),
        pythonpath=pythonpath,
        gpu_available=gpu_available,
    )

    dynamic_script = ""
    if strategy == "dynamic":
        dynamic_script = _jinja.get_template("strategy_dynamic.sh.j2").render(
            libraries=resolved_libs,
            versions=_VERSIONS,
            gpu_available=gpu_available,
        )

    # CephFS 관련 정보가 필요한지 확인 (data_mounts 포함)
    has_cephfs = any(fs.get("share_proto", "CEPHFS") == "CEPHFS" for fs in file_storages) or \
                 any(dm.get("share_proto") == "CEPHFS" for dm in _data_mounts)
    has_nfs = any(fs.get("share_proto", "CEPHFS") == "NFS" for fs in file_storages) or \
              any(dm.get("share_proto") == "NFS" for dm in _data_mounts)

    health_check_script = ""
    if report_url and instance_id and report_token:
        health_check_script = _jinja.get_template("health_check.sh.j2").render(
            report_url=report_url,
            instance_id=instance_id,
            report_token=report_token,
            file_storages=file_storages,
        )

    rotate_key_script = ""
    if union_cephx_rotate_hours > 0:
        rotate_key_script = _jinja.get_template("envmgr_rotate_key.sh.j2").render(
            union_cephx_rotate_hours=union_cephx_rotate_hours,
        )

    data_mounts_script = ""
    if _data_mounts:
        data_mounts_script = _jinja.get_template("data_mounts.sh.j2").render(
            data_mounts=_data_mounts,
        )

    yaml_str = _jinja.get_template("cloudinit_base.yaml.j2").render(
        strategy=strategy,
        libraries=resolved_libs,
        file_storages=file_storages,
        ceph_monitors=ceph_monitors,
        overlay_script=overlay_script,
        dynamic_script=dynamic_script,
        upper_device=upper_device,
        has_cephfs=has_cephfs,
        has_nfs=has_nfs,
        gpu_available=gpu_available,
        pythonpath=pythonpath,
        report_url=report_url,
        health_check_script=health_check_script,
        union_ro_share_export=union_ro_share_export or "",
        union_manifest_share_export=union_manifest_share_export or "",
        union_cephx_rotate_hours=union_cephx_rotate_hours,
        rotate_key_script=rotate_key_script,
        dcgm_exporter_version=_DCGM_EXPORTER_VERSION,
        data_mounts=_data_mounts,
        data_mounts_script=data_mounts_script,
    )

    # Nova는 userdata를 base64로 인코딩해서 전달
    return base64.b64encode(yaml_str.encode()).decode()
