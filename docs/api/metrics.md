# 메트릭 및 헬스 체크 (Metrics & Health) API

> 태그: `metrics`  
> 기본 경로: `/api/metrics`, `/api/health`

Prometheus 메트릭 수집과 서비스 헬스 체크를 제공합니다.

---

## 1. 메트릭

> 태그: `metrics`  
> 기본 경로: `/api/metrics`

### GET /api/metrics

Prometheus exposition 포맷으로 메트릭을 반환합니다. **인증이 필요하지 않습니다.** Prometheus가 이 엔드포인트를 주기적으로 스크레이핑합니다.

**응답 (200 OK)** — `text/plain` (Prometheus exposition 포맷)

```
# HELP union_http_requests_total Total HTTP requests
# TYPE union_http_requests_total counter
union_http_requests_total{method="GET",path="/api/instances",status="200"} 142.0

# HELP union_http_request_duration_ms HTTP request duration in milliseconds
# TYPE union_http_request_duration_ms histogram
union_http_request_duration_ms_bucket{method="GET",path="/api/instances",le="50.0"} 120.0
union_http_request_duration_ms_bucket{method="GET",path="/api/instances",le="100.0"} 138.0
union_http_request_duration_ms_bucket{method="GET",path="/api/instances",le="500.0"} 142.0
union_http_request_duration_ms_count{method="GET",path="/api/instances"} 142.0
union_http_request_duration_ms_sum{method="GET",path="/api/instances"} 3250.5
```

**수집 메트릭**

| 메트릭 | 타입 | 레이블 | 설명 |
|--------|------|--------|------|
| `union_http_requests_total` | Counter | `method`, `path`, `status` | 총 HTTP 요청 수 |
| `union_http_request_duration_ms` | Histogram | `method`, `path` | 요청 처리 시간 (ms) |

### Prometheus 스크레이핑 설정

```yaml
scrape_configs:
  - job_name: 'union'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /api/metrics
```

---

## 2. 헬스 체크

### GET /api/health

서비스 정상 여부를 확인합니다. **인증이 필요하지 않습니다.** 로드밸런서 헬스 체크 및 Docker Compose healthcheck에 사용합니다.

**응답 (200 OK)**

```json
{
  "status": "ok"
}
```

이 엔드포인트는 요청 로그에 기록되지 않도록 미들웨어에서 제외 처리되어 있습니다.