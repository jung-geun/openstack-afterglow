## 20. K3s 부팅 데드락 해소 — Barbican KMS / Keystone Auth host static pod 전환 (2026-05-10) — 8.14 후속 마감

> **배경**: 8.14에서 두 K3s 보안 플러그인이 부팅 데드락으로 강제 비활성화되어 있었다. Barbican KMS는 DaemonSet으로 동작해 apiserver 위에 놓여 KMS socket이 부팅 시 없어 chicken-and-egg, Keystone Auth는 cluster service URL을 webhook endpoint로 사용해 부팅 직후 DNS resolve 실패. 두 플러그인 모두 **host static pod**(`/var/lib/rancher/k3s/agent/pod-manifests/`)로 재구조화 — kubelet이 apiserver 의존 없이 직접 띄우므로 의존 역전 해소.

### 20.1 Barbican KMS — host static pod 전환

- [x] `backend/app/templates/k3s_plugins/barbican_kms/static_pod.yaml.j2` 신규 — kind=Pod, hostNetwork=true, priorityClassName=system-node-critical, hostPath /var/lib/kms (socket) + /etc/kubernetes/barbican-cloud.conf (cloud-config), securityContext.privileged=true
- [x] `backend/app/templates/k3s_plugins/barbican_kms/cloud_conf.yaml.j2` 신규 — [Global] + [KeyManager] 섹션. Secret 의존 제거, host file 0600. **보안 trade-off**: 기존 Secret(=etcd, KMS 미작동 시 plaintext)과 동등한 plaintext-at-rest posture, 위치만 다름 (의도적)
- [x] `backend/app/services/k3s_plugins/barbican_kms.py` 재작성:
  - `should_deploy()` 강제 False 제거 → `enabled + KEK + 자격증명` 검증
  - `extra_write_files()` 3건 (encryption-config.yaml, static pod manifest, barbican-cloud.conf) 모두 0600
  - `generate_manifests()` 빈 문자열 반환 (DaemonSet 제거)
  - `server_install_args()` 에 `--kubelet-arg=pod-manifest-path=/var/lib/rancher/k3s/agent/pod-manifests` 추가

### 20.2 Keystone Auth — hostNetwork host static pod 전환

- [x] `backend/app/templates/k3s_plugins/keystone_auth/static_pod.yaml.j2` 신규 — hostNetwork=true, `--listen=127.0.0.1:8443`, `--keystone-policy-file=/etc/policy/policy.json` (upstream 정확한 플래그명, PolicyFile은 PolicyConfigMap보다 우선이라 ConfigMap 의존 완전 제거)
- [x] `backend/app/templates/k3s_plugins/keystone_auth/webhook_config.yaml.j2` — endpoint `https://k8s-keystone-auth.kube-system.svc.cluster.local:8443/webhook` → `https://127.0.0.1:8443/webhook`
- [x] `backend/app/services/k3s_plugins/keystone_auth.py` 재작성:
  - `should_deploy()` 강제 False 제거 → `enabled + image + os_auth_url` 검증
  - `extra_write_files()` 5건 (webhook config, static pod manifest, tls.crt, tls.key, policy.json)
  - `generate_manifests()` 빈 문자열 반환 (Deployment/Service/RBAC 제거)
  - `server_install_args()` 에 `--kubelet-arg=pod-manifest-path=...` 추가 (Barbican과 동일, `aggregate_server_args` dedup으로 자동 처리)
  - `_get_or_create_cert` 캐싱은 그대로 유지 (extra_write_files에서도 같은 cert/key 사용)

### 20.3 단위 테스트

- [x] `backend/tests/test_k3s_plugins.py` — 게이팅 테스트 정상 분기로 재작성 + 신규 11건:
  - **Barbican (5건 + 1)**: should_deploy_when_enabled_and_kek_set, server_install_args_includes_kubelet_arg, extra_write_files_paths_and_modes, static_pod_manifest_valid_pod, generate_manifests_empty, arg_path_matches_write_file
  - **Keystone (6건)**: should_deploy_when_enabled, should_not_deploy_without_image, server_install_args_includes_kubelet_arg, extra_write_files_paths, webhook_endpoint_is_localhost, static_pod_listens_on_localhost, generate_manifests_empty
- [x] `backend/tests/test_k3s_clusters.py` — 8.14 게이팅 4건 (강제 False 검증) → 정상 분기 검증 (`should_deploy=True` when 설정 충족)으로 재작성
- [x] `_base_settings()` / `_make_plugin_settings()` 에 `os_project_name`, `os_project_domain_name`, `k3s_keystone_auth_image`, `k3s_barbican_kms_image` 보강

### 20.4 부팅 race 가정 명시

apiserver와 kubelet은 K3s 안에서 동일 `k3s server` 프로세스의 자식이라 거의 동시 시작. apiserver의 KMS provider 초기화는 **`PluginInitTimeout`(최근 K8s 기본 60초)** 동안 socket 연결 retry → kubelet이 static pod를 띄워 KMS socket 생성하는 수초~십수 초 윈도우를 흡수. 향후 K8s가 timeout을 단축하면 추가 방어(`ExecStartPre` socket-wait) 필요. Keystone webhook은 lazy 연결이라 race 부담 없음.

### 20.5 실 환경 검증 (사용자 1회)

1. `config.toml` 에 `[k3s] barbican_kms_enabled=true`, `barbican_kms_kek_id=<id>`, `keystone_auth_enabled=true` 활성화
2. 새 K3s 클러스터 생성 → 부팅 데드락 없이 ACTIVE 도달
3. `kubectl get pods -n kube-system` → barbican-kms / k8s-keystone-auth Running
4. `kubectl create secret generic test --from-literal=foo=bar` → etcd raw에서 KMS 암호화 적용 확인
5. Keystone 토큰으로 kubectl 접근 가능 (`kubectl --token=<keystone_token> get nodes`)

### 20.6 범위 외

- 기존 `manifests.yaml.j2` (DaemonSet/Deployment) 파일 GC — 호출되지 않으나 보관, 차후 정리 PR
- apiserver 인증서 갱신 시 자동 재시작 트리거 — 운영 절차로 분리
- 외부 KMS 백엔드 (Vault 등) 추상화 — Barbican 한정 유지
- 통합 테스트 자동화 — 셀프호스티드 K3s 러너 필요, 본 작업은 단위 검증 중심

