# 외부 채팅 API (OpenAI / Anthropic 호환)

빌트인 AI 채팅을 외부 프로그램에서 **OpenAI SDK** 또는 **Anthropic(Claude) SDK**로 호출할 수 있다.
발급한 **API 키**로 인증하며, 사용량은 발급 사용자의 지갑·월 쿼터에서 차감되고 웹과 분리된 API 통계로 집계된다.

## 전용 서브도메인

외부 API는 **전용 서브도메인에서만** 열린다(기본 URL과의 충돌·오용 방지).

| 환경 | Base URL |
|------|----------|
| 프로덕션 | `https://api.cloud.dmslab.re.kr` |
| 테스트 | `https://api.test.cloud.dmslab.re.kr` |

기본 URL(`https://cloud.dmslab.re.kr`)에서는 `/v1/*` 이 노출되지 않는다(404).

> 운영: ingress/haproxy가 이 서브도메인의 `/v1` 을 백엔드로 라우팅하고, 백엔드 `[chat] api_hosts` 에
> 같은 호스트를 지정해야 한다(이중 방어). 미지정 시 앱은 모든 Host를 허용(개발).

## 인증 — API 키

1. 웹 대시보드 → 채팅 → **설정 → API 키** 에서 발급한다.
2. 발급 시 **평문 키(`sk-afgl-…`)는 한 번만** 표시된다. 안전하게 저장한다(DB엔 SHA-256 해시만 저장).
3. 요청 헤더:
   - OpenAI 형식: `Authorization: Bearer sk-afgl-…`
   - Anthropic 형식: `x-api-key: sk-afgl-…` (또는 `Authorization: Bearer …` 도 허용)

## 엔드포인트

| 형식 | 메서드 · 경로 | 설명 |
|------|--------------|------|
| Discovery | `GET /v1` | 포맷·엔드포인트·연결법 안내(키 불필요) |
| OpenAI | `POST /v1/chat/completions` | 채팅 완료(stream/non-stream, tools) |
| OpenAI | `GET /v1/models` | 사용 가능한 모델 목록(키 필요) |
| Anthropic | `POST /v1/messages` | 메시지 완료(stream/non-stream, tools) |

## 사용 가능한 모델

`GET /v1/models` 로 조회한다(관리자가 등록·활성화한 모델). 응답은 OpenAI 형식:

```json
{ "object": "list", "data": [ { "id": "<model_name>", "object": "model", "owned_by": "<provider>" } ] }
```

## 연결 예시

### OpenAI SDK (Python)

```python
from openai import OpenAI

client = OpenAI(base_url="https://api.cloud.dmslab.re.kr/v1", api_key="sk-afgl-...")

# 비스트리밍
resp = client.chat.completions.create(
    model="<model_name>",
    messages=[{"role": "user", "content": "안녕"}],
)
print(resp.choices[0].message.content)

# 스트리밍
for chunk in client.chat.completions.create(model="<model_name>", messages=[...], stream=True):
    print(chunk.choices[0].delta.content or "", end="")
```

### Anthropic SDK (Python)

```python
from anthropic import Anthropic

client = Anthropic(base_url="https://api.cloud.dmslab.re.kr", api_key="sk-afgl-...")

msg = client.messages.create(
    model="<model_name>",
    max_tokens=1024,
    messages=[{"role": "user", "content": "안녕"}],
)
print(msg.content[0].text)
```

### curl

```bash
curl https://api.cloud.dmslab.re.kr/v1/chat/completions \
  -H "Authorization: Bearer sk-afgl-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"<model_name>","messages":[{"role":"user","content":"안녕"}]}'
```

## 기능

- **스트리밍**: `stream: true` (OpenAI) / Anthropic 이벤트 스트림.
- **도구 호출(function calling)**: 요청의 `tools` 를 모델에 그대로 전달하고, 모델이 반환한 `tool_calls`(OpenAI) /
  `tool_use`(Anthropic)를 **클라이언트가 실행**한 뒤 결과를 다음 요청에 넣어 이어간다(표준 pass-through).
- **이미지 입력(vision)**: vision 지원 모델에서 멀티모달 메시지 입력.

## 과금·사용량

- API 사용량은 **웹과 동일한 지갑·월 쿼터**에서 차감된다(키별 별도 한도 없음).
- 통계는 **접근 경로(web/api)·API 키별·시간(시/일/월)** 으로 분리 집계된다. 웹 대시보드 → 설정 → 사용량에서 확인.
- 월 쿼터를 초과하면 `429` 를 반환한다.

## 제한

- 응답 `max_tokens` 상한은 서버 정책(기본 4096)을 따른다.
- 키가 폐기되면 즉시 `401`.
