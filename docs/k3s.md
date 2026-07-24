# k3s 클러스터 프로비저닝

**Language:** 한국어 · [English](en/k3s.md)

Afterglow는 OpenStack의 Magnum 서비스 없이 VM에 k3s를 직접 배포하여 Kubernetes 환경을 제공합니다.

---

## 개요

### Magnum 대비 장점

| 항목 | Magnum | Afterglow k3s |
|---|---|---|
| 설치 복잡도 | Heat 템플릿 + 별도 서비스 설치 필요 | OpenStack 기본 서비스만으로 동작 |
| 지원 배포판 | 제한적 | Ubuntu 22.04 / 24.04 (CoreOS 예정) |
| 경량성 | 무거운 풀 Kubernetes | k3s — 단일 바이너리, 메모리 512MB~ |
| 프로비저닝 속도 | 10~20분 | 3~5분 |
| 이력 관리 | 없음 | soft-delete로 삭제 이력 영구 보존 |

### 아키텍처

```
Afterglow 대시보드
    │
    ├── Nova: 마스터 노드 VM 생성
    │     └── cloud-init: k3s server 설치
    │
    ├── Nova: 워커 노드 VM 생성 (선택)
    │     └── cloud-init: k3s agent 조인
    │
    └── kubeconfig → 사용자 다운로드
```

---

## 클러스터 생성

### 대시보드에서 생성

1. **컨테이너 → k3s 클러스터** 메뉴 이동
2. **클러스터 생성** 버튼 클릭
3. 설정 입력:
   - 클러스터 이름
   - 마스터 노드 플레이버 (권장: 2vCPU / 4GB RAM 이상)
   - 워커 노드 수 및 플레이버
   - 네트워크 / 보안 그룹 선택
4. **배포** → 생성 진행 상황 실시간 확인

### cloud-init 동작 방식

마스터 노드 VM 생성 시 Afterglow가 다음 cloud-init을 자동 생성합니다:

```yaml
#cloud-config
package_update: true
packages:
  - curl

runcmd:
  # k3s 서버 설치
  - curl -sfL https://get.k3s.io | sh -s - server \
      --disable traefik \
      --node-name master-01
  # kubeconfig 권한 설정
  - chmod 644 /etc/rancher/k3s/k3s.yaml
```

워커 노드는 마스터의 join token을 자동 주입받아 클러스터에 합류합니다:

```yaml
runcmd:
  - curl -sfL https://get.k3s.io | K3S_URL=https://<master-ip>:6443 \
      K3S_TOKEN=<join-token> sh -
```

---

## 클러스터 관리

### kubeconfig 다운로드

클러스터 상세 페이지 → **kubeconfig 다운로드** 버튼

```bash
# 다운로드한 kubeconfig 적용
export KUBECONFIG=~/Downloads/afterglow-cluster.yaml
kubectl get nodes
```

### 클러스터 상태 확인

| 상태 | 설명 |
|---|---|
| `CREATING` | VM 생성 및 k3s 설치 중 |
| `ACTIVE` | 정상 운영 중 |
| `ERROR` | 생성 실패 |
| `DELETED` | 삭제됨 (이력 조회 가능) |

### 삭제 이력 조회

삭제된 클러스터는 soft-delete로 처리되어 이력이 보존됩니다:

```
대시보드 → k3s 클러스터 → "삭제된 클러스터 보기" 토글
```

삭제된 항목은 회색으로 표시되며 삭제 시각, 삭제한 사용자를 확인할 수 있습니다.

---

## 네트워크 구성

### 권장 보안 그룹 규칙

마스터 노드에 적용할 인바운드 규칙:

| 포트 | 프로토콜 | 용도 |
|---|---|---|
| 6443 | TCP | Kubernetes API 서버 |
| 10250 | TCP | kubelet API |
| 2379-2380 | TCP | etcd (멀티 마스터) |
| 8472 | UDP | Flannel VXLAN |
| 51820 | UDP | WireGuard (선택) |

워커 노드:

| 포트 | 프로토콜 | 용도 |
|---|---|---|
| 10250 | TCP | kubelet API |
| 30000-32767 | TCP/UDP | NodePort 서비스 |
| 8472 | UDP | Flannel VXLAN |

### Floating IP 연결

외부에서 API 서버에 접근하려면 마스터 노드에 Floating IP를 연결합니다:

```bash
# OpenStack CLI로 Floating IP 연결
openstack floating ip create <external-network>
openstack server add floating ip <master-vm-id> <floating-ip>
```

---

## OS 지원 현황 및 로드맵

### 현재: Ubuntu

| 버전 | 상태 |
|---|---|
| Ubuntu 22.04 LTS (Jammy) | ✅ 지원 |
| Ubuntu 24.04 LTS (Noble) | ✅ 지원 |

### 예정: Fedora CoreOS

불변 인프라(Immutable Infrastructure) 원칙에 따라 Fedora CoreOS로 전환을 계획하고 있습니다.

**CoreOS 전환 이유:**

- **rpm-ostree** 기반 원자적 OS 업데이트 — 롤백 지원
- **불변 루트 파일시스템** — 드리프트 방지
- **Ignition** 기반 선언적 초기화 (cloud-init 대체)
- Kubernetes 워크로드에 최적화된 경량 OS

