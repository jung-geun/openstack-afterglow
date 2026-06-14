## 17. 인스턴스 성능 모니터링

- [x] Phase 1: Prometheus http_sd 설정 + sd_targets.py 9100/9400 분리 (node_exporter / dcgm_exporter)
- [x] Phase 2: PromQL 프록시 엔드포인트 신설 (`GET /api/instances/{id}/metrics`) + project_id 권한 검증
- [x] Phase 3: InstanceDetailPanel MetricsPanel 카드 + 4종 차트 (GPU VM: +2 차트)
- [x] Phase 4: `/metrics-batch` 단일 엔드포인트 + httpx 커넥션 풀 + `calc_step` 최적화 (다중 차트 API 호출 1→1 통합)

