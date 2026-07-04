# squashfs 레이어 빌드/소비 관리자 버튼 + 모니터링

## 목표
NFS Manila에 수동으로 검증한 squashfs+OverlayFS 레이어 파이프라인을 관리자 버튼으로 실행하고 모니터링할 수 있게 한다.

## 완료 기준
- [x] 백엔드: LayerBuild / LayerConsume DB 모델 추가 (db.py)
- [x] 백엔드: squashfs_python_layer() 빌드 스크립트 블록 추가 (recipe_blocks.py)
- [x] 백엔드: run_layer_build / run_layer_consume 오케스트레이션 (services/layer_build.py)
- [x] 백엔드: asyncio 백그라운드 태스크 관리자 (services/layer_builder.py)
- [x] 백엔드: FastAPI 라우터 /api/v1/admin/layers (api/union/layer_ops.py)
- [x] 백엔드: main.py 라우터 등록 (/api/v1/admin/layers)
- [x] 프론트엔드: /admin/layers 페이지 — 빌드 폼 + 소비 폼 + 모니터링 테이블 + 상세 모달
- [x] 프론트엔드: nav.ts에 squashfs 레이어 메뉴 추가
- [x] 테스트: test_layer_ops.py 43건 (Pydantic 검증 + 인가 + API 흐름)
- [x] 문서화: docs/squashfs-layer-pipeline.md 신규 + layers/README.md 갱신
- [x] lint:backend + test:backend 전체 통과
