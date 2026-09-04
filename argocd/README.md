# ArgoCD 자동 배포 설정

버전 변경 시 자동 배포를 위한 ArgoCD Application 설정입니다.

## 파일 구조

```
argocd/
  00-namespace.yaml              # argocd 네임스페이스
  01-appproject.yaml             # AppProject (권한 범위)
  03-ingress.yaml                # ArgoCD UI Ingress
  04-server-config.yaml          # ArgoCD server 설정 (insecure, URL 등)
  image-updater/
    install.yaml                 # Image Updater 공식 매니페스트 v1.1.1 + log.level=info
    imageupdater-prod.yaml       # ImageUpdater CR — prod app annotation 감시
```

Application 매니페스트는 `argocd/generate_helm_application.py`가
`deploy/k8s/argocd-application-{dev,prod}.yaml`로 생성합니다. 이 파일은 Secret 값을
포함하므로 git에 커밋하지 않습니다. `argocd/02-application.*.yaml` 형태의
Kustomize Application은 제거했으며, Helm Application만 사용합니다.

## 배포 흐름

```
helm/afterglow 차트 또는 이미지 변경
  → ArgoCD Helm Application 자동 sync
  → 새 Pod 롤아웃

환경별 설정 변경
  → helm/afterglow/values-<env>.yaml 또는 secrets-<env>.yaml 수정
  → generate_helm_application.py 실행
  → 생성된 Helm Application CR 적용

관리자 ConfigMap/Secret 변경
  → generate_k8s.py가 환경 프로필과 함께 매니페스트 생성
  → kubectl apply
  → ArgoCD ignoreDifferences가 직접 적용한 data를 보존
```

---

## 최초 설치 순서

### 1. ArgoCD 설치

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### 2. ArgoCD Image Updater 설치 (선언적, 파일로 직접)

두 단계로 나눠 적용합니다. CRD 가 등록된 뒤에 ImageUpdater CR 을 생성해야 합니다.

```bash
# Step 1: CRD + RBAC + Deployment + ConfigMap (log.level=info 포함)
kubectl apply -f argocd/image-updater/install.yaml

# Step 2: ImageUpdater CR — CRD 등록 완료 후 적용
kubectl apply -f argocd/image-updater/imageupdater-prod.yaml
```

- `install.yaml` — CRD, RBAC, Deployment, ConfigMap 일괄 포함 (v1.1.1, log.level=info 내장)
- `imageupdater-prod.yaml` — ImageUpdater CR: afterglow-prod 앱의 annotation 읽어 digest 감시

업그레이드 시 `argocd/image-updater/install.yaml` 을 새 버전으로 교체 후 재적용.

### 3. GHCR pull-secret 생성 (필수 — private 패키지)

Image Updater 가 GHCR 이미지 digest 를 polling 하려면 인증이 필요합니다.
`argocd` 네임스페이스에 secret 을 생성하고, Application annotation 에 선언된
`pullsecret:argocd/ghcr-secret` 과 이름을 맞춥니다.

```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=openstack-afterglow \
  --docker-password=<GITHUB_PAT_READ_PACKAGES> \
  -n argocd
```

> 생성된 Helm Application의 Image Updater annotation이 이 secret을 가리킵니다.
> secret이 없으면 Image Updater가 401로 실패합니다.

### 4. GitHub 레포 등록

```bash
argocd repo add https://github.com/openstack-afterglow/openstack-afterglow.git \
  --username openstack-afterglow \
  --password <GITHUB_PAT>
```

### 5. ArgoCD 리소스 적용

```bash
# 네임스페이스와 AppProject 먼저 적용
kubectl apply -f argocd/00-namespace.yaml
kubectl apply -f argocd/01-appproject.yaml
kubectl apply -f argocd/03-ingress.yaml
kubectl apply -f argocd/04-server-config.yaml

# Helm Application 생성 및 적용 — dev/prod 모두 같은 경로 사용
backend/.venv/bin/python argocd/generate_helm_application.py dev
KUBECONFIG=/Users/pieroot/code/afterglow/deploy/k8s/kubeconfig \
  kubectl apply -f deploy/k8s/argocd-application-dev.yaml

backend/.venv/bin/python argocd/generate_helm_application.py prod
KUBECONFIG=/Users/pieroot/code/afterglow/deploy/k8s/kubeconfig \
  kubectl apply -f deploy/k8s/argocd-application-prod.yaml

# 최초 수동 sync (이후 자동)
argocd app sync afterglow-dev
argocd app sync afterglow-prod
```

