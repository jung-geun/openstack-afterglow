"""recipe_blocks / library_recipes 빌트인 레시피 단위 테스트.

빌딩 블록의 스크립트 생성·입력 검증(명령 주입 방어)·레시피 조합 무결성을 검증한다.
"""

from __future__ import annotations

import pytest

from app.services import recipe_blocks as rb
from app.services.cloud_init_builder import render_user_data
from app.services.library_recipes import (
    _BUILTIN_RECIPE_DEFS,
    _RECIPE_ALIASES,
    _builtin_recipe_ns,
)

# ---------------------------------------------------------------------------
# uv 블록
# ---------------------------------------------------------------------------


def test_uv_bootstrap_idempotent_guard():
    out = rb.uv_bootstrap()
    assert "command -v uv" in out  # 멱등 가드
    assert "astral.sh/uv/install.sh" in out
    assert "UV_INSTALL_DIR=/usr/local/bin" in out


def test_python_layer_targets_layer_root():
    out = rb.python_layer("3.11")
    assert "uv python install cpython-3.11" in out
    assert "/mnt/share/usr/local" in out
    assert "/mnt/share/usr/local/lib/python3.11/site-packages" in out
    assert rb._PYCOPY_PATH in out  # 병렬 복사기 사용


def test_python_layer_rejects_bad_version():
    with pytest.raises(ValueError):
        rb.python_layer("3.11; rm -rf /")
    with pytest.raises(ValueError):
        rb.python_layer("$(reboot)")


def test_pip_layer_quotes_and_targets_site_packages():
    out = rb.pip_layer(["torch==2.4.0", "uvicorn[standard]"], python_version="3.11")
    assert "--target /mnt/share/usr/local/lib/python3.11/site-packages" in out
    assert "torch==2.4.0" in out
    # extras 포함 스펙은 쿼팅되어 들어간다
    assert "'uvicorn[standard]'" in out
    # apt python 의존 없음 — uv 관리 CPython 사용
    assert "uv python install cpython-3.11" in out
    assert "apt-get" not in out


def test_pip_layer_rejects_injection():
    with pytest.raises(ValueError):
        rb.pip_layer(["torch; rm -rf /"])
    with pytest.raises(ValueError):
        rb.pip_layer(["torch && reboot"])
    with pytest.raises(ValueError):
        rb.pip_layer([])


# ---------------------------------------------------------------------------
# apt 캡처 블록
# ---------------------------------------------------------------------------


def test_apt_capture_layer_structure():
    out = rb.apt_capture_layer(["apache2", "php"])
    # 루프백 ext4 upper (NFS upperdir 불가 + lowerdir 하위 overlap 회피)
    assert "truncate -s 8G" in out
    assert "mkfs.ext4" in out
    assert "mount -o loop" in out
    # overlay 캡처 + chroot 설치
    assert "lowerdir=/,upperdir=$CAP/upper,workdir=$CAP/work" in out
    assert "chroot" in out
    assert "apt-get install -y --no-install-recommends apache2 php" in out
    assert "DEBIAN_FRONTEND=noninteractive" in out
    # dpkg fsync 생략 (설치 가속) — 설치 후 레이어에 남지 않도록 제거
    assert "force-unsafe-io" in out
    assert "rm -f /etc/dpkg/dpkg.cfg.d/aft-unsafe-io" in out
    # 휘발성 경로 정리 후 레이어로 복사
    assert "$CAP/upper/var/cache" in out
    assert "$CAP/upper/var/lib/apt/lists" in out
    assert f'{rb._PYCOPY_PATH} "$CAP/upper" /mnt/share' in out


def test_apt_capture_layer_debconf_selections():
    out = rb.apt_capture_layer(
        ["phpmyadmin"],
        debconf_selections=["phpmyadmin phpmyadmin/dbconfig-install boolean false"],
    )
    assert "debconf-set-selections" in out
    assert "phpmyadmin/dbconfig-install boolean false" in out


