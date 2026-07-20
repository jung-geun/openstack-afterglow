/**
 * 채팅 답변 출처(citations) — 표시/집계 순수 함수.
 *
 * 백엔드가 최종 assistant 메시지에 `[{url, title?, snippet?}]` 형태로 저장/스트리밍한다.
 * 메시지 하단 출처 리스트와 "대화 전체 출처" 패널이 이 유틸을 공유한다.
 */

export interface Citation {
	url: string;
	title?: string | null;
	snippet?: string | null;
}

/** URL 에서 표시용 도메인(호스트, www 제거) 추출. 파싱 실패 시 원문 앞부분. */
export function citationDomain(url: string): string {
	try {
		const host = new URL(url).hostname;
		return host.replace(/^www\./, '');
	} catch {
		return url.replace(/^https?:\/\//, '').split('/')[0] || url;
	}
}

/** 출처의 표시 라벨 — title 우선, 없으면 도메인. */
export function citationLabel(c: Citation): string {
	const title = c.title?.trim();
	return title || citationDomain(c.url);
}

/** http/https URL 만 허용(javascript:·data: 등 스킴 클릭 실행 방어). */
function isSafeHttpUrl(url: string): boolean {
	try {
		const u = new URL(url);
		return u.protocol === 'http:' || u.protocol === 'https:';
	} catch {
		return false;
	}
}

/** unknown(저장/스트림) → Citation[] 방어적 정규화. http/https url 있는 항목만. */
export function normalizeCitations(value: unknown): Citation[] {
	if (!Array.isArray(value)) return [];
	const out: Citation[] = [];
	for (const raw of value) {
		if (!raw || typeof raw !== 'object') continue;
		const c = raw as Record<string, unknown>;
		// url 은 provider grounding/모델 annotations 유래 — 스킴을 반드시 검증한다(XSS 방어).
		if (typeof c.url === 'string' && isSafeHttpUrl(c.url)) {
			out.push({
				url: c.url,
				title: typeof c.title === 'string' ? c.title : null,
				snippet: typeof c.snippet === 'string' ? c.snippet : null
			});
		}
	}
	return out;
}

/**
 * 여러 메시지의 출처를 url 기준 중복 제거해 하나의 목록으로 집계(등장 순서 보존).
 * 더 풍부한 항목(title/snippet 보유)으로 업그레이드한다. "대화 전체 출처" 패널용.
 */
export function aggregateCitations(messages: { citations?: unknown }[]): Citation[] {
	const byUrl = new Map<string, Citation>();
	for (const m of messages) {
		for (const c of normalizeCitations(m.citations)) {
			const existing = byUrl.get(c.url);
			if (!existing) {
				byUrl.set(c.url, c);
			} else {
				if (!existing.title && c.title) existing.title = c.title;
				if (!existing.snippet && c.snippet) existing.snippet = c.snippet;
			}
		}
	}
	return [...byUrl.values()];
}
