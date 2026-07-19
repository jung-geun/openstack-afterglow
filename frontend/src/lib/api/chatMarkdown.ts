/**
 * 채팅 마크다운 렌더링 + 코드 하이라이트.
 *
 * - marked 로 마크다운 → HTML, DOMPurify.sanitize 로 XSS 방어(<script> 등 제거).
 * - shiki 는 무거우므로 동적 import 로 지연 로딩하고, 스트리밍 중에는 호출하지 않는다
 *   (델타마다 재하이라이트하면 버벅임). 스트리밍 완료 후 한 번만 코드블록을 하이라이트한다.
 * - shiki 출력은 자체적으로 코드 텍스트를 HTML escape 하므로(XSS 안전) DOMPurify 를
 *   거치지 않고 삽입한다. 이렇게 해야 dual-theme 용 CSS 커스텀 프로퍼티가 제거되지 않는다.
 */
import { marked } from 'marked';
import DOMPurify from 'dompurify';

marked.setOptions({ breaks: true, gfm: true });

/**
 * 마크다운을 살균된 HTML 로 변환한다. 코드블록은 아직 하이라이트하지 않은
 * plain <pre><code class="language-xxx"> 형태(스트리밍 중에도 안전하게 즉시 렌더).
 */
export function renderMarkdown(source: string): string {
	const raw = marked.parse(source ?? '', { async: false }) as string;
	return DOMPurify.sanitize(raw, {
		ADD_ATTR: ['target', 'rel'],
		FORBID_TAGS: ['style', 'form', 'input', 'button'],
		FORBID_ATTR: ['onerror', 'onload', 'onclick']
	});
}

type CodeToHtml = (code: string, options: Record<string, unknown>) => Promise<string>;

let codeToHtmlPromise: Promise<CodeToHtml> | null = null;

/** shiki 를 지연 로딩해 codeToHtml 를 반환(모듈 단위 싱글턴). */
function getCodeToHtml(): Promise<CodeToHtml> {
	if (!codeToHtmlPromise) {
		codeToHtmlPromise = import('shiki').then(
			(mod) => (mod as unknown as { codeToHtml: CodeToHtml }).codeToHtml
		);
	}
	return codeToHtmlPromise;
}

function langFromClass(el: Element): string {
	const cls = el.getAttribute('class') ?? '';
	const m = cls.match(/language-([\w+-]+)/);
	return m ? m[1] : 'text';
}

/**
 * 주어진 컨테이너 내부의 모든 <pre><code> 블록을 shiki 로 하이라이트한다.
 * 완료(스트리밍 종료) 후 한 번만 호출한다. 이미 처리된 블록은 건너뛴다.
 */
export async function highlightCodeBlocks(container: HTMLElement): Promise<void> {
	const blocks = Array.from(container.querySelectorAll('pre > code')).filter(
		(el) => !el.closest('pre')?.hasAttribute('data-shiki')
	);
	if (blocks.length === 0) return;

	const codeToHtml = await getCodeToHtml();

	for (const code of blocks) {
		const pre = code.closest('pre');
		if (!pre) continue;
		const lang = langFromClass(code);
		const text = code.textContent ?? '';
		try {
			const html = await codeToHtml(text, {
				lang,
				themes: { light: 'github-light', dark: 'github-dark' },
				defaultColor: false
			});
			// shiki 는 <pre class="shiki">...</pre> 전체를 반환. 기존 pre 를 교체.
			const tpl = document.createElement('template');
			tpl.innerHTML = html.trim();
			const next = tpl.content.firstElementChild;
			if (next instanceof HTMLElement) {
				next.setAttribute('data-shiki', '');
				pre.replaceWith(next);
			} else {
				pre.setAttribute('data-shiki', '');
			}
		} catch {
			// 미지원 언어 등: 원본 유지, 재시도 방지 플래그만
			pre.setAttribute('data-shiki', '');
		}
	}
}