def test_apt_capture_layer_rejects_injection():
    with pytest.raises(ValueError):
        rb.apt_capture_layer(["apache2; rm -rf /"])
    with pytest.raises(ValueError):
        rb.apt_capture_layer(["Apache2"])  # 대문자 — Debian 패키지명 정책 위반
    with pytest.raises(ValueError):
        rb.apt_capture_layer(["php\nmalicious"])
    with pytest.raises(ValueError):
        rb.apt_capture_layer([])
    with pytest.raises(ValueError):
        rb.apt_capture_layer(["apache2"], capture_size_gb=999)
    with pytest.raises(ValueError):
        rb.apt_capture_layer(
            ["apache2"],
            debconf_selections=["pkg key boolean false\necho pwned"],
        )


def test_pycopy_skips_special_files():
    # whiteout(char device) 등 특수 파일 스킵 로직이 포함되어야 한다
    assert "S_ISREG" in rb._PYCOPY_SOURCE
    # 소유자 보존 (no_root_squash 전제 best-effort)
    assert "chown" in rb._PYCOPY_SOURCE


# ---------------------------------------------------------------------------
# 빌트인 레시피 정의 무결성
# ---------------------------------------------------------------------------


def test_builtin_defs_have_required_fields():
    for lib_id, entry in _BUILTIN_RECIPE_DEFS.items():
        assert isinstance(entry["version"], int) and entry["version"] >= 1, lib_id
        assert entry["share_size_gb"] >= 1, lib_id
        assert entry["share_proto"] in ("NFS", "CEPHFS"), lib_id
        assert entry["commands"], lib_id
        for cmd in entry["commands"]:
            assert cmd["step"], lib_id
            assert isinstance(cmd["script"], str) and cmd["script"].strip(), lib_id


def test_python_recipes_do_not_depend_on_apt_python():
    """torch/vllm/jupyter v2: Ubuntu 24.04에 없는 apt python3.11 의존 제거 확인."""
    for lib_id in ("torch", "vllm", "jupyter"):
        entry = _BUILTIN_RECIPE_DEFS[lib_id]
        assert "python3.11" not in entry["apt_packages"], lib_id
        scripts = "\n".join(c["script"] for c in entry["commands"])
        assert "uv python install" in scripts, lib_id


def test_apache_php_recipe_uses_apt_capture():
    entry = _BUILTIN_RECIPE_DEFS["apache-php"]
    scripts = "\n".join(c["script"] for c in entry["commands"])
    assert "chroot" in scripts
    assert "phpmyadmin" in scripts
    assert "apache2" in scripts


def test_builtin_ns_alias_pytorch():
    ns = _builtin_recipe_ns("pytorch")
    assert ns is not None
    assert ns.library_id == "pytorch"
    assert ns.commands == _BUILTIN_RECIPE_DEFS["torch"]["commands"]
    assert _RECIPE_ALIASES["pytorch"] == "torch"


def test_builtin_ns_unknown_returns_none():
    assert _builtin_recipe_ns("no-such-lib") is None


# ---------------------------------------------------------------------------
# cloud-init 렌더 통합 — 모든 빌트인 레시피가 user_data로 렌더 가능해야 한다
# ---------------------------------------------------------------------------


def test_render_user_data_for_all_builtin_recipes():
    for lib_id in list(_BUILTIN_RECIPE_DEFS) + list(_RECIPE_ALIASES):
        ns = _builtin_recipe_ns(lib_id)
        out = render_user_data(ns, {"share_proto": "NFS", "export_path": "host:/path"}, "tok123")
        assert out.startswith("#cloud-config"), lib_id
        assert "::AFTERGLOW::SUCCESS::tok123" in out, lib_id
        assert "::AFTERGLOW::FAILURE::tok123" in out, lib_id
        # sentinel 조기 감지 윈도우 (poweroff 전 60초)
        assert "sleep 60" in out, lib_id
        assert "mode: poweroff" in out, lib_id
