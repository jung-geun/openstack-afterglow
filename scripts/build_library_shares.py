#!/usr/bin/env python3
"""
사전 빌드 라이브러리 share 관리 CLI 스크립트.

사용법:
  python build_library_shares.py build --library python311
  python build_library_shares.py list
  python build_library_shares.py delete --share-id <id>

동작:
  1. Manila share 생성 (상태: building)
  2. 임시 VM 생성 (부트 볼륨 + 생성된 share 마운트)
  3. VM 내부에서 pip install 실행
  4. VM 삭제, share 상태를 available 로 업데이트
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

import openstack


# ---------------------------------------------------------------------------
# 라이브러리 설정
# ---------------------------------------------------------------------------
LIBRARY_CATALOG = {
    "python311": {
        "name": "Python 3.11",
        "version": "3.11",
        "packages": ["python3.11", "python3.11-pip", "python3.11-venv"],
        "size_gb": 5,
        "install_script": """
#!/bin/bash
apt-get update -qq
apt-get install -y python3.11 python3.11-pip python3.11-venv
mkdir -p /share/usr_local /share/opt
cp -a /usr/local/. /share/usr_local/
""",
    },
    "torch": {
        "name": "PyTorch 2.4",
        "version": "2.4.0",
        "packages": ["torch==2.4.0", "torchvision==0.19.0", "torchaudio==2.4.0"],
        "size_gb": 15,
        "install_script": """
#!/bin/bash
pip3 install --no-cache-dir torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0
mkdir -p /share/usr_local
cp -a /usr/local/. /share/usr_local/
""",
    },
    "vllm": {
        "name": "vLLM 0.6",
        "version": "0.6.0",
        "packages": ["vllm==0.6.0"],
        "size_gb": 8,
        "install_script": """
#!/bin/bash
pip3 install --no-cache-dir vllm==0.6.0
mkdir -p /share/usr_local
cp -a /usr/local/. /share/usr_local/
""",
    },
    "jupyter": {
        "name": "Jupyter Lab 4",
        "version": "4.2.0",
        "packages": ["jupyterlab==4.2.0", "ipykernel"],
        "size_gb": 3,
        "install_script": """
#!/bin/bash
pip3 install --no-cache-dir jupyterlab==4.2.0 ipykernel
mkdir -p /share/usr_local
cp -a /usr/local/. /share/usr_local/
""",
    },
}


def get_conn() -> openstack.connection.Connection:
    return openstack.connect(
        auth_url=os.environ["OS_AUTH_URL"],
        username=os.environ["OS_USERNAME"],
        password=os.environ["OS_PASSWORD"],
        project_name=os.environ.get("OS_PROJECT_NAME", "admin"),
        user_domain_name=os.environ.get("OS_USER_DOMAIN_NAME", "Default"),
        project_domain_name=os.environ.get("OS_PROJECT_DOMAIN_NAME", "Default"),
        region_name=os.environ.get("OS_REGION_NAME", "RegionOne"),
    )


def cmd_list(args, conn):
    # Manila REST 호출
    import httpx
    catalog = conn.config.get_service_catalog()
    manila_ep = None
    for svc in catalog:
        if svc.get("type") in ("share", "sharev2"):
            for ep in svc.get("endpoints", []):
                if ep.get("interface") == "public":
                    manila_ep = ep["url"]
                    break
    if not manila_ep:
        print("Manila 엔드포인트를 찾을 수 없습니다", file=sys.stderr)
        return

    project_id = conn.current_project_id
    url = f"{manila_ep.rstrip('/')}/{project_id}/shares/detail"
    headers = {
        "X-Auth-Token": conn.auth_token,
        "X-OpenStack-Manila-API-Version": "2.65",
    }
    r = httpx.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    shares = r.json()["shares"]
    union_shares = [s for s in shares if s.get("metadata", {}).get("union_type")]

    if not union_shares:
        print("Union share 없음")
        return

    print(f"{'ID':<36}  {'이름':<30}  {'상태':<12}  {'라이브러리'}")
    print("-" * 90)
    for s in union_shares:
        meta = s.get("metadata", {})
        print(f"{s['id']}  {s['name']:<30}  {s['status']:<12}  {meta.get('union_library', '-')}")


def cmd_build(args, conn):
    lib_id = args.library
    if lib_id not in LIBRARY_CATALOG:
        print(f"알 수 없는 라이브러리: {lib_id}", file=sys.stderr)
        sys.exit(1)

    lib = LIBRARY_CATALOG[lib_id]
    share_network_id = os.environ.get("OS_MANILA_SHARE_NETWORK_ID", "")
    share_type = os.environ.get("OS_MANILA_SHARE_TYPE", "cephfstype")

    print(f"[1/4] Manila share 생성: union-prebuilt-{lib_id}")
    # Manila REST API 직접 호출
    import httpx
    catalog = conn.config.get_service_catalog()
    manila_ep = None
    for svc in catalog:
        if svc.get("type") in ("share", "sharev2"):
            for ep in svc.get("endpoints", []):
                if ep.get("interface") == "public":
                    manila_ep = ep["url"]
                    break

    project_id = conn.current_project_id
    headers = {
        "X-Auth-Token": conn.auth_token,
        "X-OpenStack-Manila-API-Version": "2.65",
        "Content-Type": "application/json",
    }

    body = {
        "share": {
            "name": f"union-prebuilt-{lib_id}",
            "share_proto": "CEPHFS",
            "size": lib["size_gb"],
            "share_type": share_type,
            "share_network_id": share_network_id,
            "metadata": {
                "union_type": "prebuilt",
                "union_library": lib_id,
                "union_version": lib["version"],
                "union_status": "building",
            },
        }
    }
    r = httpx.post(f"{manila_ep}/{project_id}/shares", json=body, headers=headers, timeout=30)
    r.raise_for_status()
    share = r.json()["share"]
    share_id = share["id"]
    print(f"  Share ID: {share_id}")

    print("[2/4] share available 대기 중...")
    for _ in range(60):
        time.sleep(5)
        r = httpx.get(f"{manila_ep}/{project_id}/shares/{share_id}", headers=headers, timeout=30)
        if r.json()["share"]["status"] == "available":
            break
    else:
        print("Share 가용 상태 대기 시간 초과", file=sys.stderr)
        sys.exit(1)

    print("[3/4] (수동 단계) 라이브러리를 share에 설치하세요:")
    print(f"  1. 임시 VM을 생성하고 이 share를 마운트하세요 (share ID: {share_id})")
    print(f"  2. 다음 스크립트를 실행하세요:")
    print("-" * 40)
    print(lib["install_script"])
    print("-" * 40)
    input("설치 완료 후 Enter를 눌러 share 메타데이터를 업데이트하세요...")

    print("[4/4] Share 메타데이터 업데이트...")
    meta_body = {
        "set_metadata": {
            "union_status": "ready",
            "union_built_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    r = httpx.post(
        f"{manila_ep}/{project_id}/shares/{share_id}/metadata",
        json=meta_body, headers=headers, timeout=30
    )
    r.raise_for_status()
    print(f"완료! Share {share_id} 사용 준비됨")


def main():
    parser = argparse.ArgumentParser(description="Union 라이브러리 Share 관리")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="Share 목록 조회")

    build_p = sub.add_parser("build", help="사전 빌드 share 생성")
    build_p.add_argument("--library", required=True, choices=list(LIBRARY_CATALOG.keys()))

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    conn = get_conn()
    if args.cmd == "list":
        cmd_list(args, conn)
    elif args.cmd == "build":
        cmd_build(args, conn)


if __name__ == "__main__":
    main()
