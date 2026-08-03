---
title: 채팅 (Chat)
parent: API 레퍼런스
nav_order: 64
---

# 채팅 (Chat) API

> 태그: `chat`
> 기본 경로: `/api/v1/chat`

기존에 운영 중인 LibreChat 인스턴스의 LLM 토큰 사용량을 **읽기 전용으로 미러링**합니다. Afterglow는 LibreChat 데이터에 쓰기를 수행하지 않으며, 현재 로그인 사용자 본인의 사용량만 노출합니다.

> **활성화 조건:** `afterglow.conf [services] chat = true` 및 LibreChat MongoDB 연동 설정.
> 비활성화 상태에서는 라우터가 등록되지 않습니다.

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `Authorization` | `Bearer <access_token>` (로그인 응답의 access JWT) |
| `X-Project-Id` | (선택) 프로젝트 UUID — 생략 시 토큰의 프로젝트로 처리, 다른 값이면 rescope |

---

## 개요

### 신원 조인

Afterglow `token_info`의 `username`(Keystone / GitLab federation 매핑)을 LibreChat username과 매칭해 사용량을 조회합니다. 두 시스템의 사용자명이 어긋나면 조회 실패로 취급합니다.

### 항상 200 반환

LibreChat가 미설정이거나 매칭되는 사용자가 없어도 `200`으로 응답하며, `found=false`로 빈 상태를 표현합니다(Grafana 대시보드 엔드포인트와 동일한 패턴 — 프론트엔드가 `found` 플래그로 빈 상태를 판단).

---

## GET /api/v1/chat/usage

로그인 사용자 본인의 LibreChat 토큰 사용량 집계를 반환합니다.

**응답 (200 OK) — 매칭 성공**

```json
{
  "found": true,
  "total_raw_amount": 12345.0,
  "total_token_value": 6789.0,
  "transaction_count": 42
}
```

**응답 (200 OK) — 미설정/미매칭**

```json
{
  "found": false,
  "total_raw_amount": 0.0,
  "total_token_value": 0.0,
  "transaction_count": 0
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `found` | boolean | 매칭되는 LibreChat 사용자를 찾았는지 여부 |
| `total_raw_amount` | float | 원시 토큰 사용량 합계 |
| `total_token_value` | float | 토큰 가치(비용 환산) 합계 |
| `transaction_count` | integer | 사용 트랜잭션 수 |
