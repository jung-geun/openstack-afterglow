# Union: Ubuntu OverlayFS 레이어 시스템

Ubuntu 이미지 기반으로 `uv` 패키지 관리자를 사용하여 라이브러리 레이어를 빌드하고, OverlayFS를 통해 조합하여 통합 환경을 제공하는 시스템.

---

## 목차

1. [아키텍처 개요](#아키텍처-개요)
2. [PostgreSQL DB 스키마](#postgresql-db-스키마)
3. [디렉토리 구조](#디렉토리-구조)
4. [레이어 빌드 프로세스](#레이어-빌드-프로세스)
5. [Cloud-init 템플릿](#cloud-init-템플릿)
6. [웹서버 API 흐름](#웹서버-api-흐름)
7. [쉘 스크립트 초안](#쉘-스크립트-초안)

---

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PostgreSQL Database                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │ ubuntu_ver  │  │ python_ver  │  │ library_layers / deps / ... │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (웹서버)                         │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │
│  │ 레이어 분석     │  │ Cloud-init     │  │ 의존성 토폴로지 정렬   │ │
│  │ DB 조회/기록   │  │ 템플릿 생성    │  │ lowerdir 순서 결정     │ │
│  └────────────────┘  └────────────────┘  └────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Manila Share (CephFS)                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ python-3.11 │  │ torch-2.4   │  │ vllm-0.6    │  │ jupyter-4.2 │ │
│  │ (read-only) │  │ (read-only) │  │ (read-only) │  │ (read-only) │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Manila access rule (CephX)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Ubuntu Instance                               │
│  /opt/layers/          ← Manila 마운트 (read-only)                   │
│  ├── python-3.11/                                             │
│  ├── torch-2.4/                                                 │
│  ├── vllm-0.6/                                                  │
│  └── jupyter-4.2/                                               │
│                                                                    │
│  /opt/workspace/merged/  ← OverlayFS merged (사용자 환경)           │
│  /opt/workspace/upper/   ← writable 레이어 (Cinder 볼륨)            │
│  /opt/workspace/work/     ← OverlayFS workdir                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## PostgreSQL DB 스키마

### 테이블 구조

```sql
-- Ubuntu 버전 정보
CREATE TABLE ubuntu_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL UNIQUE,        -- 예: '22.04', '24.04'
    codename VARCHAR(50),                        -- 예: 'jammy', 'noble'
    glibc_version VARCHAR(20),                  -- glibc 버전 (호환성 확인용)
    python_versions JSONB,                       -- 지원하는 Python 버전 목록
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Python 버전 정보
CREATE TABLE python_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL UNIQUE,         -- 예: '3.10', '3.11', '3.12'
    major INT NOT NULL,
    minor INT NOT NULL,
    patch INT DEFAULT 0,
    eol_date DATE,                              -- End of Life 날짜
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 라이브러리 레이어 메타데이터
CREATE TABLE library_layers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,                 -- 레이어 이름 (예: 'torch-2.4-cu121')
    library_type VARCHAR(50) NOT NULL,           -- 'python', 'torch', 'vllm', 'jupyter'
    version VARCHAR(50) NOT NULL,                -- 버전 (예: '2.4.0')
    variant VARCHAR(50),                         -- 변형 (예: 'cu121', 'cpu')
    
    -- 호환성 정보
    ubuntu_versions JSONB,                       -- 지원 Ubuntu 버전 목록
    python_versions JSONB,                       -- 지원 Python 버전 목록
    
    -- 의존성
    depends_on JSONB,                            -- 의존하는 다른 레이어 IDs
    conflicts_with JSONB,                        -- 충돌하는 레이어 IDs
    
    -- Manila share 정보
    manila_share_id UUID,                        -- Manila share UUID
    manila_export_path TEXT,                     -- CephFS export 경로
    size_gb INT NOT NULL,                        -- 레이어 크기
    
    -- 빌드 정보
    build_status VARCHAR(20) DEFAULT 'pending',  -- pending, building, ready, failed
    built_at TIMESTAMP,
    build_log TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(library_type, version, variant)
);

-- 레이어 의존성 관계
CREATE TABLE layer_dependencies (
    id SERIAL PRIMARY KEY,
    parent_layer_id INT REFERENCES library_layers(id),
    child_layer_id INT REFERENCES library_layers(id),
    dependency_type VARCHAR(20) DEFAULT 'required', -- required, optional, recommended
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(parent_layer_id, child_layer_id)
);

-- OS 간 호환성 매트릭스
CREATE TABLE os_compatibility (
    id SERIAL PRIMARY KEY,
    source_ubuntu_id INT REFERENCES ubuntu_versions(id),
    target_ubuntu_id INT REFERENCES ubuntu_versions(id),
    is_compatible BOOLEAN DEFAULT false,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_ubuntu_id, target_ubuntu_id)
);

-- 사용자 레이어 조합 기록 (마운트 이력)
CREATE TABLE mount_configurations (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,               -- Keystone user ID
    instance_id UUID,                            -- Nova instance ID
    
    -- 선택한 레이어
    ubuntu_version_id INT REFERENCES ubuntu_versions(id),
    python_version_id INT REFERENCES python_versions(id),
    layer_ids JSONB NOT NULL,                    -- 순서대로 정렬된 레이어 ID 목록
    
    -- 마운트 정보
    mount_path VARCHAR(255) DEFAULT '/opt/workspace/merged',
    upper_device VARCHAR(100),                   -- Cinder 볼륨 장치 경로
    
    -- cloud-init 메타데이터
    cloudinit_userdata TEXT,                     -- 생성된 cloud-init YAML
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_library_layers_type ON library_layers(library_type);
CREATE INDEX idx_library_layers_status ON library_layers(build_status);
CREATE INDEX idx_mount_configs_user ON mount_configurations(user_id);
CREATE INDEX idx_mount_configs_instance ON mount_configurations(instance_id);
```

### 샘플 데이터

```sql
-- Ubuntu 버전
INSERT INTO ubuntu_versions (version, codename, glibc_version, python_versions) VALUES
('22.04', 'jammy', '2.35', '["3.10", "3.11", "3.12"]'),
('24.04', 'noble', '2.39', '["3.12", "3.13"]');

-- Python 버전
INSERT INTO python_versions (version, major, minor, patch, eol_date) VALUES
('3.10', 3, 10, 0, '2026-10-31'),
('3.11', 3, 11, 0, '2027-10-31'),
('3.12', 3, 12, 0, '2028-10-31');

-- 라이브러리 레이어
INSERT INTO library_layers (name, library_type, version, variant, ubuntu_versions, python_versions, depends_on, size_gb) VALUES
('python-3.11', 'python', '3.11.0', NULL, '["22.04", "24.04"]', '["3.11"]', '[]', 1),
('torch-2.4-cu121', 'torch', '2.4.0', 'cu121', '["22.04", "24.04"]', '["3.10", "3.11", "3.12"]', '["python-3.11"]', 15),
('vllm-0.6', 'vllm', '0.6.0', 'cu121', '["22.04", "24.04"]', '["3.10", "3.11", "3.12"]', '["torch-2.4-cu121"]', 8),
('jupyter-4.2', 'jupyter', '4.2.0', NULL, '["22.04", "24.04"]', '["3.10", "3.11", "3.12"]', '["python-3.11"]', 2);

-- OS 호환성 (Ubuntu 22.04 레이어를 24.04에서 사용 가능)
INSERT INTO os_compatibility (source_ubuntu_id, target_ubuntu_id, is_compatible, notes) VALUES
(1, 2, true, 'glibc 호환됨: 22.04 레이어를 24.04에서 사용 가능'),
(2, 1, false, 'glibc 버전 차이: 24.04 레이어를 22.04에서 사용 불가');
```

---

## 디렉토리 구조

### Ubuntu 인스턴스 내부

```
/opt/
├── layers/                           # Manila 마운트 지점 (read-only)
│   ├── python-3.10/                  # Python 3.10 레이어
│   │   └── usr/
│   │       └── local/
│   │           ├── bin/python3.10
│   │           └── lib/python3.10/
│   ├── python-3.11/                  # Python 3.11 레이어
│   │   └── usr/local/
│   ├── python-3.12/
│   ├── torch-2.4-cu121/             # PyTorch 레이어 (CUDA 12.1)
│   │   └── usr/local/lib/python3.11/site-packages/torch/
│   ├── vllm-0.6/                    # vLLM 레이어
│   │   └── usr/local/lib/python3.11/site-packages/vllm/
│   └── jupyter-4.2/                 # Jupyter 레이어
│       └── usr/local/bin/jupyter
│
├── workspace/                        # 작업 공간
│   ├── merged/                       # OverlayFS merged 디렉토리
│   │   ├── bin/                      # 합쳐진 실행 파일
│   │   └── lib/                      # 합쳐진 라이브러리
│   ├── upper/                        # writable 레이어 (Cinder 볼륨)
│   │   ├── usr/local/
│   │   └── opt/
│   └── work/                         # OverlayFS workdir
│
└── union/                            # 시스템 관리
    ├── config.yaml                   # 설정 파일
    ├── db/                           # 로컬 DB 캐시
    │   └── layers_cache.json
    └── scripts/                      # 관리 스크립트
        ├── layer-sync.sh
        └── health-check.sh
```

### Manila Share 구조

```
/cephfs/shares/                       # CephFS 루트
├── union-layers/                     # Union 전용 디렉토리
│   ├── ubuntu-22.04/
│   │   ├── python-3.10/
│   │   ├── python-3.11/
│   │   ├── torch-2.4-cu121/
│   │   ├── vllm-0.6/
│   │   └── jupyter-4.2/
│   ├── ubuntu-24.04/
│   │   └── ...
│   └── universal/                    # OS 무관 레이어
│       └── ...
└── union-instances/                  # 인스턴스별 writable 영역
    ├── instance-a1b2c3d4/
    └── instance-e5f6g7h8/
```

---

## 레이어 빌드 프로세스

### uv를 사용한 레이어 빌드

```bash
#!/bin/bash
# build-layer.sh - uv로 레이어 빌드
# 사용법: build-layer.sh <library_type> <version> [options]

set -euo pipefail

LIBRARY_TYPE=$1
VERSION=$2
PYTHON_VERSION=${3:-3.11}
UBUNTU_VERSION=${4:-22.04}
VARIANT=${5:-cu121}

LAYER_NAME="${LIBRARY_TYPE}-${VERSION}-${VARIANT}"
BUILD_DIR="/tmp/layer-build/${LAYER_NAME}"
LAYER_DIR="/opt/layers/${LAYER_NAME}"

echo "[1/6] 빌드 환경 준비..."
mkdir -p "${BUILD_DIR}/root"
mkdir -p "${LAYER_DIR}/usr/local"

echo "[2/6] uv 설치..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "[3/6] 가상환경 생성..."
uv venv --python "${PYTHON_VERSION}" "${BUILD_DIR}/venv"
source "${BUILD_DIR}/venv/bin/activate"

echo "[4/6] 패키지 설치 (uv 사용)..."

case "${LIBRARY_TYPE}" in
    "python")
        # Python 자체는 시스템 패키지지만, pip/setuptools 등 설치
        uv pip install --no-cache-dir pip setuptools wheel
        ;;
    "torch")
        uv pip install --no-cache-dir \
            "torch==${VERSION}" \
            "torchvision==${VERSION}" \
            "torchaudio==${VERSION%.*}" \
            --index-url "https://download.pytorch.org/whl/${VARIANT}"
        ;;
    "vllm")
        uv pip install --no-cache-dir "vllm==${VERSION}"
        ;;
    "jupyter")
        uv pip install --no-cache-dir "jupyterlab==${VERSION}" ipykernel
        ;;
    *)
        echo "알 수 없는 라이브러리 타입: ${LIBRARY_TYPE}"
        exit 1
        ;;
esac

echo "[5/6] 레이어로 복사..."
cp -a "${BUILD_DIR}/venv/lib/python${PYTHON_VERSION}/site-packages/." \
    "${LAYER_DIR}/usr/local/lib/python${PYTHON_VERSION}/site-packages/"
cp -a "${BUILD_DIR}/venv/bin/." "${LAYER_DIR}/usr/local/bin/"

echo "[6/6] 정리..."
rm -rf "${BUILD_DIR}"

echo "완료: ${LAYER_DIR}"
```

### 레이어 DB 등록 (Python)

```python
# backend/app/services/layer_builder.py

import subprocess
import json
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from backend.app.models.layer import LibraryLayer, LayerDependency

LAYER_BUILD_SCRIPT = Path("/opt/union/scripts/build-layer.sh")

async def build_layer(
    db: Session,
    library_type: str,
    version: str,
    python_version: str = "3.11",
    ubuntu_versions: list[str] = None,
    variant: str = None,
    depends_on: list[str] = None,
) -> LibraryLayer:
    """레이어 빌드 및 DB 등록"""
    
    # 1. DB에 pending 상태로 생성
    layer = LibraryLayer(
        name=f"{library_type}-{version}-{variant}" if variant else f"{library_type}-{version}",
        library_type=library_type,
        version=version,
        variant=variant,
        ubuntu_versions=ubuntu_versions or ["22.04", "24.04"],
        python_versions=[python_version],
        depends_on=depends_on or [],
        size_gb=0,
        build_status="building",
    )
    db.add(layer)
    db.commit()
    
    try:
        # 2. 빌드 스크립트 실행
        result = subprocess.run(
            [
                str(LAYER_BUILD_SCRIPT),
                library_type,
                version,
                python_version,
                ubuntu_versions[0] if ubuntu_versions else "22.04",
                variant or "",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        
        # 3. 빌드 결과 크기 계산
        layer_path = Path(f"/opt/layers/{layer.name}")
        size_bytes = sum(f.stat().st_size for f in layer_path.rglob("*") if f.is_file())
        layer.size_gb = size_bytes // (1024**3) + 1
        
        # 4. Manila share 생성 및 업로드
        manila_share_id = await upload_to_manila(layer_path, layer.name)
        layer.manila_share_id = manila_share_id
        
        layer.build_status = "ready"
        layer.built_at = datetime.utcnow()
        
    except subprocess.CalledProcessError as e:
        layer.build_status = "failed"
        layer.build_log = e.stderr
        raise
    
    db.commit()
    return layer
```

---

## Cloud-init 템플릿

### 기본 cloud-init 구조

```yaml
# cloud-init/base.yaml.j2
#cloud-config

write_files:
  # CephX 키링 파일들 (각 레이어별)
  {% for share in shares %}
  - path: /etc/ceph/ceph.client.{{ share.cephx_id }}.keyring
    content: |
      [client.{{ share.cephx_id }}]
          key = {{ share.cephx_key }}
    permissions: '0600'
    owner: root:root
  {% endfor %}
  
  # OverlayFS 설정 스크립트
  - path: /opt/union/scripts/overlay-setup.sh
    content: |
      {{ overlay_script | indent(6) }}
    permissions: '0755'
    owner: root:root
  
  # systemd 유닛
  - path: /etc/systemd/system/union-overlay.service
    content: |
      [Unit]
      Description=Union OverlayFS Mount Service
      After=network-online.target
      Wants=network-online.target
      
      [Service]
      Type=oneshot
      ExecStart=/opt/union/scripts/overlay-setup.sh
      RemainAfterExit=yes
      
      [Install]
      WantedBy=multi-user.target
    permissions: '0644'
    owner: root:root

runcmd:
  - systemctl daemon-reload
  - systemctl enable union-overlay.service
  - systemctl start union-overlay.service
```

### OverlayFS 설정 스크립트 템플릿

```bash
#!/bin/bash
# overlay-setup.sh.j2 - OverlayFS 구성 스크립트
# cloud-init이 생성하며, systemd가 매 부팅 시 실행

set -euo pipefail

LOG=/var/log/union-overlay.log
exec >> "$LOG" 2>&1
echo "[$(date)] Union OverlayFS 구성 시작"

# ---------------------------------------------------------------------------
# 1. Manila 레이어 마운트 (CephFS)
# ---------------------------------------------------------------------------
mkdir -p /opt/layers
mkdir -p /opt/workspace/{upper,work,merged}

mount_cephfs() {
    local layer_name="$1"
    local export_path="$2"
    local cephx_id="$3"
    local mountpoint="/opt/layers/${layer_name}"
    
    mkdir -p "$mountpoint"
    
    # 이미 마운트된 경우 스킵
    mountpoint -q "$mountpoint" && return 0
    
    # 커널 CephFS 우선, ceph-fuse 폴백
    if modprobe ceph 2>/dev/null; then
        mount -t ceph "$export_path" "$mountpoint" \
            -o "name=${cephx_id},secretfile=/etc/ceph/ceph.client.${cephx_id}.keyring,_netdev"
    else
        ceph-fuse "$mountpoint" \
            --id="$cephx_id" \
            --keyring="/etc/ceph/ceph.client.${cephx_id}.keyring"
    fi
    echo "[$(date)] 레이어 마운트 완료: ${layer_name}"
}

# 레이어 마운트 실행 (DB에서 조회한 순서)
{% for layer in layers %}
mount_cephfs "{{ layer.name }}" "{{ layer.export_path }}" "{{ layer.cephx_id }}"
{% endfor %}

# ---------------------------------------------------------------------------
# 2. Writable 레이어 준비 (Cinder 볼륨)
# ---------------------------------------------------------------------------
UPPER_DEV="{{ upper_device }}"

if [ -n "$UPPER_DEV" ] && [ -b "$UPPER_DEV" ]; then
    # 장치 대기
    for i in $(seq 1 30); do
        [ -b "$UPPER_DEV" ] && break
        echo "장치 대기 중... ($i/30)"
        sleep 2
    done
    
    # 파일시스템 생성 (필요시)
    if ! blkid "$UPPER_DEV" | grep -q ext4; then
        mkfs.ext4 -F "$UPPER_DEV"
    fi
    
    # 마운트
    mount "$UPPER_DEV" /opt/workspace/upper
    mkdir -p /opt/workspace/upper/{usr_local,opt}
    
    echo "[$(date)] Writable 레이어 마운트 완료: ${UPPER_DEV}"
fi

# ---------------------------------------------------------------------------
# 3. Lowerdir 순서 결정 (토폴로지 정렬된 순서)
#    OverlayFS에서 왼쪽이 최신 레이어 (가장 높은 우선순위)
#    파일 중복 시 왼쪽 레이어의 파일이 우선적으로 사용됨
# ---------------------------------------------------------------------------
# 예: vllm이 torch에 의존, torch가 python에 의존
#     → 최신(의존성 높은) 레이어가 왼쪽에 배치
# lowerdir = /opt/layers/vllm-0.6/usr/local:/opt/layers/torch-2.4/usr/local:/opt/layers/python-3.11/usr/local

LOWER_DIRS_USR_LOCAL=""
LOWER_DIRS_OPT=""

{% for layer in layers %}
LOWER_DIRS_USR_LOCAL="${LOWER_DIRS_USR_LOCAL}:/opt/layers/{{ layer.name }}/usr/local"
LOWER_DIRS_OPT="${LOWER_DIRS_OPT}:/opt/layers/{{ layer.name }}/opt"
{% endfor %}

# 앞의 콜론 제거
LOWER_DIRS_USR_LOCAL="${LOWER_DIRS_USR_LOCAL#:}"
LOWER_DIRS_OPT="${LOWER_DIRS_OPT#:}"

echo "[$(date)] Lowerdir 순서 (usr/local): ${LOWER_DIRS_USR_LOCAL}"
echo "[$(date)] Lowerdir 순서 (opt): ${LOWER_DIRS_OPT}"

# ---------------------------------------------------------------------------
# 4. OverlayFS 마운트
# ---------------------------------------------------------------------------
# /usr/local OverlayFS
if ! mountpoint -q /usr/local; then
    # 기존 /usr/local 백업
    if [ -d /usr/local ] && [ "$(ls -A /usr/local 2>/dev/null)" ]; then
        mv /usr/local /usr/local.bak
    fi
    mkdir -p /usr/local
    
    mount -t overlay overlay \
        -o "lowerdir=${LOWER_DIRS_USR_LOCAL},upperdir=/opt/workspace/upper/usr_local,workdir=/opt/workspace/work/usr_local" \
        /usr/local
    
    echo "[$(date)] /usr/local OverlayFS 마운트 완료"
fi

# /opt OverlayFS (선택적)
{% if mount_opt %}
if ! mountpoint -q /opt; then
    mount -t overlay overlay \
        -o "lowerdir=${LOWER_DIRS_OPT},upperdir=/opt/workspace/upper/opt,workdir=/opt/workspace/work/opt" \
        /opt
    
    echo "[$(date)] /opt OverlayFS 마운트 완료"
fi
{% endif %}

# ---------------------------------------------------------------------------
# 5. 환경 변수 설정
# ---------------------------------------------------------------------------
echo "PATH=/usr/local/bin:/usr/bin:/bin" > /etc/profile.d/union-path.sh
echo "export PATH" >> /etc/profile.d/union-path.sh
echo "PYTHONPATH=/usr/local/lib/python{{ python_version }}/site-packages" > /etc/profile.d/union-python.sh
echo "export PYTHONPATH" >> /etc/profile.d/union-python.sh

echo "[$(date)] Union OverlayFS 구성 완료"
```

### 동적 설치 템플릿 (Strategy B)

```bash
#!/bin/bash
# strategy_dynamic.sh.j2 - 첫 부팅 시 라이브러리 설치 (uv 사용)

set -euo pipefail

LOG=/var/log/union-dynamic-install.log
exec >> "$LOG" 2>&1
echo "[$(date)] 동적 라이브러리 설치 시작"

MARKER=/var/lib/union/.install_done
[ -f "$MARKER" ] && { echo "이미 설치됨, 스킵"; exit 0; }

# uv 설치
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# OverlayFS 마운트 대기
for i in $(seq 1 30); do
    mountpoint -q /usr/local && break
    echo "OverlayFS 대기 중... ($i/30)"
    sleep 5
done

# 라이브러리 설치
{% for library in libraries %}
case "{{ library.type }}" in
    "python")
        echo "[$(date)] Python {{ library.version }} 설치 중..."
        uv python install {{ library.version }}
        ;;
    "torch")
        echo "[$(date)] PyTorch {{ library.version }} 설치 중..."
        uv pip install --system --no-cache-dir \
            torch=={{ library.version }} \
            torchvision=={{ library.version }} \
            {% if library.variant %}--index-url https://download.pytorch.org/whl/{{ library.variant }}{% endif %}
        ;;
    "vllm")
        echo "[$(date)] vLLM {{ library.version }} 설치 중..."
        uv pip install --system --no-cache-dir vllm=={{ library.version }}
        ;;
    "jupyter")
        echo "[$(date)] Jupyter Lab {{ library.version }} 설치 중..."
        uv pip install --system --no-cache-dir jupyterlab=={{ library.version }} ipykernel
        ;;
esac
{% endfor %}

mkdir -p /var/lib/union
touch "$MARKER"
echo "[$(date)] 동적 라이브러리 설치 완료"
```

---

## 웹서버 API 흐름

### 인스턴스 생성 시 레이어 조합

```python
# backend/app/services/layer_composer.py

from typing import List
from sqlalchemy.orm import Session
from backend.app.models.layer import LibraryLayer, MountConfiguration

class LayerComposer:
    """레이어 조합 및 Cloud-init 생성 서비스"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_layer_order(self, layer_ids: List[str]) -> List[LibraryLayer]:
        """
        의존성 그래프를 기반으로 토폴로지 정렬 수행.
        레이어 순서: 의존성이 낮은 것부터 높은 순으로 배치.
        OverlayFS lowerdir에서는 반대 순서 (의존성 높은 것이 먼저).
        """
        
        layers = self.db.query(LibraryLayer).filter(
            LibraryLayer.name.in_(layer_ids)
        ).all()
        
        # 의존성 그래프 구성
        graph = {layer.name: set(layer.depends_on) for layer in layers}
        
        # 토폴로지 정렬 (Kahn's algorithm)
        result = []
        visited = set()
        
        def visit(name: str):
            if name in visited:
                return
            visited.add(name)
            for dep in graph.get(name, []):
                visit(dep)
            layer = next((l for l in layers if l.name == name), None)
            if layer:
                result.append(layer)
        
        for layer in layers:
            visit(layer.name)
        
        # OverlayFS 순서로 반전 (의존성 높은 것이 먼저)
        return list(reversed(result))
    
    def check_compatibility(
        self,
        ubuntu_version: str,
        python_version: str,
        layers: List[LibraryLayer],
    ) -> bool:
        """OS/Python 호환성 검사"""
        
        for layer in layers:
            if ubuntu_version not in layer.ubuntu_versions:
                # 호환성 매트릭스 확인
                compatible = self.db.query(OSCompatibility).filter(
                    OSCompatibility.source_ubuntu_id == layer.ubuntu_versions[0],
                    OSCompatibility.target_ubuntu_id == ubuntu_version,
                    OSCompatibility.is_compatible == True,
                ).first()
                if not compatible:
                    return False
            
            if python_version not in layer.python_versions:
                return False
        
        return True
    
    def generate_cloudinit(
        self,
        config: MountConfiguration,
    ) -> str:
        """Cloud-init userdata 생성"""
        
        from jinja2 import Environment, FileSystemLoader
        
        env = Environment(loader=FileSystemLoader('/opt/union/templates'))
        
        # 레이어 순서 조회
        layers = self.get_layer_order(config.layer_ids)
        
        # OverlayFS 스크립트 생성
        overlay_script = env.get_template('overlay-setup.sh.j2').render(
            layers=[
                {
                    'name': layer.name,
                    'export_path': layer.manila_export_path,
                    'cephx_id': f"union-{config.instance_id[:8]}-{layer.name}",
                }
                for layer in layers
            ],
            upper_device=config.upper_device,
            python_version=config.python_version_id,
            mount_opt=True,
        )
        
        # Cloud-init YAML 생성
        cloudinit = env.get_template('cloud-init/base.yaml.j2').render(
            shares=[{
                'cephx_id': f"union-{config.instance_id[:8]}-{layer.name}",
                'cephx_key': layer.cephx_key,  # Manila에서 조회
            } for layer in layers],
            overlay_script=overlay_script,
            layers=layers,
        )
        
        return cloudinit
```

### API 엔드포인트

```python
# backend/app/api/layers.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.services.layer_composer import LayerComposer
from backend.app.models.layer import LibraryLayer, MountConfiguration

router = APIRouter(prefix="/api/layers", tags=["layers"])

@router.get("/")
def list_layers(db: Session = Depends(get_db)):
    """사용 가능한 레이어 목록 조회"""
    return db.query(LibraryLayer).filter(
        LibraryLayer.build_status == "ready"
    ).all()

@router.get("/{layer_name}")
def get_layer(layer_name: str, db: Session = Depends(get_db)):
    """레이어 상세 정보"""
    layer = db.query(LibraryLayer).filter(
        LibraryLayer.name == layer_name
    ).first()
    if not layer:
        raise HTTPException(status_code=404, detail="Layer not found")
    return layer

@router.post("/compose")
def compose_layers(
    ubuntu_version: str,
    python_version: str,
    layer_names: list[str],
    db: Session = Depends(get_db),
):
    """레이어 조합 및 cloud-init 생성"""
    
    composer = LayerComposer(db)
    
    # 1. 레이어 순서 결정
    layers = composer.get_layer_order(layer_names)
    
    # 2. 호환성 검사
    if not composer.check_compatibility(ubuntu_version, python_version, layers):
        raise HTTPException(
            status_code=400,
            detail="호환되지 않는 레이어 조합입니다."
        )
    
    # 3. cloud-init 생성
    # (실제로는 인스턴스 생성 시 호출)
    
    return {
        "layer_order": [l.name for l in layers],
        "compatible": True,
    }
```

---

## 쉘 스크립트 초안

### 레이어 동기화 스크립트

```bash
#!/bin/bash
# layer-sync.sh - Manila에서 레이어 동기화

set -euo pipefail

MANILA_ENDPOINT="${MANILA_ENDPOINT:?MANILA_ENDPOINT required}"
PROJECT_ID="${PROJECT_ID:?PROJECT_ID required}"
TOKEN="${TOKEN:?TOKEN required}"

LAYER_DIR="/opt/layers"
CACHE_FILE="/opt/union/db/layers_cache.json"

echo "[layer-sync] 레이어 목록 동기화 중..."

# Manila share 목록 조회
curl -s -H "X-Auth-Token: $TOKEN" \
    "${MANILA_ENDPOINT}/${PROJECT_ID}/shares/detail?metadata=%7B%22union_type%22%3A%22prebuilt%22%7D" \
    | jq -r '.shares[] | select(.metadata.union_status == "ready")' \
    > "$CACHE_FILE"

echo "[layer-sync] 동기화 완료: $(jq 'length' "$CACHE_FILE")개 레이어"
```

### 상태 확인 스크립트

```bash
#!/bin/bash
# health-check.sh - OverlayFS 상태 확인

set -euo pipefail

echo "=== Union OverlayFS 상태 ==="
echo ""

echo "--- Mounted Layers ---"
mount | grep "/opt/layers" || echo "마운트된 레이어 없음"
echo ""

echo "--- OverlayFS Status ---"
if mountpoint -q /usr/local; then
    echo "/usr/local: OverlayFS 마운트됨"
    cat /proc/mounts | grep "/usr/local"
else
    echo "/usr/local: 마운트되지 않음"
fi
echo ""

if mountpoint -q /opt/workspace/merged; then
    echo "/opt/workspace/merged: 마운트됨"
else
    echo "/opt/workspace/merged: 마운트되지 않음"
fi
echo ""

echo "--- Layer Sizes ---"
for layer in /opt/layers/*/; do
    if [ -d "$layer" ]; then
        name=$(basename "$layer")
        size=$(du -sh "$layer" 2>/dev/null | cut -f1)
        echo "$name: $size"
    fi
done
echo ""

echo "--- Installed Packages ---"
python_versions=()
for p in /opt/layers/python-*/; do
    [ -d "$p" ] && python_versions+=("$(basename "$p")")
done

if [ ${#python_versions[@]} -gt 0 ]; then
    echo "Python: ${python_versions[*]}"
fi

if [ -f "/usr/local/bin/python3" ]; then
    echo "Active Python: $(/usr/local/bin/python3 --version 2>&1)"
fi

if command -v python3 &>/dev/null; then
    echo ""
    echo "--- pip list ---"
    python3 -m pip list --format=freeze 2>/dev/null || true
fi
```

### 언마운트 스크립트

```bash
#!/bin/bash
# union-umount.sh - OverlayFS 언마운트

set -euo pipefail

echo "[union-umount] OverlayFS 언마운트 시작"

# 1. OverlayFS 언마운트
if mountpoint -q /usr/local; then
    echo "언마운트: /usr/local"
    umount /usr/local
fi

if mountpoint -q /opt; then
    echo "언마운트: /opt"
    umount /opt
fi

# 2. Writable 레이어 언마운트
if mountpoint -q /opt/workspace/upper; then
    echo "언마운트: /opt/workspace/upper"
    umount /opt/workspace/upper
fi

# 3. 레이어 마운트 해제
for layer in /opt/layers/*/; do
    if mountpoint -q "$layer"; then
        echo "언마운트: $layer"
        umount "$layer"
    fi
done

echo "[union-umount] 완료"
```

---

## 사용 예시

### 1. 레이어 빌드 (관리자)

```bash
# Python 3.11 레이어 빌드
./build-layer.sh python 3.11.0 --python 3.11

# PyTorch 2.4 (CUDA 12.1) 레이어 빌드
./build-layer.sh torch 2.4.0 --python 3.11 --variant cu121

# vLLM 0.6 레이어 빌드
./build-layer.sh vllm 0.6.0 --python 3.11 --variant cu121

# Jupyter Lab 4.2 레이어 빌드
./build-layer.sh jupyter 4.2.0 --python 3.11
```

### 2. API를 통한 레이어 조합

```bash
# 레이어 목록 조회
curl -H "X-Auth-Token: $TOKEN" \
    https://api.example.com/api/layers

# 레이어 조합 검증
curl -X POST \
    -H "X-Auth-Token: $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "ubuntu_version": "22.04",
        "python_version": "3.11",
        "layers": ["python-3.11", "torch-2.4-cu121", "vllm-0.6"]
    }' \
    https://api.example.com/api/layers/compose
```

### 3. 인스턴스 생성 시 Cloud-init 적용

```bash
# Nova 인스턴스 생성 (cloud-init userdata 포함)
openstack server create \
    --image ubuntu-22.04 \
    --flavor gpu.a100 \
    --user-data cloud-init.yaml \
    --boot-from-volume 100 \
    my-ml-instance
```

---

## 보안 아키텍처

### 개요

레이어 마운트를 위한 보안 모델은 **동적 읽기 전용 CephX 키**를 사용하여 각 인스턴스와 레이어별로 격리된 접근 권한을 제공합니다.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Security Architecture                            │
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐        │
│  │ Layer DB     │     │ Ceph Auth    │     │ Key Manager  │        │
│  │ (PostgreSQL) │     │ (CephX)      │     │ (Backend)    │        │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘        │
│         │                    │                    │                 │
│         │   1. 레이어 경로   │                    │                 │
│         │◄───────────────────┤                    │                 │
│         │                    │                    │                 │
│         │   2. 키 생성 요청   │                    │                 │
│         │────────────────────┼───────────────────►│                 │
│         │                    │                    │                 │
│         │                    │   3. ceph auth    │                 │
│         │                    │◄──────────────────┤                 │
│         │                    │                    │                 │
│         │                    │   4. 읽기 전용 키  │                 │
│         │                    ├───────────────────►│                 │
│         │                    │                    │                 │
│         │   5. cloud-init에 키 포함              │                 │
│         │◄───────────────────────────────────────┤                 │
│         │                    │                    │                 │
└─────────┼────────────────────┼────────────────────┼─────────────────┘
          │                    │                    │
          │                    │                    ▼
          │            ┌───────┴───────┐    ┌──────────────┐
          │            │ CephFS Cluster│    │ Nova Instance│
          │            │               │    │              │
          │            │ /union-layers │◄───│ mount -t ceph│
          │            │   /torch-2.4  │    │ (readonly)   │
          │            │   /vllm-0.6   │    │              │
          │            └───────────────┘    └──────────────┘
          │                     ▲
          │                     │
          └─────────────────────┘
                    6. 인스턴스 삭제 시 키 폐기
```

---

### CephX 권한 설정

#### 경로 기반 읽기 전용 권한

각 레이어는 CephFS 내에서 독립된 디렉토리로 관리되며, CephX 키는 해당 경로에만 읽기 권한을 가집니다.

```bash
# CephX 키 생성 명령어
ceph auth get-or-create client.union-{instance_id}-{layer_name} \
    mon 'allow r' \
    osd 'allow r pool=cephfs_data path=/union-layers/{layer_name}' \
    -o /etc/ceph/ceph.client.union-{instance_id}-{layer_name}.keyring
```

#### 권한 레벨 설명

| 권한 | 범위 | 설명 |
|------|------|------|
| `mon allow r` | 모니터 | 클러스터 상태 조회 (마운트에 필요) |
| `osd allow r pool=cephfs_data` | OSD | CephFS 데이터 풀 읽기 |
| `path=/union-layers/{layer}` | 경로 제한 | 특정 레이어 디렉토리만 접근 |

#### 키 네이밍 규칙

```
client.union-{instance_short_id}-{layer_name}

예시:
- client.union-a1b2c3d4-torch-2.4-cu121
- client.union-a1b2c3d4-vllm-0.6
- client.union-e5f6g7h8-python-3.11
```

---

### 키 수명 주기 관리

#### 1. 키 생성 (인스턴스 생성 시)

```python
# backend/app/services/cephx_manager.py

import subprocess
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.models.layer import LibraryLayer, CephXKeyRecord

logger = logging.getLogger(__name__)

class CephXKeyManager:
    """CephX 키 수명 주기 관리"""
    
    CEPHFS_POOL = "cephfs_data"
    LAYER_BASE_PATH = "/union-layers"
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_layer_key(
        self,
        layer_name: str,
        instance_id: str,
        expiry_hours: int = 72,
    ) -> dict:
        """
        레이어별 읽기 전용 CephX 키 생성
        
        Args:
            layer_name: 레이어 이름 (예: torch-2.4-cu121)
            instance_id: Nova 인스턴스 UUID
            expiry_hours: 키 만료 시간 (기본 72시간)
        
        Returns:
            dict: cephx_id, cephx_key, layer_path, expiry
        """
        
        # 1. 레이어 정보 조회
        layer = self.db.query(LibraryLayer).filter_by(name=layer_name).first()
        if not layer:
            raise ValueError(f"Layer not found: {layer_name}")
        
        # 2. CephX ID 생성
        instance_short = instance_id[:8]
        cephx_id = f"client.union-{instance_short}-{layer_name}"
        
        # 3. 레이어 경로
        layer_path = f"{self.LAYER_BASE_PATH}/{layer_name}"
        
        # 4. Ceph에서 키 생성
        try:
            result = subprocess.run(
                [
                    "ceph", "auth", "get-or-create",
                    cephx_id,
                    "mon", "allow r",
                    "osd", f"allow r pool={self.CEPHFS_POOL} path={layer_path}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            
            # 키 추출
            cephx_key = self._extract_key(result.stdout)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"CephX key creation failed: {e.stderr}")
            raise RuntimeError(f"Failed to create CephX key: {e.stderr}")
        
        # 5. DB에 기록
        expiry = datetime.utcnow() + timedelta(hours=expiry_hours)
        
        key_record = CephXKeyRecord(
            cephx_id=cephx_id,
            cephx_key=cephx_key,
            layer_id=layer.id,
            instance_id=instance_id,
            layer_path=layer_path,
            expiry_at=expiry,
            is_active=True,
        )
        self.db.add(key_record)
        self.db.commit()
        
        logger.info(f"CephX key created: {cephx_id} for layer {layer_name}")
        
        return {
            "cephx_id": cephx_id,
            "cephx_key": cephx_key,
            "layer_path": layer_path,
            "expiry": expiry.isoformat(),
        }
    
    async def revoke_key(self, cephx_id: str) -> bool:
        """
        CephX 키 폐기
        """
        
        try:
            # 1. Ceph에서 키 삭제
            subprocess.run(
                ["ceph", "auth", "del", cephx_id],
                capture_output=True,
                text=True,
                check=True,
            )
            
            # 2. DB에서 비활성화
            record = self.db.query(CephXKeyRecord).filter_by(
                cephx_id=cephx_id
            ).first()
            if record:
                record.is_active = False
                self.db.commit()
            
            logger.info(f"CephX key revoked: {cephx_id}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"CephX key revocation failed: {e.stderr}")
            return False
    
    async def revoke_instance_keys(self, instance_id: str) -> int:
        """
        인스턴스와 연관된 모든 키 폐기
        (인스턴스 삭제 시 호출)
        """
        
        records = self.db.query(CephXKeyRecord).filter_by(
            instance_id=instance_id,
            is_active=True,
        ).all()
        
        revoked_count = 0
        for record in records:
            if await self.revoke_key(record.cephx_id):
                revoked_count += 1
        
        logger.info(f"Revoked {revoked_count} keys for instance {instance_id}")
        return revoked_count
    
    def _extract_key(self, output: str) -> str:
        """Ceph auth 출력에서 키 추출"""
        import re
        match = re.search(r'key\s*=\s*([A-Za-z0-9+/=]+)', output)
        if match:
            return match.group(1)
        raise ValueError("Could not extract key from Ceph output")
```

#### 2. 키 사용 (Cloud-init)

```yaml
# cloud-init 보안 템플릿
#cloud-config

write_files:
  # 각 레이어별 개별 키 (읽기 전용)
  {% for layer in layers %}
  - path: /etc/ceph/ceph.{{ layer.cephx_id }}.keyring
    content: |
      [{{ layer.cephx_id }}]
          key = {{ layer.cephx_key }}
          caps mon = "allow r"
          caps osd = "allow r pool=cephfs_data path={{ layer.layer_path }}"
    permissions: '0600'
    owner: root:root
  {% endfor %}

runcmd:
  # 각 레이어 마운트 (읽기 전용)
  {% for layer in layers %}
  - |
    mkdir -p /opt/layers/{{ layer.name }}
    mount -t ceph {{ layer.layer_path }} /opt/layers/{{ layer.name }} \
      -o "name={{ layer.cephx_id }},secretfile=/etc/ceph/ceph.{{ layer.cephx_id }}.keyring,ro,_netdev"
  {% endfor %}
```

#### 3. 키 폐기 (인스턴스 삭제 시)

```python
# backend/app/api/instances.py

from fastapi import APIRouter, Depends, BackgroundTasks
from backend.app.services.cephx_manager import CephXKeyManager

router = APIRouter()

@router.delete("/instances/{instance_id}")
async def delete_instance(
    instance_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """인스턴스 삭제 및 연관 키 폐기"""
    
    # 1. Nova 인스턴스 삭제
    await nova_client.delete_instance(instance_id)
    
    # 2. 백그라운드에서 키 폐기
    key_manager = CephXKeyManager(db)
    background_tasks.add_task(
        key_manager.revoke_instance_keys,
        instance_id,
    )
    
    return {"status": "deleted", "instance_id": instance_id}
```

---

### DB 스키마 확장

```sql
-- CephX 키 기록 테이블
CREATE TABLE cephx_key_records (
    id SERIAL PRIMARY KEY,
    cephx_id VARCHAR(100) NOT NULL UNIQUE,     -- client.union-{inst}-{layer}
    cephx_key TEXT NOT NULL,                    -- 키 값 (암호화 저장 권장)
    layer_id INT REFERENCES library_layers(id),
    instance_id UUID NOT NULL,                  -- Nova instance ID
    layer_path VARCHAR(255) NOT NULL,           -- /union-layers/{layer}
    expiry_at TIMESTAMP NOT NULL,               -- 만료 시간
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP,
    
    INDEX idx_cephx_instance (instance_id),
    INDEX idx_cephx_expiry (expiry_at),
    INDEX idx_cephx_active (is_active)
);

-- 만료 키 정리를 위한 인덱스
CREATE INDEX idx_cephx_cleanup ON cephx_key_records(expiry_at) 
    WHERE is_active = true;
```

---

### 보안 체크리스트

#### 인스턴스 생성 시

- [ ] 각 레이어별 읽기 전용 CephX 키 생성
- [ ] 키에 경로 제한 설정 (`path=/union-layers/{layer}`)
- [ ] Cloud-init에 키 포함 (암호화 권장)
- [ ] DB에 키 기록 및 만료 시간 설정

#### 인스턴스 실행 중

- [ ] `/etc/ceph/*.keyring` 파일 권한 0600 유지
- [ ] 마운트 옵션에 `ro` (읽기 전용) 포함
- [ ] 불필요한 키 파일 정기적 감사

#### 인스턴스 삭제 시

- [ ] Ceph에서 키 즉시 폐기 (`ceph auth del`)
- [ ] DB에서 키 비활성화
- [ ] Cinder 볼륨 정리 (writable 레이어)

#### 정기 유지보수

- [ ] 만료된 키 자동 정리 (cron job)
- [ ] 미사용 키 감사 로그

---

### 만료 키 정리 스크립트

```bash
#!/bin/bash
# cleanup-expired-keys.sh - 만료된 CephX 키 정리
# cron: 0 */6 * * * /opt/union/scripts/cleanup-expired-keys.sh

set -euo pipefail

LOG="/var/log/union-key-cleanup.log"
exec >> "$LOG" 2>&1

echo "[$(date)] 만료 키 정리 시작"

# DB에서 만료된 키 조회
EXPIRED_KEYS=$(psql -h localhost -U union -d union -t -c "
    SELECT cephx_id FROM cephx_key_records 
    WHERE expiry_at < NOW() AND is_active = true
")

for cephx_id in $EXPIRED_KEYS; do
    [ -z "$cephx_id" ] && continue
    
    echo "[$(date)] 폐기: $cephx_id"
    
    # Ceph에서 삭제
    ceph auth del "$cephx_id" 2>/dev/null || true
    
    # DB에서 비활성화
    psql -h localhost -U union -d union -c "
        UPDATE cephx_key_records 
        SET is_active = false, revoked_at = NOW() 
        WHERE cephx_id = '$cephx_id'
    "
done

echo "[$(date)] 만료 키 정리 완료"
```

---

### 보안 vs 성능 비교

| 방식 | 보안 | 성능 | 복잡도 | 권장 상황 |
|------|------|------|--------|----------|
| **동적 읽기 전용 키** (현재) | 높음 | 높음 | 중간 | 프로덕션 |
| 단일 공유 키 | 낮음 | 높음 | 낮음 | 테스트 환경 |
| NFS Gateway | 높음 | 중간 | 높음 | 보안 최우선 |
| 읽기 전용 레이어 없음 | - | - | - | (비권장) |

---

## 참고

- **uv 공식 문서**: https://docs.astral.sh/uv/
- **OverlayFS 커널 문서**: https://www.kernel.org/doc/Documentation/filesystems/overlayfs.txt
- **Manila CephFS 드라이버**: https://docs.openstack.org/manila/latest/contributor/driver_cephfs.html
- **cloud-init 문서**: https://cloudinit.readthedocs.io/