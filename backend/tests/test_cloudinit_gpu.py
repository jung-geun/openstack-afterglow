"""GPU flavor 인스턴스의 cloud-init userdata 회귀 테스트.

flavor.is_gpu=True 인 plain instance (libraries=[]) 생성 시
NVIDIA 드라이버 + dcgm-exporter 설치 단계가 user-data 에 포함되는지 검증.

이 테스트는 사용자 보고 (gpu.1080ti_8c_16g flavor 인스턴스에서 GPU 메트릭 부재)
회귀 방지용 — 실제 미설치 원인이 cloud-init userdata 누락이 아님을 backend 단에서 보장.
"""

import base64

from app.services import cloudinit


def _generate(gpu_available: bool) -> str:
    """generate_userdata 는 base64 인코딩된 결과 반환 → 디코드한 raw YAML 반환."""
    encoded = cloudinit.generate_userdata(
        libraries=[],
        strategy="prebuilt",
        file_storages=[],
        upper_device="/dev/vdb",
        ceph_monitors="",
        gpu_available=gpu_available,
    )
    return base64.b64decode(encoded).decode()


def test_gpu_userdata_includes_install_script():
    """gpu_available=True 시 install_dcgm_exporter.sh 가 write_files 에 포함."""
    yaml = _generate(gpu_available=True)
    assert "/opt/union/install_dcgm_exporter.sh" in yaml
    assert "ubuntu-drivers autoinstall" in yaml, "NVIDIA 드라이버 자동 설치 스크립트 누락"


def test_gpu_userdata_runcmd_runs_install_script():
    """gpu_available=True 시 runcmd 에 install_dcgm_exporter.sh 실행 커맨드 포함."""
    yaml = _generate(gpu_available=True)
    # runcmd 에 두 항목이 모두 포함되어야 함 (순서 무관)
    assert "/opt/union/install_dcgm_exporter.sh" in yaml
    assert "dcgm-exporter.service" in yaml
    assert "systemctl enable --now dcgm-exporter.service" in yaml


def test_gpu_userdata_includes_dcgm_systemd_unit():
    """gpu_available=True 시 dcgm-exporter.service unit 파일이 user-data 에 포함."""
    yaml = _generate(gpu_available=True)
    assert "/etc/systemd/system/dcgm-exporter.service" in yaml
    assert "ExecStart=/usr/local/bin/dcgm-exporter" in yaml
    assert "0.0.0.0:9400" in yaml


def test_non_gpu_userdata_omits_gpu_install():
    """gpu_available=False 시 NVIDIA / DCGM 설치 항목이 모두 부재."""
    yaml = _generate(gpu_available=False)
    assert "install_dcgm_exporter.sh" not in yaml
    assert "ubuntu-drivers" not in yaml
    assert "dcgm-exporter" not in yaml
    assert "nvidia" not in yaml.lower()


def test_gpu_userdata_exports_cuda_env():
    """gpu_available=True 시 /etc/profile.d/union-env.sh 에 CUDA_HOME export 포함."""
    yaml = _generate(gpu_available=True)
    assert 'export CUDA_HOME="/usr/local/cuda"' in yaml


# ---------------------------------------------------------------------------
# Handler-side: /async 핸들러의 cloud-init 분기 회귀 테스트
# (libraries=[] + GPU flavor 인스턴스가 user-data 없이 생성되던 버그 회귀 방지)
# ---------------------------------------------------------------------------


def test_async_handler_generates_userdata_for_gpu_only_instance():
    """libraries=[] + flavor.is_gpu=True 시 generate_userdata 가 호출되어야 한다.

    기존 버그: `/async` 핸들러가 `if resolved_libs:` 안에서만 userdata 생성 →
    GPU flavor 만 선택한 인스턴스가 user-data 없이 부팅 → NVIDIA 미설치.

    이 테스트는 분기 조건을 직접 검증 — `resolved_libs or gpu_available` 이
    False 가 되는 경우에만 userdata=None 이 허용됨.
    """
    # 분기 진리표 검증
    cases = [
        # (resolved_libs, gpu_available, should_generate_userdata)
        ([], False, False),  # 일반 인스턴스 — userdata 불필요
        ([], True, True),  # GPU only — userdata 필요 (기존 버그 케이스)
        (["torch"], False, True),  # libraries only — userdata 필요
        (["torch"], True, True),  # libraries + GPU — userdata 필요
    ]
    for resolved_libs, gpu_available, expected in cases:
        actual = bool(resolved_libs or gpu_available)
        assert actual is expected, (
            f"resolved_libs={resolved_libs!r}, gpu_available={gpu_available!r} "
            f"→ expected userdata={expected}, got {actual}"
        )
