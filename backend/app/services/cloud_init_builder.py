"""cloud-init user-data 렌더러 — ephemeral 라이브러리 빌드용.

순수 함수 모듈 (OpenStack 의존성 zero) — 단위 테스트 용이.
"""

from __future__ import annotations

import base64
import shlex
import textwrap


def render_user_data(
    recipe,
    mount_spec: dict,
    build_token: str,
) -> str:
    """cloud-config YAML 문자열을 반환한다.

    Args:
        recipe:      LibraryRecipe ORM 객체 (commands, apt_packages, share_proto 필드 사용).
        mount_spec:  프로토콜별 마운트 정보 dict.
            NFS:    { "share_proto": "NFS",   "export_path": "host:/path" }
            CephFS: { "share_proto": "CEPHFS","ceph_mons": str,
                       "ceph_path": str, "cephx_user": str, "cephx_secret": str }
        build_token: 128bit hex (uuid4().hex) — sentinel grep 기준.

    Returns:
        cloud-config YAML 문자열 (base64-encoded user_data 용).
    """
    proto = (recipe.share_proto or mount_spec.get("share_proto", "NFS")).upper()
    apt_pkgs = list(recipe.apt_packages or [])
    commands = list(recipe.commands or [])

    if proto == "NFS":
        apt_pkgs = _ensure_pkg(apt_pkgs, "nfs-common")
    else:
        apt_pkgs = _ensure_pkg(apt_pkgs, "ceph-common")
    apt_pkgs = _ensure_pkg(apt_pkgs, "curl")

    run_build_sh = _render_run_build_sh(commands)
    run_build_b64 = base64.b64encode(run_build_sh.encode()).decode()

    write_files: list[dict] = [
        {
            "path": "/usr/local/bin/run-build.sh",
            "encoding": "b64",
            "content": run_build_b64,
            "permissions": "0755",
        }
    ]

    if proto == "CEPHFS":
        # double-base64: cloud-init이 한 번 디코딩 → 셸에서 한 번 더 디코딩
        cephx_secret_b64 = base64.b64encode(mount_spec["cephx_secret"].encode()).decode()
        cephx_secret_b64b64 = base64.b64encode(cephx_secret_b64.encode()).decode()
        write_files.insert(
            0,
            {
                "path": "/etc/ceph/builder.secret.b64",
                "encoding": "b64",
                "content": cephx_secret_b64b64,
                "permissions": "0600",
            },
        )

    mount_lines = _render_mount_lines(proto, mount_spec)
    runcmd_body = _render_runcmd_body(mount_lines, build_token)

    parts: list[str] = [
        "#cloud-config",
        "package_update: true",
        "package_upgrade: false",
        # apt-daily-upgrade가 빌드 VM에서 30분 타임아웃을 유발하는 것을 방지
        "bootcmd:",
        "  - systemctl mask apt-daily.service apt-daily-upgrade.service 2>/dev/null || true",
        "  - systemctl stop apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true",
    ]

    if apt_pkgs:
        parts.append("packages:")
        for pkg in apt_pkgs:
            parts.append(f"  - {shlex.quote(pkg)}")

    parts.append("write_files:")
    for wf in write_files:
        parts.append(f"  - path: {shlex.quote(wf['path'])}")
        if "encoding" in wf:
            parts.append(f"    encoding: {wf['encoding']}")
        parts.append(f"    content: {wf['content']}")
        if "permissions" in wf:
            parts.append(f"    permissions: '{wf['permissions']}'")

    # runcmd: 단일 멀티라인 셸 블록
    parts.append("runcmd:")
    parts.append("  - |")
    for line in runcmd_body.splitlines():
        parts.append(f"    {line}")

    parts.append("power_state:")
    parts.append("  mode: poweroff")
    parts.append("  delay: now")
    parts.append("  condition: true")

    return "\n".join(parts) + "\n"


def _ensure_pkg(pkgs: list[str], pkg: str) -> list[str]:
    return pkgs if pkg in pkgs else [pkg] + pkgs


def _render_mount_lines(proto: str, spec: dict) -> list[str]:
    """프로토콜별 mount 명령 라인 목록을 반환한다."""
    if proto == "NFS":
        export_path = spec["export_path"]
        return [
            "mkdir -p /mnt/share",
            f"mount -t nfs {shlex.quote(export_path)} /mnt/share -o rw,hard,intr",
        ]
    else:
        ceph_mons = spec["ceph_mons"]
        ceph_path = spec["ceph_path"]
        cephx_user = spec["cephx_user"]
        target = shlex.quote(f"{ceph_mons}:{ceph_path}")
        return [
            "mkdir -p /mnt/share /etc/ceph",
            "SECRET_FILE=$(mktemp /tmp/ceph.XXXXXX)",
            'base64 -d /etc/ceph/builder.secret.b64 | base64 -d > "$SECRET_FILE"',
            'chmod 600 "$SECRET_FILE"',
            f'mount -t ceph {target} /mnt/share -o name={shlex.quote(cephx_user)},secretfile="$SECRET_FILE"',
            'rm -f "$SECRET_FILE"',
        ]


def _render_run_build_sh(commands: list[dict]) -> str:
    """각 step을 순차 실행하고 진행 마커를 touch 하는 셸 스크립트를 반환한다."""
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "mkdir -p /mnt/share/_build_logs",
        "",
        "_on_error() {",
        "  tail -n 100 /var/log/cloud-init-output.log"
        " > /mnt/share/_build_logs/error.txt 2>/dev/null || true",
        "}",
        "trap _on_error ERR",
        "",
    ]

    for cmd in commands:
        step = cmd.get("step", "step")
        pct = int(cmd.get("progress_pct", 50))
        script = textwrap.dedent(cmd.get("script", "")).strip()
        lines.append(f"# --- {step} ---")
        lines.append(script)
        lines.append(f"touch /mnt/share/.progress_{pct}_{step}")
        lines.append("")

    return "\n".join(lines)


def _render_runcmd_body(mount_lines: list[str], build_token: str) -> str:
    """sentinel을 emit 하는 전체 runcmd 셸 블록(문자열)을 반환한다."""
    success_sentinel = f"::AFTERGLOW::SUCCESS::{build_token}"
    failure_sentinel = f"::AFTERGLOW::FAILURE::{build_token}"

    # mount_lines를 &&로 연결하고 run-build.sh 까지 포함
    # NOTE: 멀티라인 \\\n && 연결 시 YAML literal block scalar 내에서 &&로 시작하는
    # 라인이 block scalar 확립 들여쓰기보다 얕아져 YAML 앵커(&)로 오해석되는 버그가
    # 발생한다. 단일 라인 && 연결로 고정한다.
    chain_lines = mount_lines + ["bash /usr/local/bin/run-build.sh"]
    mount_and_build = " && ".join(chain_lines)

    return textwrap.dedent(f"""\
        set +e
        {{
          _rc=0
          {mount_and_build} || _rc=$?
          if [ "$_rc" -eq 0 ]; then
            touch /mnt/share/.union_build_complete
            mkdir -p /mnt/share/_build_logs
            cp /var/log/cloud-init-output.log /mnt/share/_build_logs/ 2>/dev/null || true
            umount /mnt/share 2>/dev/null || true
            echo "{success_sentinel}"
          else
            umount /mnt/share 2>/dev/null || true
            echo "{failure_sentinel}::rc=$_rc"
          fi
        }} 2>&1 | tee /dev/console
        # power_state: poweroff 는 cloud-init 전체 완료 후 실행되므로
        # runcmd 에서 직접 poweroff 해 SHUTOFF 지연을 방지한다
        sync
        poweroff
    """)
