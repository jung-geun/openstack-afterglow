"""OpenTofu subprocess 래퍼 — ephemeral 인프라 선언적 관리."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

_logger = logging.getLogger(__name__)

# backend/tofu/ 디렉터리 (모듈 소스)
_TOFU_MODULES_DIR = Path(__file__).parent.parent.parent / "tofu"

# tofu 실행 파일 이름 (PATH에서 찾음)
_TOFU_BIN = "tofu"


class TofuNotFound(RuntimeError):
    """tofu CLI 를 찾을 수 없을 때 발생."""


class TofuApplyError(RuntimeError):
    """tofu apply 실패 시 발생."""


class TofuDestroyError(RuntimeError):
    """tofu destroy 실패 시 발생."""


def _tofu_bin() -> str:
    """tofu binary 경로를 반환한다. 없으면 TofuNotFound."""
    path = shutil.which(_TOFU_BIN)
    if not path:
        raise TofuNotFound(
            f"'{_TOFU_BIN}' 를 PATH 에서 찾을 수 없습니다. Dockerfile 에 OpenTofu CLI 가 설치됐는지 확인하세요."
        )
    return path


def _env_from_conn(conn: openstack.connection.Connection) -> dict[str, str]:
    """openstacksdk Connection 에서 OpenStack provider 환경변수를 구성한다."""
    auth = conn.auth or {}
    env = os.environ.copy()
    mapping = {
        "OS_AUTH_URL": auth.get("auth_url", ""),
        "OS_USERNAME": auth.get("username", ""),
        "OS_PASSWORD": auth.get("password", ""),
        "OS_PROJECT_ID": auth.get("project_id", ""),
        "OS_PROJECT_NAME": auth.get("project_name", ""),
        "OS_USER_DOMAIN_NAME": auth.get("user_domain_name", "Default"),
        "OS_PROJECT_DOMAIN_NAME": auth.get("project_domain_name", "Default"),
        "OS_REGION_NAME": getattr(getattr(conn, "config", None), "region_name", "") or "",
        # tofu 비대화형 실행
        "TF_IN_AUTOMATION": "1",
        "TF_CLI_ARGS_apply": "-auto-approve",
        "TF_CLI_ARGS_destroy": "-auto-approve",
    }
    # 빈 값은 기존 환경변수에서도 제거해 openstack provider 인증 우선순위를 보장
    for k, v in mapping.items():
        if v:
            env[k] = str(v)
        elif k in env:
            del env[k]

    # OS_INSECURE: openstack provider는 소문자 bool 문자열("true"/"false")만 허용
    if "OS_INSECURE" in env:
        val = env["OS_INSECURE"].strip().lower()
        env["OS_INSECURE"] = "true" if val in ("1", "true", "yes") else "false"

    return env


def _var_file_args(workdir: Path) -> list[str]:
    """workdir 의 *.tfvars.json 파일을 -var-file 인자 목록으로 반환한다."""
    return [f"-var-file={vf}" for vf in sorted(workdir.glob("*.tfvars.json"))]


def _run_tofu(args: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    tofu = _tofu_bin()
    cmd = [tofu, *args]
    _logger.debug("[tofu] %s (cwd=%s)", " ".join(cmd), cwd)
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _logger.error("[tofu] 실패\nstdout:\n%s\nstderr:\n%s", result.stdout, result.stderr)
    return result


async def apply(
    module: str,
    variables: dict,
    conn: openstack.connection.Connection,
) -> tuple[Path, dict]:
    """지정 모듈을 격리된 workdir 에 복사하고 tofu apply 를 실행한다.

    Returns:
        (workdir, outputs_dict) — workdir 은 destroy() 에 전달해야 한다.
    """
    module_src = _TOFU_MODULES_DIR / module
    if not module_src.is_dir():
        raise FileNotFoundError(f"tofu 모듈을 찾을 수 없습니다: {module_src}")

    workdir = Path(tempfile.mkdtemp(prefix="afterglow-tofu-"))
    _logger.info("[tofu] workdir 생성: %s", workdir)

    try:
        # 모듈 파일 복사
        for src in module_src.glob("*.tf"):
            shutil.copy2(src, workdir / src.name)

        # 변수 파일 생성
        tfvars_path = workdir / "smoke.tfvars.json"
        tfvars_path.write_text(json.dumps(variables, ensure_ascii=False))

        env = await asyncio.to_thread(_env_from_conn, conn)

        # init
        init = await asyncio.to_thread(_run_tofu, ["init", "-input=false"], workdir, env)
        if init.returncode != 0:
            raise TofuApplyError(f"tofu init 실패: {init.stderr}")

        # apply
        apply_result = await asyncio.to_thread(
            _run_tofu,
            ["apply", "-input=false", f"-var-file={tfvars_path}"],
            workdir,
            env,
        )
        if apply_result.returncode != 0:
            raise TofuApplyError(f"tofu apply 실패: {apply_result.stderr}")

        # output
        out_result = await asyncio.to_thread(_run_tofu, ["output", "-json"], workdir, env)
        if out_result.returncode != 0:
            raise TofuApplyError(f"tofu output 실패: {out_result.stderr}")

        raw = json.loads(out_result.stdout)
        outputs = {k: v["value"] for k, v in raw.items()}
        _logger.info("[tofu] apply 완료, outputs: %s", list(outputs.keys()))
        return workdir, outputs

    except Exception:
        # apply 실패 시 workdir 정리 시도 (best-effort)
        try:
            env = await asyncio.to_thread(_env_from_conn, conn)
            destroy_args = ["destroy", "-input=false"] + _var_file_args(workdir)
            await asyncio.to_thread(_run_tofu, destroy_args, workdir, env)
        except Exception:
            pass
        shutil.rmtree(workdir, ignore_errors=True)
        raise


async def destroy(workdir: Path, conn: openstack.connection.Connection) -> None:
    """workdir 의 state 기반으로 tofu destroy 를 실행하고 디렉터리를 정리한다."""
    if not workdir.exists():
        return
    try:
        env = await asyncio.to_thread(_env_from_conn, conn)
        destroy_args = ["destroy", "-input=false"] + _var_file_args(workdir)
        result = await asyncio.to_thread(_run_tofu, destroy_args, workdir, env)
        if result.returncode != 0:
            _logger.error("[tofu] destroy 실패 (state 잔존 가능): %s", result.stderr)
            raise TofuDestroyError(f"tofu destroy 실패: {result.stderr}")
        _logger.info("[tofu] destroy 완료: %s", workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
