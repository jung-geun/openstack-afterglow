import { fireEvent, render } from '@testing-library/svelte';
import { expect, it } from 'vitest';
import ExecutionTimeline from '../ExecutionTimeline.svelte';

it('shows user-facing tasks while hiding backend lifecycle stages', async () => {
	const { getByLabelText, getByText, queryByText } = render(ExecutionTimeline, {
		active: true,
		items: [
			{
				id: 'stage:1',
				kind: 'stage',
				seq: 1,
				createdAt: '2026-07-26T00:00:00Z',
				stage: 'model_response',
				toolName: null
			},
			{
				id: 'reasoning:0',
				kind: 'reasoning',
				seq: 2,
				createdAt: '2026-07-26T00:00:01Z',
				text: '검색 범위를 정리합니다.',
				active: false
			},
			{
				id: 'stage:2',
				kind: 'stage',
				seq: 3,
				createdAt: '2026-07-26T00:00:02Z',
				stage: 'tool_execution',
				toolName: 'managed_web_search'
			},
			{
				id: 'tool:call-1',
				kind: 'tool',
				seq: 4,
				createdAt: '2026-07-26T00:00:03Z',
				callId: 'call-1',
				name: 'managed_web_search',
				arguments: { query: 'Afterglow' },
				status: 'completed',
				content: [{ type: 'text', text: '검색 결과' }],
				errorCode: null
			},
			{
				id: 'stage:3',
				kind: 'stage',
				seq: 5,
				createdAt: '2026-07-26T00:00:04Z',
				stage: 'response_writing',
				toolName: null
			}
		]
	});

	const timeline = getByLabelText('작업 기록');
	expect(timeline.textContent).toMatch(/추론 과정.*웹 검색/s);
	expect(queryByText('모델 응답을 처리함')).toBeNull();
	expect(queryByText('응답을 작성함')).toBeNull();
	await fireEvent.click(getByText('추론 과정'));
	expect(getByText('검색 범위를 정리합니다.')).toBeTruthy();
	await fireEvent.click(getByText('웹 검색'));
	expect(getByText('검색 결과')).toBeTruthy();
});
