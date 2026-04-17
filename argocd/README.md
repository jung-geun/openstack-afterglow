# ArgoCD 자동 배포 설정

버전 변경 시 자동 배포를 위한 ArgoCD Application 설정입니다.

## 파일 구조

```
argocd/
  appproject.yaml   # ArgoCD AppProject (권한 범위 설정)
  application.yaml  # ArgoCD Application (배포 대상 및 동기화 정책)
```

## 배포 흐름

```
npm run version:bump:patch
  → git tag v1.x.x 생성
  → git push origin main --tags
  → GitHub Actions: ghcr.io/jung-geun/afterglow-api:latest 및 :vX.Y.Z 푸시
  → ArgoCD Image Updater: :latest digest 변경 감지 (약 2분 내)
  → ArgoCD 자동 sync → 새 Pod 롤아웃
```

## 사전 요구사항

### 1. ArgoCD 설치

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### 2. ArgoCD Image Updater 설치

```bash
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj-labs/argocd-image-updater/stable/manifests/install.yaml
```

### 3. GitHub 레포 등록

```bash
argocd repo add https://github.com/jung-geun/openstack-afterglow.git \
  --username jung-geun \
  --password <GITHUB_PAT>
```

> Image Updater의 `write-back-method: git` 사용 시 **쓰기 권한**이 있는 토큰/키가 필요합니다.

### 4. ghcr.io 레지스트리 설정 (private 패키지인 경우)

```bash
# GitHub Container Registry용 pull secret
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=jung-geun \
  --docker-password=<GITHUB_PAT> \
  -n argocd
```

그 후 `application.yaml`의 annotation에 추가:
```yaml
argocd-image-updater.argoproj.io/pull-secret: pullsecret:argocd/ghcr-secret
```

## 적용 방법

```bash
# 1. AppProject 먼저 적용
kubectl apply -f argocd/appproject.yaml

# 2. Application 적용
kubectl apply -f argocd/application.yaml

# 3. 상태 확인
argocd app get afterglow
argocd app sync afterglow  # 최초 수동 동기화 (이후 자동)
```

## Test 환경 사용

동일한 `application.yaml`을 test 환경에서도 사용하려면 `targetRevision`과 `path`만 변경:

```yaml
source:
  targetRevision: dev   # dev 브랜치 추적
  path: k8s-test        # test 매니페스트 사용
```

또는 별도 Application 리소스로 분리하여 두 환경을 동시에 관리할 수 있습니다.

## 동작 방식

- **Image Updater `digest` 전략**: `:latest` 태그가 가리키는 이미지 digest가 바뀌면 새 배포 트리거. semver 태그 없이 mutable tag만 사용해도 자동 감지 가능.
- **`write-back-method: git`**: Image Updater가 `.argocd-source-afterglow.yaml` 파일을 git에 커밋하여 변경 이력 유지.
- **`selfHeal: true`**: 클러스터 리소스가 git 상태와 달라지면 자동으로 되돌림.
- **`prune: true`**: git에서 삭제된 매니페스트는 클러스터에서도 삭제.
- **Secret 제외**: `ignoreDifferences`로 Secret data는 ArgoCD가 관리하지 않음 (수동 또는 외부 시크릿 매니저로 관리).
