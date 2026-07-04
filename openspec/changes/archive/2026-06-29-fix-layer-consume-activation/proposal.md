## Why
레이어 소비 VM은 fstab까지만 생성되고 첫 부팅 중 NFS, SquashFS, OverlayFS 활성화가 실행되지 않는다. 수동 mount -av 후에는 레이어 데이터가 보이므로 빌드보다 소비 VM 활성화 경로를 수정해야 한다.

## What Changes
- consume cloud-init이 layer-activate.service를 enable뿐 아니라 첫 부팅에서 start한다
- layer-activate.sh가 fstab 기반 NFS mountpoint를 retry mount한 뒤 SquashFS를 마운트한다
- /usr overlay target에서 SquashFS root가 아니라 각 레이어의 usr 하위 디렉터리를 lowerdir로 사용한다
- 회귀 테스트로 service start, NFS mount retry, /usr lowerdir 매핑을 고정한다

## Impact
backend/app/services/layer_build.py, backend/tests/test_layer_consume.py, layers/vm/layer-activate.sh. 레이어 빌드 API와 LayerArtifact 생성 경로는 변경하지 않는다.