**전환 계획:**

```
현재: Ubuntu + cloud-init
  └── k3s 바이너리 직접 설치

예정: Fedora CoreOS + Ignition
  ├── Butane YAML → Ignition JSON 변환
  ├── k3s systemd unit 선언적 구성
  └── rpm-ostree layering으로 추가 패키지 관리
```

Ignition 설정 예시 (계획):

```yaml
# butane 설정 (YAML) → ignition (JSON) 변환
variant: fcos
version: 1.5.0
systemd:
  units:
    - name: k3s.service
      enabled: true
      contents: |
        [Unit]
        Description=k3s server
        After=network-online.target

        [Service]
        ExecStartPre=/usr/local/bin/install-k3s.sh
        ExecStart=/usr/local/bin/k3s server
        Restart=always

        [Install]
        WantedBy=multi-user.target
```

---

## 문제 해결

### k3s 설치 실패

```bash
# VM에 SSH 접속 후 cloud-init 로그 확인
sudo cat /var/log/cloud-init-output.log
sudo systemctl status k3s
```

### 워커 노드 조인 실패

```bash
# 마스터에서 join token 확인
sudo cat /var/lib/rancher/k3s/server/node-token

# 워커에서 agent 상태 확인
sudo systemctl status k3s-agent
sudo journalctl -u k3s-agent -n 50
```

### API 서버 접근 불가

1. 보안 그룹에서 6443 포트 개방 확인
2. Floating IP 연결 여부 확인
3. kubeconfig의 server 주소가 Floating IP인지 확인:

```bash
# kubeconfig 서버 주소 변경
kubectl config set-cluster default \
  --server=https://<floating-ip>:6443
```

---

## Cloud Provider OpenStack 플러그인

k3s 클러스터는 Cloud Provider OpenStack 플러그인 레지스트리를 통해 다양한 OpenStack 서비스와 통합됩니다. 각 플러그인은 `config.toml [k3s]` 섹션에서 독립적으로 활성화할 수 있습니다。

### 지원 플러그인

| 플러그인 | 설정 키 | 용도 |
|---------|--------|------|
| **OCCM** (OpenStack Cloud Controller Manager) | `occm_enabled` | 노드 초기화, Service 타입 LoadBalancer → Octavia LB 자동 생성 |
| **Cinder CSI** | `cinder_csi_enabled` | PVC → Cinder 블록 스토리지 자동 프로비저닝 |
| **Manila CSI** | `manila_csi_enabled` | PVC → Manila NFS (ReadWriteMany) 자동 프로비저닝 |
| **Octavia Ingress** | `octavia_ingress_enabled` | Ingress 리소스 → Octavia LB 자동 생성 |
| **Keystone Auth** | `keystone_auth_enabled` | Kubernetes 인증 → Keystone 토큰 연동 |
| **Barbican KMS** | `barbican_kms_enabled` | Kubernetes Secret at-rest 암호화 → Barbican 연동 |

### config.toml 예시

```toml
[k3s]
occm_enabled = true
cinder_csi_enabled = true
manila_csi_enabled = false
octavia_ingress_enabled = false
keystone_auth_enabled = false
barbican_kms_enabled = false
```

### 플러그인 배포 과정

클러스터 생성 시 플러그인 레지스트리가 다음을 집계합니다:

1. **cloud.conf** — OCCM과 Cinder CSI가 공유하는 `/etc/kubernetes/cloud.conf` (OpenStack 인증 정보)
2. **manifests** — 각 플러그인의 Kubernetes 매니페스트 파일
3. **server args** — K3s 설치 인자 (예: `--kube-apiserver-arg`)

cloud-init의 콜백 스크립트가 플러그인을 순차적으로 배포하며, 각 플러그인의 결과를 `plugin_status` 필드로 보고합니다:

```json
{
  "plugin_status": {
    "occm": "deployed",
    "cinder_csi": "deployed",
    "manila_csi": "failed"
  }
}
```

배포에 실패한 플러그인은 `failed` 상태로 표시되지만, 클러스터 자체는 정상 동작합니다。

### 클러스터 삭제 시 자동 정리

OCCM이 활성화된 클러스터 삭제 시, Kubernetes LoadBalancer 서비스가 생성한 Octavia LB가 orphan되지 않도록 자동 정리됩니다:

- `kube_service_{cluster_name}_` 접두사로 매칭되는 모든 Octavia LB를 cascade 삭제
- 정리 실패 시 warning 로그 후 삭제 계속 진행 (best-effort)

### 스케일 다운 시 노드 정리

워커 노드 스케일 다운 시, VM 삭제 전 Kubernetes 노드 오브젝트를 먼저 삭제합니다. 이렇게 하면 OCCM이 `failed to find object` 오류로 무한 재시도하는 것을 방지할 수 있습니다.

### kubeconfig 존재 확인 (HEAD)

`HEAD /api/v1/k3s/clusters/{id}/kubeconfig` 요청으로 kubeconfig 파일 존재 여부만 확인할 수 있습니다. 이는 파일을 다운로드하지 않고 클러스터 준비 상태를 확인할 때 유용합니다.
