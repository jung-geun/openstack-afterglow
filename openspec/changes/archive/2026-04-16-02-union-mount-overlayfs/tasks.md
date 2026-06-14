## 2. Union Mount (OverlayFS) 재설계 및 구현

> **목표**: Manila share(NFS) 레이어를 `/opt/layers/lower/`에 순차 마운트하고, `/opt/layers/upper/`와 함께 `/opt/layers/merged/`에 OverlayFS로 통합 마운트

### 2.1 Lower Layer — NFS 마운트

- [x] 2.1.1 디렉토리 구조 표준화
  ```
  /opt/layers/
  ├── lower/                    # 읽기 전용 레이어 (NFS 마운트 포인트)
  │   ├── python311/            # Python 3.11 레이어
  │   ├── torch/                # PyTorch 레이어
  │   ├── vllm/                 # vLLM 레이어
  │   └── jupyter/              # Jupyter 레이어
  ├── upper/                    # 쓰기 가능 레이어 (Cinder 볼륨)
  ├── work/                     # OverlayFS workdir
  └── merged/                   # OverlayFS 병합 마운트 포인트
  ```

- [x] 2.1.2 cloud-init 템플릿 재작성 (`overlay_setup.sh.j2`)
  - [x] CephFS 마운트 → NFS 마운트 전환 (프로토콜 자동 감지)
  - [x] `/opt/layers/lower_<lib_name>` 에 순차적 NFS 마운트
  - [x] 각 레이어 마운트 순서: 의존성 토폴로지 정렬 (기존 `libraries.py` 로직 활용)
  - [x] 마운트 실패 시 재시도 로직 (최대 30회, 5초 간격)
  - [x] NFS 마운트 vs CephFS 마운트 분기 처리

- [x] 2.1.3 프로토콜 자동 감지 로직
  - [x] Manila share `share_proto` 필드 기반 분기
  - [x] NFS: `mount -t nfs <export_location> /opt/layers/lower_<name>`
  - [x] CephFS: 기존 `mount -t ceph` 또는 `ceph-fuse` 로 폴백
  - [x] `cloudinit.py` — `generate_userdata()` 에 프로토콜 정보 전달

### 2.2 OverlayFS 마운트 — `/opt/layers/merged/`

- [x] 2.2.1 단일 OverlayFS 마운트 구현
  ```bash
  mount -t overlay overlay \
    -o "lowerdir=/opt/layers/lower/vllm:/opt/layers/lower/torch:/opt/layers/lower/python311,upperdir=/opt/layers/upper,workdir=/opt/layers/work" \
    /opt/layers/merged
  ```
  - [x] lowerdir 순서: 의존성이 높은 레이어가 우선 (왼쪽)
  - [x] 기존 `/usr/local` 및 `/opt` 개별 overlay → 단일 `/opt/layers/merged` 로 통합
  - [ ] 기본 OS lowerdir 포함 여부 결정 (필요시 `/usr/local` 원본을 마지막 lowerdir로)

- [x] 2.2.2 OverlayFS systemd 유닛 재설계
  - [x] `union-overlay.service`: 네트워크/원격 파일시스템 의존성 추가
    ```ini
    [Unit]
    After=network-online.target remote-fs.target
    Requires=network-online.target
    ```
  - [x] `After=remote-fs.target` — NFS 마운트 완료 후 OverlayFS 시작 보장
  - [x] 마운트 실패 시 자동 복구 로직 (`OnFailure=emergency.target`)

- [x] 2.2.3 Cinder 볼륨 upperdir 구성
  - [x] `/dev/vdb` (또는 설정 가능) 블록 장치 → `/opt/layers/upper` 마운트
  - [x] 최초 마운트 시 ext4 포맷 (`mkfs.ext4 -F`)
  - [x] `/opt/layers/upper` 및 `/opt/layers/work` 하위 디렉토리 자동 생성

### 2.3 마운트된 디렉토리 환경변수 등록

> **조사 결론**: `/usr/local` 심볼릭 링크 방식은 기존 시스템 바이너리와 충돌 위험이 있어 **하이브리드 방식**을 추천

- [x] 2.3.1 `/etc/profile.d/union-env.sh` — PATH 및 환경변수 설정
  ```bash
  export PATH="/opt/layers/merged/usr/local/bin:/opt/layers/merged/bin:$PATH"
  export LD_LIBRARY_PATH="/opt/layers/merged/usr/local/lib:/opt/layers/merged/usr/local/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export PYTHONPATH="/opt/layers/merged/usr/local/lib/python3.11/site-packages${PYTHONPATH:+:$PYTHONPATH}"
  export PKG_CONFIG_PATH="/opt/layers/merged/usr/local/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
  ```
  - [x] 로그인 셸 + 대화형 셸에 적용
  - [x] 라이브러리별 Python 버전에 따라 PYTHONPATH 동적 생성

- [x] 2.3.2 `/etc/environment` 업데이트 — 시스템 서비스에도 적용
  - [x] systemd 서비스(SSHD 등)가 overlay 경로의 바이너리를 찾을 수 있도록 `/etc/environment` 갱신

- [ ] 2.3.3 선택적 심볼릭 링크 생성 (보조)
  - [ ] `/opt/layers/merged/bin/python3` → `/usr/local/bin/python3` 심볼릭 링크
  - [ ] 기존 `/usr/local` 백업 후 심볼릭 링크 교체는 고위험 → profile.d 방식 우선
  - [ ] 관리자 옵션으로 `--symlink-mode` 제공 (호환성 필요 시)

- [x] 2.3.4 환경변수 템플릿 (`cloudinit_base.yaml.j2` 수정)
  - [x] `write_files` 에 `union-env.sh` 추가
  - [x] 라이브러리 의존성에 따른 PYTHONPATH 동적 구성
  - [x] GPU 관련 환경변수 (`CUDA_HOME`, `LD_LIBRARY_PATH` 등) 조건부 추가

---

