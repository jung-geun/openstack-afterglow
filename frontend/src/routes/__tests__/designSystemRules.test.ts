import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const repoRoot = resolve(__dirname, '../../..');
const layoutSource = readFileSync(resolve(repoRoot, 'src/routes/layout.css'), 'utf8');
const designSource = readFileSync(resolve(repoRoot, '../DESIGN.md'), 'utf8');
const readmeSource = readFileSync(resolve(repoRoot, 'README.md'), 'utf8');
const agentsPath = resolve(repoRoot, '../AGENTS.md');
const agentsSource = existsSync(agentsPath) ? readFileSync(agentsPath, 'utf8') : '';
const uiIndexSource = readFileSync(resolve(repoRoot, 'src/lib/components/ui/index.ts'), 'utf8');
const tokenSource = readFileSync(resolve(repoRoot, 'src/lib/design/tokens.ts'), 'utf8');

const editorialTokenNames = [
	'--gradient-editorial-canvas',
	'--pattern-editorial-grid',
	'--gradient-editorial-grid-mask',
	'--gradient-editorial-cta',
	'--color-surface-editorial-media',
];


const chatMessageTokenNames = [
	'--chat-message-gap',
	'--chat-message-meta-gap',
	'--chat-message-meta-inset',
	'--chat-message-meta-size',
	'--chat-message-radius',
	'--chat-message-directional-corner',
	'--chat-message-padding-block',
	'--chat-message-padding-inline',
	'--chat-message-assistant-max-inline',
	'--chat-message-user-max-inline',
];

const designTokenNames = [
	'--color-surface-canvas',
	'--color-surface-base',
	'--color-surface-raised',
	'--color-surface-sunken',
	'--color-ink-0',
	'--color-ink-1',
	'--color-ink-2',
	'--color-ink-3',
	'--color-line',
	'--color-line-2',
	'--color-accent',
	'--color-accent-2',
	'--color-warm',
	'--color-warm-2',
	'--color-state-success',
	'--color-state-warning',
	'--color-state-danger',
	'--color-state-info',
	'--color-state-neutral',
];

const requiredUiExports = [
	'Alert',
	'Button',
	'Card',
	'Field',
	'TextInput',
	'SelectInput',
	'ChatBubble',
	'TextareaInput',
	'TableShell',
	'ToggleGroup',
	'UsageBar',
	'StatusChip',
	'Pill',
];

describe('design system source contracts', () => {
	it('keeps layout.css as the token authority with the legacy override boundary', () => {
		expect(layoutSource).toContain('@theme static');
		expect(layoutSource).toContain(':root.light');
		expect(layoutSource).toContain('Legacy light-mode compatibility overrides');
		for (const token of designTokenNames) expect(layoutSource).toContain(token);
	});

	it('keeps DESIGN.md as the canonical new-entity rulebook', () => {
		expect(designSource).toContain('새 색상·gradient·badge tone·table density·form control·card treatment가 필요하면');
		expect(designSource).toContain('새 route/component file은 raw hex');
		for (const token of designTokenNames) expect(designSource).toContain(token);
	});

	it('keeps editorial public-surface tokens and panel composition documented', () => {
		for (const token of editorialTokenNames) {
			expect(layoutSource).toContain(token);
			expect(tokenSource).toContain(token);
			expect(designSource).toContain(token);
		}
		expect(tokenSource).toContain('EDITORIAL_CSS_VAR');
		expect(designSource).toContain('Approved panel composition');
		expect(designSource).toContain('Card surface="subtle"');
		expect(designSource).toContain('method matrix is one Card');
	});

	it('defines the reusable chat message primitive and its shared layout tokens', () => {
		for (const token of chatMessageTokenNames) {
			expect(layoutSource).toContain(token);
			expect(tokenSource).toContain(token);
			expect(designSource).toContain(token);
		}
		expect(tokenSource).toContain('CHAT_MESSAGE_CSS_VAR');
		expect(designSource).toContain('ChatBubble');
		expect(designSource).toContain('chat-start');
		expect(designSource).toContain('chat-end');
	});

	it('links tracked frontend docs and optional local agent instructions to the canonical design system', () => {
		expect(readmeSource).toContain('../DESIGN.md');
		if (agentsSource) expect(agentsSource).toContain('프론트엔드 UI/UX 디자인 시스템');
	});

	it('exports the reusable primitives required for new UI work', () => {
		for (const componentName of requiredUiExports) {
			expect(uiIndexSource).toContain(`export { default as ${componentName} }`);
		}
	});
});
