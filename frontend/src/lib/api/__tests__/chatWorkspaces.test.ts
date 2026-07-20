import { describe, expect, it } from 'vitest';
import {
	buildWorkspacePayload,
	emptyWorkspaceForm,
	workspaceToForm,
	type Workspace
} from '../chatWorkspaces';

describe('emptyWorkspaceForm', () => {
	it('모든 필드가 빈 문자열', () => {
		expect(emptyWorkspaceForm()).toEqual({ name: '', description: '', instructions: '' });
	});
});

describe('buildWorkspacePayload', () => {
	it('name 만 있으면 name 만(공백 trim)', () => {
		expect(buildWorkspacePayload({ ...emptyWorkspaceForm(), name: '  내 프로젝트  ' })).toEqual({
			name: '내 프로젝트'
		});
	});

	it('빈 description/instructions 는 생략', () => {
		const form = { name: 'p', description: '   ', instructions: '' };
		expect(buildWorkspacePayload(form)).toEqual({ name: 'p' });
	});

	it('description/instructions 있으면 trim 후 포함', () => {
		const form = {
			name: ' 리서치 ',
			description: ' 검색 관련 대화 ',
			instructions: ' 항상 출처를 밝혀라 '
		};
		expect(buildWorkspacePayload(form)).toEqual({
			name: '리서치',
			description: '검색 관련 대화',
			instructions: '항상 출처를 밝혀라'
		});
	});
});

describe('workspaceToForm', () => {
	const base: Workspace = {
		id: 1,
		name: '마케팅',
		description: '마케팅 캠페인',
		instructions: '브랜드 톤을 유지하라'
	};

	it('편집 진입 왕복: form → payload 가 원본과 일치', () => {
		const form = workspaceToForm(base);
		expect(form).toEqual({
			name: '마케팅',
			description: '마케팅 캠페인',
			instructions: '브랜드 톤을 유지하라'
		});
		expect(buildWorkspacePayload(form)).toEqual({
			name: '마케팅',
			description: '마케팅 캠페인',
			instructions: '브랜드 톤을 유지하라'
		});
	});

	it('description/instructions null 이면 빈 문자열', () => {
		const form = workspaceToForm({ ...base, description: null, instructions: null });
		expect(form.description).toBe('');
		expect(form.instructions).toBe('');
	});
});
