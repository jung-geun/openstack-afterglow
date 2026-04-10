"""
cloud-init userdata 생성 엔진.

Jinja2 템플릿을 이용해 CephX 크리덴셜과 OverlayFS 구성을 담은
cloud-init YAML을 생성한다.

지원 프로토콜: CephFS, NFS
OverlayFS 구조: /opt/layers/{lower,upper,work,merged}
"""
import base64
import shlex
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.config import get_settings
from app.services import libraries as lib_svc

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_jinja = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
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


def generate_userdata(
    libraries: list[str],
    strategy: str,
    file_storages: list[dict],
    upper_device: str,
    ceph_monitors: str,
    gpu_available: bool = False,
) -> str:
    """
    cloud-init userdata 문자열(YAML) 생성.

    Args:
        libraries: 선택된 라이브러리 ID 목록 (의존성 포함, 토폴로지 정렬)
        strategy: "prebuilt" | "dynamic"
        file_storages: [
            {
              name: str,                # 라이브러리 ID (디렉토리명에 사용)
              share_proto: str,         # "CEPHFS" | "NFS"
              export_path: str,         # CephFS export location (CEPHFS인 경우)
              cephx_id: str,           # CephX 사용자 ID (CEPHFS인 경우)
              cephx_key: str,           # CephX secret key (CEPHFS인 경우)
              nfs_export_location: str, # NFS export 경로 (NFS인 경우)
              mount_options: str,       # NFS 마운트 옵션 (선택)
            }
        ]
        upper_device: Cinder upper 볼륨 장치 경로 (예: /dev/vdb)
        ceph_monitors: 쉼표 구분 모니터 주소
        gpu_available: GPU 플레이버 여부 (PyTorch CUDA 인덱스 선택)
    """
    resolved_libs = lib_svc.resolve_with_deps(libraries)

    # lowerdir 체인 생성 (의존성이 높은 라이브러리가 앞에 오도록)
    # 역순으로 정렬하여 가장 구체적인(의존성이 높은) 라이브러리가 맨 앞에 오도록 함
    # 예: vllm:torch:python311 → lowerdir=vllm:torch:python311
    lowerdir_paths = [f"/opt/layers/lower_{s['name']}" for s in file_storages]

    # PYTHONPATH 동적 생성
    python_version = "3.11"  # 기본 Python 버전
    for lib in resolved_libs:
        if lib.id == "python311":
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

    # CephFS 관련 정보가 필요한지 확인
    has_cephfs = any(fs.get("share_proto", "CEPHFS") == "CEPHFS" for fs in file_storages)
    has_nfs = any(fs.get("share_proto", "CEPHFS") == "NFS" for fs in file_storages)

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
    )

    # Nova는 userdata를 base64로 인코딩해서 전달
    return base64.b64encode(yaml_str.encode()).decode()