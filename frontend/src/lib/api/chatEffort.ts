/**
 * thinking(추론) effort 선택 — 순수 함수.
 *
 * 선택지는 하드코딩하지 않고 모델의 `reasoning_options`(models.dev 유래)에서 도출한다.
 * reasoning 은 지원하지만 effort 목록이 없으면(litellm fallback 등) 표준 low/medium/high 로 대체.
 */
import type { ModelCapabilities } from './chatTree';

const _DEFAULT_EFFORTS = ['low', 'medium', 'high'];

const _LABELS: Record<string, string> = {
	minimal: '최소',
	low: '낮음',
	medium: '중간',
	high: '높음',
	xhigh: '매우 높음',
	ultra: '울트라'
};

/** 모델이 지원하는 effort 값 목록. reasoning 미지원이면 빈 배열. */
export function effortOptionsFor(caps: ModelCapabilities | null | undefined): string[] {
	if (!caps?.reasoning) return [];
	const opt = caps.reasoning_options?.find((o) => o.type === 'effort');
	const values = opt?.values?.filter((v) => typeof v === 'string' && v.length > 0);
	return values && values.length ? values : _DEFAULT_EFFORTS;
}

/** effort 값 → 표시 라벨(한국어). 매핑 없으면 원문. */
export function effortLabel(value: string): string {
	return _LABELS[value] ?? value;
}

/**
 * 현재 effort 가 모델에서 유효한지 확인하고, 아니면 null(=서버 기본) 반환.
 * 모델을 바꾸면 이전 effort 가 새 모델에 없을 수 있으므로 정규화에 사용.
 */
export function normalizeEffort(
	effort: string | null,
	caps: ModelCapabilities | null | undefined
): string | null {
	if (!effort) return null;
	return effortOptionsFor(caps).includes(effort) ? effort : null;
}
