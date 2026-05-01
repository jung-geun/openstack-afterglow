# ArgoCD 자동 배포 설정

버전 변경 시 자동 배포를 위한 ArgoCD Application 설정입니다.

## 파일 구조

```
argocd/
  00-namespace.yaml              # argocd 네임스페이스
  01-appproject.yaml             # AppProject (권한 범위)
  02-application.dev.yaml        # dev Application (dev 브랜치 추적, CI digest 갱신)
  02-application.prod.yaml       # prod Application (main 브랜치 추적, Image Updater 감지)
  03-ingress.yaml                # ArgoCD UI Ingress
  04-server-config.yaml          # ArgoCD server 설정 (insecure, URL 등)
  image-updater/
    install.yaml                 # Image Updater 공식 매니페스트 (v1.1.1)
    kustomization.yaml           # Kustomize overlay (log level 패치)
    config-patch.yaml            # ConfigMap 패치 (log.level=info)
    imageupdater-prod.yaml       # ImageUpdater CR — prod app 감시 (useAnnotations)
```

## 배포 흐름

```
git tag v1.x.x && git push origin main --tags
  → GitHub Actions: ghcr.io/jung-geun/afterglow-api:{vX.Y.Z, latest} 빌드/푸시
  → ArgoCD: prod kustomization.yaml 의 newTag 변경 감지 → auto-sync → 새 Pod 롤아웃
  → Image Updater: :latest digest 변경 감지 → 다음 릴리즈부터 자동 재배포

dev 푸시
  → GitHub Actions update-manifests: kustomization.yaml digest 갱신 커밋
  → ArgoCD: dev digest 변경 감지 → auto-sync → 새 Pod 롤아웃
```

---

## 최초 설치 순서

### 1. ArgoCD 설치

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### 2. ArgoCD Image Updater 설치 (선언적, 파일로 직접)

```bash
# 리포지터리 루트에서 실행
kubectl apply -k argocd/image-updater/
```

- `install.yaml` — CRD + RBAC + Deployment 등 공식 매니페스트 (v1.1.1)
- `config-patch.yaml` — ConfigMap 패치: log.level=info
- `imageupdater-prod.yaml` — ImageUpdater CR: afterglow-prod 앱의 annotation 읽어 digest 감시

업그레이드 시 `argocd/image-updater/install.yaml` 을 새 버전으로 교체 후 재적용.

### 3. GHCR pull-secret 생성 (필수 — private 패키지)

Image Updater 가 GHCR 이미지 digest 를 polling 하려면 인증이 필요합니다.
`argocd` 네임스페이스에 secret 을 생성하고, Application annotation 에 선언된
`pullsecret:argocd/ghcr-secret` 과 이름을 맞춥니다.

```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=jung-geun \
  --docker-password=<GITHUB_PAT_READ_PACKAGES> \
  -n argocd
```

> `02-application.prod.yaml` 의 `backend.pull-secret` / `frontend.pull-secret` annotation 이
> 이 secret 을 가리킵니다. secret 이 없으면 Image Updater 가 401 로 실패합니다.

### 4. GitHub 레포 등록

```bash
argocd repo add https://github.com/jung-geun/openstack-afterglow.git \
  --username jung-geun \
  --password <GITHUB_PAT>
```

### 5. ArgoCD 리소스 적용

```bash
# 네임스페이스 → AppProject → Application 순서로 적용
kubectl apply -f argocd/00-namespace.yaml
kubectl apply -f argocd/01-appproject.yaml
kubectl apply -f argocd/02-application.dev.yaml
kubectl apply -f argocd/02-application.prod.yaml
kubectl apply -f argocd/03-ingress.yaml
kubectl apply -f argocd/04-server-config.yaml

# 최초 수동 sync (이후 자동)
argocd app sync afterglow-dev
argocd app sync afterglow-prod
```

---

## 동작 방식

### prod 환경
- ArgoCD 가 `main` 브랜치의 `deploy/k8s-template/overlays/prod/kustomization.yaml` 을 추적.
- 새 릴리즈 시 `newTag` 를 업데이트하는 PR → main 머지 → ArgoCD git-diff 감지 → auto-sync.
- Image Updater 가 `:latest` digest 변경을 감지하면 ArgoCD Application 을 in-cluster patch → 롤아웃.

### dev 환경
- CI `update-manifests` job 이 dev 빌드마다 `kustomization.yaml` 의 `digest` 필드를 갱신 커밋.
- ArgoCD 가 git-diff 를 감지하여 auto-sync.

### Image Updater CR (`imageupdater-prod.yaml`)
- `useAnnotations: true` — prod Application 의 `argocd-image-updater.argoproj.io/*` annotation 을 읽어 설정.
- 별도 이미지 목록 설정 없이 Application annotation 으로 update-strategy/pull-secret 관리.

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
