"""
cloud-init userdata 생성 엔진.

Jinja2 템플릿을 이용해 CephX 크리덴셜과 OverlayFS 구성을 담은
cloud-init YAML을 생성한다.
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
    shares: list[dict],
    upper_device: str,
    ceph_monitors: str,
    gpu_available: bool = False,
) -> str:
    """
    cloud-init userdata 문자열(YAML) 생성.

    Args:
        libraries: 선택된 라이브러리 ID 목록 (의존성 포함, 토폴로지 정렬)
        strategy: "prebuilt" | "dynamic"
        shares: [
            {
              name: str,           # Manila share 이름 (디렉토리명에 사용)
              export_path: str,    # CephFS export location
              cephx_id: str,       # CephX 사용자 ID
              cephx_key: str,      # CephX secret key
            }
        ]
        upper_device: Cinder upper 볼륨 장치 경로 (예: /dev/vdb)
        ceph_monitors: 쉼표 구분 모니터 주소
        gpu_available: GPU 플레이버 여부 (PyTorch CUDA 인덱스 선택)
    """
    resolved_libs = lib_svc.resolve_with_deps(libraries)

    # lowerdir 체인 생성 (우선순위 높은 것이 앞)
    # 순서: 최상위 라이브러리 → 하위 의존성 → 기본 OS 경로
    reversed_libs = list(reversed(resolved_libs))

    lowerdir_usr_local = ":".join(
        [f"/mnt/union/lib_{s['name']}/usr_local" for s in shares]
        + ["/usr/local"]
    )
    lowerdir_opt = ":".join(
        [f"/mnt/union/lib_{s['name']}/opt" for s in shares]
        + ["/opt"]
    )

    overlay_script = _jinja.get_template("overlay_setup.sh.j2").render(
        shares=shares,
        upper_device=upper_device,
        lowerdir_usr_local=lowerdir_usr_local,
        lowerdir_opt=lowerdir_opt,
    )

    dynamic_script = ""
    if strategy == "dynamic":
        dynamic_script = _jinja.get_template("strategy_dynamic.sh.j2").render(
            libraries=resolved_libs,
            versions=_VERSIONS,
            gpu_available=gpu_available,
        )

    yaml_str = _jinja.get_template("cloudinit_base.yaml.j2").render(
        strategy=strategy,
        libraries=resolved_libs,
        shares=shares,
        ceph_monitors=ceph_monitors,
        overlay_script=overlay_script,
        dynamic_script=dynamic_script,
        upper_device=upper_device,
    )

    # Nova는 userdata를 base64로 인코딩해서 전달
    return base64.b64encode(yaml_str.encode()).decode()
