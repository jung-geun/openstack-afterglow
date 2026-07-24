import { describe, expect, it } from 'vitest';
import { renderMarkdown } from '../chatMarkdown';
import { renderMath, renderMermaidBlocks } from '../chatRichOutput';

describe('chat rich output', () => {
	it('renders display and inline LaTeX but leaves fenced source untouched', async () => {
		const host = document.createElement('div');
		host.innerHTML = renderMarkdown('Inline $x^2$ and \\(a+b\\).\n\n$$\\text{build} \\rightarrow \\text{review}$$\n\n$$\n\\frac{1}{2}\n$$\n\n\\[\n\\sqrt{x}\n\\]\n\n```\n$$\ndo not parse\n$$\n```');

		await renderMath(host);

		expect(host.querySelectorAll('.katex')).toHaveLength(5);
		expect(host.querySelectorAll('.math-display')).toHaveLength(3);
		expect(host.querySelector('[data-chat-math]')).toBeNull();
		expect(host.querySelector('pre code')?.textContent).toBe('$$\ndo not parse\n$$\n');
	});

	it('parses bold emphasis even when Korean text immediately follows its closing delimiter', () => {
		const host = document.createElement('div');
		host.innerHTML = renderMarkdown('**굵은 제목**뒤따르는 본문');

		expect(host.querySelector('strong')?.textContent).toBe('굵은 제목');
		expect(host.textContent?.trim()).toBe('굵은 제목뒤따르는 본문');
	});

	it('parses bold text ending in punctuation before adjacent Korean text', () => {
		const host = document.createElement('div');
		host.innerHTML = renderMarkdown('**CLA (Individual Contributor License Agreement):**에 전자 서명합니다.');

		expect(host.querySelector('strong')?.textContent).toBe('CLA (Individual Contributor License Agreement):');
	});

	it('does not merge ordinary bold spans before a punctuation-adjacent label', () => {
		const host = document.createElement('div');
		host.innerHTML = renderMarkdown('**첫째** / **레이블:**뒤 본문');

		expect(Array.from(host.querySelectorAll('strong'), (node) => node.textContent)).toEqual(['첫째', '레이블:']);
	});

	it('keeps Mermaid source readable when the renderer cannot execute', async () => {
		const host = document.createElement('div');
		host.innerHTML = '<pre><code class="language-mermaid">flowchart LR\nA[Start] --&gt; B[Finish]</code></pre>';

		await renderMermaidBlocks(host);

		expect(host.querySelector('pre[data-mermaid-error] code')?.textContent).toContain('flowchart LR');
	});
});
