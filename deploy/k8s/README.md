# Union Kubernetes 배포 가이드

## 디렉토리 구조

```
k8s/
├── namespace.yaml
├── configmap.yaml
├── secret.yaml
├── ingress.yaml
├── redis/
│   ├── deployment.yaml
│   └── service.yaml
├── backend/
│   ├── deployment.yaml
│   └── service.yaml
├── frontend/
│   ├── deployment.yaml
│   └── service.yaml
└── monitoring/
    ├── prometheus/
    │   ├── configmap.yaml
    │   ├── deployment.yaml
    │   └── service.yaml
    ├── grafana/
    │   ├── deployment.yaml
    │   └── service.yaml
    └── opensearch/
        ├── statefulset.yaml
        └── service.yaml
```

## 빠른 배포 방법

### 1. 이미지 빌드

```bash
docker build -t union-backend:latest ./backend
docker build -t union-frontend:latest ./frontend
```

로컬 Kubernetes 클러스터(예: minikube)를 사용하는 경우, 이미지를 클러스터에 로드합니다.

```bash
# minikube 사용 시
minikube image load union-backend:latest
minikube image load union-frontend:latest
```

### 2. 설정 수정

배포 전 반드시 다음 값을 실제 환경에 맞게 수정하세요.

- `configmap.yaml`: OpenStack 엔드포인트, 프로젝트 설정 등
- `secret.yaml`: OpenStack 비밀번호 및 Secret Key
- `frontend/deployment.yaml`: `ORIGIN` 및 `PUBLIC_API_BASE` (실제 도메인)
- `ingress.yaml`: `host` 값 (실제 도메인)

### 3. 순서대로 배포

```bash
# 1. 네임스페이스 생성
kubectl apply -f k8s/namespace.yaml

# 2. ConfigMap 생성
kubectl apply -f k8s/configmap.yaml

# 3. Secret 생성 (파일 수정 후 적용 또는 아래 명령어 직접 사용)
kubectl apply -f k8s/secret.yaml
# 또는 kubectl로 직접 생성:
# kubectl create secret generic union-secrets \
#   --namespace=union \
#   --from-literal=OPENSTACK_PASSWORD=실제비밀번호 \
#   --from-literal=SECRET_KEY=랜덤한시크릿키

# 4. Redis 배포
kubectl apply -f k8s/redis/

# 5. Backend 배포
kubectl apply -f k8s/backend/

# 6. Frontend 배포
kubectl apply -f k8s/frontend/

# 7. Ingress 배포
kubectl apply -f k8s/ingress.yaml
```

또는 한 번에 전체 배포 (순서 보장 필요 시 위 방법 사용):

```bash
kubectl apply -f k8s/namespace.yaml && \
kubectl apply -f k8s/configmap.yaml && \
kubectl apply -f k8s/secret.yaml && \
kubectl apply -f k8s/redis/ && \
kubectl apply -f k8s/backend/ && \
kubectl apply -f k8s/frontend/ && \
kubectl apply -f k8s/ingress.yaml
```

### 4. 배포 상태 확인

```bash
kubectl get all -n union
kubectl get ingress -n union
```

## PUBLIC_API_BASE 설정 주의사항

`PUBLIC_API_BASE`는 **브라우저(클라이언트)에서 직접 접근 가능한 URL**이어야 합니다.

- Ingress를 사용하는 경우, `ORIGIN`과 동일하게 외부 도메인으로 설정합니다.
  ```
  PUBLIC_API_BASE=http://union.example.com
  ```
- 클러스터 내부 서비스 주소(예: `http://backend:8000`)로 설정하면 **브라우저에서 접근할 수 없습니다.**
- HTTPS를 사용하는 경우 `http://` 대신 `https://`를 사용하세요.
- 도메인 변경 후에는 `kubectl rollout restart deployment/frontend -n union`으로 프론트엔드를 재시작해야 합니다.

## 모니터링 선택 배포

모니터링 스택(Prometheus, Grafana, OpenSearch)은 선택적으로 배포할 수 있습니다.

```bash
# 전체 모니터링 스택 배포
kubectl apply -f k8s/monitoring/

# 개별 배포
kubectl apply -f k8s/monitoring/prometheus/
kubectl apply -f k8s/monitoring/grafana/
kubectl apply -f k8s/monitoring/opensearch/
```

### Grafana 접근

```bash
# 포트 포워딩으로 로컬 접근
kubectl port-forward svc/grafana 3001:3000 -n union
# 브라우저에서 http://localhost:3001 접속
# 기본 계정: admin / admin
```

### Prometheus 접근

```bash
kubectl port-forward svc/prometheus 9090:9090 -n union
# 브라우저에서 http://localhost:9090 접속
```

## 문제 해결

```bash
# Pod 로그 확인
kubectl logs -f deployment/backend -n union
kubectl logs -f deployment/frontend -n union

# Pod 상태 확인
kubectl describe pod -l app=backend -n union

# ConfigMap 내용 확인
kubectl get configmap union-config -n union -o yaml
```
