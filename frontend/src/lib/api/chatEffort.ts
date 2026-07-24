/**
 * thinking(추론) effort 선택 — 순수 함수.
 *
 * 선택지는 모델의 `reasoning_options`(models.dev 유래)에서만 도출한다.
 * options가 toggle뿐이거나 미확인인 모델은 provider 기본(auto)과 명시적 해제(none)만 노출한다.
 */
import type { ModelCapabilities } from './chatContracts';

const _SUPPORTED_NAMED_EFFORTS = new Set(['minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra']);
const _LABELS: Record<string, string> = {
	auto: '자동',
	none: '없음',
	minimal: '최소',
	low: '낮음',
	medium: '중간',
	high: '높음',
	xhigh: '매우 높음',
	max: '최대',
	ultra: '울트라'
};

/** 모델별 선택지. auto 는 provider 기본, none 은 명시적인 추론 비활성화다. */
export function effortOptionsFor(caps: ModelCapabilities | null | undefined): string[] {
	if (!caps?.reasoning) return [];
	const opt = caps.reasoning_options?.find((o) => o.type === 'effort');
	const values =
		opt?.values?.filter(
			(value) => typeof value === 'string' && _SUPPORTED_NAMED_EFFORTS.has(value)
		) ?? [];
	return ['auto', 'none', ...values];
}

/** effort 값 → 표시 라벨(한국어). 매핑 없으면 원문. */
export function effortLabel(value: string): string {
	return _LABELS[value] ?? value;
}

/**
 * 현재 effort가 모델에서 유효한지 확인하고, 아니면 auto(=provider 기본) 반환.
 * 모델을 바꾸면 이전 effort가 새 모델에 없을 수 있으므로 정규화에 사용.
 */
export function normalizeEffort(
	effort: string | null,
	caps: ModelCapabilities | null | undefined
): string {
	const selected = effort ?? 'auto';
	return effortOptionsFor(caps).includes(selected) ? selected : 'auto';
}