---

## 동작 방식

### prod 환경
- ArgoCD가 `main` 브랜치의 `helm/afterglow` 차트를 추적.
- `afterglow-prod` Application은 `targetRevision: main`과 Helm valuesObject를 사용.
- Image Updater가 `:latest` digest 변경을 감지하면 Application을 patch하고 새 Pod를 롤아웃.

### dev 환경
- ArgoCD가 `dev` 브랜치의 `helm/afterglow` 차트를 추적.
- `afterglow-dev` Application은 `targetRevision: dev`와 Helm valuesObject를 사용.
- 이미지 digest 변경과 차트 변경을 ArgoCD가 자동 sync한다.

### 생성기 규칙
- `generate_helm_application.py`가 유일한 Application 생성 경로다.
- 생성된 Application에는 Helm source, `selfHeal`, Image Updater annotation,
  ConfigMap/Secret `ignoreDifferences`가 함께 들어간다.
- 삭제된 `argocd/02-application.*.yaml`을 다시 만들거나 적용하지 않는다.

### 관리자 ConfigMap/Secret 직접 반영

`afterglow-config`와 `afterglow-secrets`는 Helm이 최초 생성하지만, 두 리소스의
`data`는 관리자 운영 영역으로 지정되어 ArgoCD `ignoreDifferences`에 등록됩니다.
따라서 `selfHeal: true`를 유지하면서도 관리자가 직접 적용한 값은 자동 복구되지
않습니다. 이 설정은 `generate_helm_application.py`로 Application을 다시 생성하여
클러스터에 적용해야 활성화됩니다.

```bash
ENV=dev
NAMESPACE=afterglow-dev
OUT_DIR=/tmp/afterglow-k8s-$ENV
KUBECONFIG=/Users/pieroot/code/afterglow/deploy/k8s/kubeconfig

# 최초 1회 또는 ArgoCD Application 정책 변경 시
backend/.venv/bin/python argocd/generate_helm_application.py "$ENV"
KUBECONFIG="$KUBECONFIG" kubectl apply \
  -f "deploy/k8s/argocd-application-$ENV.yaml"

# dev는 반드시 환경별 URL 오버라이드를 함께 적용한다.
python3 generate_k8s.py \
  --config afterglow.conf \
  --override deploy/afterglow-dev.conf \
  --namespace "$NAMESPACE" \
  --output-dir "$OUT_DIR"
KUBECONFIG="$KUBECONFIG" kubectl apply -f "$OUT_DIR/secret.yaml"
KUBECONFIG="$KUBECONFIG" kubectl apply -f "$OUT_DIR/configmap.yaml"

# afterglow.conf는 subPath 마운트이고 Secret 값은 환경변수이므로 Pod 재시작 필요
KUBECONFIG="$KUBECONFIG" kubectl -n "$NAMESPACE" rollout restart deployment \
  backend frontend drover notion-worker
KUBECONFIG="$KUBECONFIG" kubectl -n "$NAMESPACE" rollout status deployment/backend
```
`--namespace`는 환경 프로필을 필수로 선택합니다. `afterglow-dev`는
`deploy/afterglow-dev.conf`, `afterglow`는 `deploy/afterglow-prod.conf`를
자동으로 먼저 적용합니다. dev를 prod `afterglow.conf`로 생성하면
`https://cloud.dmslab.re.kr`이 들어갈 수 있으므로 dev 명령에서 환경 프로필을
생략하면 안 됩니다.
`afterglow-config`/`afterglow-secrets`를 Helm values로 바꿀 때는 `ignoreDifferences`
때문에 해당 values 변경만으로는 리소스 데이터가 갱신되지 않으므로, 위의 직접 적용
절차를 사용합니다. 데이터 전체를 무시하므로 키를 삭제하거나 잘못된 값을 넣었을 때의
검증과 롤백은 관리자가 담당해야 합니다.

---

## Image Updater 상태 확인

```bash
# pod 상태
kubectl -n argocd get pods -l app.kubernetes.io/name=argocd-image-updater

# 로그 (afterglow 관련 + 에러)
kubectl -n argocd logs deploy/argocd-image-updater-controller --tail=200 | \
  grep -Ei 'afterglow|error|warn|unauthorized'

# ImageUpdater CR 상태
kubectl -n argocd get imageupdater afterglow-prod -o yaml

# prod Application in-cluster image override 확인
kubectl -n argocd get app afterglow-prod \
  -o jsonpath='{.spec.source.kustomize.images}' && echo
```
