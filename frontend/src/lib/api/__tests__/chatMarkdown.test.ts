import { describe, expect, it } from 'vitest';
import { renderMarkdown } from '../chatMarkdown';

describe('renderMarkdown', () => {
	it('마크다운 강조를 렌더한다', () => {
		const html = renderMarkdown('**굵게** _기울임_');
		expect(html).toContain('<strong>굵게</strong>');
		expect(html).toContain('<em>기울임</em>');
	});

	it('<script> 를 제거한다 (XSS 방어)', () => {
		const html = renderMarkdown('안녕<script>alert(1)</script>');
		expect(html).not.toContain('<script');
		expect(html).toContain('안녕');
	});

	it('javascript: 링크를 제거한다', () => {
		const html = renderMarkdown('[클릭](javascript:alert(1))');
		expect(html).not.toContain('javascript:');
	});

	it('onerror 등 이벤트 핸들러 속성을 제거한다', () => {
		const html = renderMarkdown('<img src=x onerror=alert(1)>');
		expect(html).not.toContain('onerror');
	});

	it('코드 블록을 language 클래스와 함께 pre>code 로 렌더한다', () => {
		const html = renderMarkdown('```js\nconst a = 1;\n```');
		expect(html).toContain('<pre>');
		expect(html).toContain('<code');
		expect(html).toContain('language-js');
	});
});
