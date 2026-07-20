import { describe, expect, it } from 'vitest';
import { effortLabel, effortOptionsFor, normalizeEffort } from '../chatEffort';

describe('effortOptionsFor', () => {
	it('reasoning 미지원이면 빈 배열', () => {
		expect(effortOptionsFor({ reasoning: false })).toEqual([]);
		expect(effortOptionsFor(null)).toEqual([]);
		expect(effortOptionsFor(undefined)).toEqual([]);
	});
	it('reasoning_options 의 effort values 를 그대로 사용', () => {
		expect(
			effortOptionsFor({
				reasoning: true,
				reasoning_options: [{ type: 'effort', values: ['low', 'high'] }]
			})
		).toEqual(['low', 'high']);
	});
	it('reasoning 지원하지만 effort 목록 없으면 표준 low/medium/high', () => {
		expect(effortOptionsFor({ reasoning: true })).toEqual(['low', 'medium', 'high']);
		expect(effortOptionsFor({ reasoning: true, reasoning_options: [] })).toEqual([
			'low',
			'medium',
			'high'
		]);
	});
});

describe('effortLabel', () => {
	it('한국어 라벨 매핑', () => {
		expect(effortLabel('low')).toBe('낮음');
		expect(effortLabel('high')).toBe('높음');
		expect(effortLabel('minimal')).toBe('최소');
	});
	it('매핑 없으면 원문', () => {
		expect(effortLabel('weird')).toBe('weird');
	});
});

describe('normalizeEffort', () => {
	const caps = { reasoning: true, reasoning_options: [{ type: 'effort', values: ['low', 'high'] }] };
	it('유효 effort 는 유지', () => {
		expect(normalizeEffort('high', caps)).toBe('high');
	});
	it('모델에 없는 effort 는 null(서버 기본)', () => {
		expect(normalizeEffort('medium', caps)).toBeNull();
	});
	it('null/빈값은 null', () => {
		expect(normalizeEffort(null, caps)).toBeNull();
		expect(normalizeEffort('', caps)).toBeNull();
	});
});
