/**
 * 채팅 스트리밍 생성 속도(tok/s) 측정 — 순수 함수.
 *
 * 속도는 런타임 계측값이라 서버에 저장하지 않는다. 프론트가 첫 토큰 도착부터
 * done 까지의 wall-clock 을 재고, done 이 주는 정확한 completion_tokens 로 tok/s 를 낸다.
 * 스트리밍 중 라이브 표시는 수신 문자 수 기반 근사(정확한 per-delta 토큰 수는 클라에 없음).
 *
 * UI 위험 로직이라 순수 함수로 격리해 단위 테스트한다.
 */

export interface StreamMetrics {
	/** 생성된 completion 토큰 수(정확: done, 라이브: 근사) */
	tokens: number;
	/** 첫 토큰~완료 경과 시간(초) */
	seconds: number;
	/** 초당 토큰(tokens/seconds). 시간 0 이면 0. */
	tokPerSec: number;
	/** true 면 라이브 근사치(문자 기반), false 면 done 확정치 */
	approximate: boolean;
}

/** 문자 수 → 대략 토큰 수(4 chars ≈ 1 token). 라이브 근사에만 사용. */
export function estimateTokens(chars: number): number {
	if (chars <= 0) return 0;
	return Math.max(1, Math.round(chars / 4));
}

/**
 * tok/s 계산. firstTokenMs/doneMs 는 performance.now() 기준 ms.
 * elapsed 가 0 이하이거나 tokens 가 0 이면 tokPerSec=0(0 나눗셈 방지).
 */
export function computeMetrics(
	tokens: number,
	firstTokenMs: number | null,
	nowMs: number,
	approximate: boolean
): StreamMetrics | null {
	if (firstTokenMs === null) return null;
	const seconds = Math.max(0, (nowMs - firstTokenMs) / 1000);
	const tok = Math.max(0, tokens);
	const tokPerSec = seconds > 0 && tok > 0 ? tok / seconds : 0;
	return { tokens: tok, seconds, tokPerSec, approximate };
}

/**
 * 표시 문자열. 예: "12.4 tok/s · 340 tok · 2.1s". 라이브 근사면 "~" 접두.
 * tokens 나 속도가 0 이면 해당 항목을 생략해 노이즈를 줄인다.
 */
export function formatMetrics(m: StreamMetrics | null): string {
	if (!m) return '';
	const parts: string[] = [];
	if (m.tokPerSec > 0) {
		const rate = m.tokPerSec >= 100 ? Math.round(m.tokPerSec).toString() : m.tokPerSec.toFixed(1);
		parts.push(`${m.approximate ? '~' : ''}${rate} tok/s`);
	}
	if (m.tokens > 0) parts.push(`${m.tokens} tok`);
	if (m.seconds > 0) parts.push(`${m.seconds.toFixed(1)}s`);
	return parts.join(' · ');
}
