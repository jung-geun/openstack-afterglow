export const DESIGN_TONES = ['accent', 'warm', 'success', 'warning', 'danger', 'info', 'neutral', 'admin-tone'] as const;
export type DesignTone = (typeof DESIGN_TONES)[number];

export const TONE_CSS_VAR: Record<DesignTone, string> = {
	accent: 'var(--color-accent)',
	warm: 'var(--color-warm)',
	success: 'var(--color-state-success)',
	warning: 'var(--color-state-warning)',
	danger: 'var(--color-state-danger)',
	info: 'var(--color-state-info)',
	neutral: 'var(--color-state-neutral)',
	'admin-tone': 'var(--admin-tone)',
};

export const SURFACE_CSS_VAR = {
	canvas: 'var(--color-surface-canvas)',
	base: 'var(--color-surface-base)',
	raised: 'var(--color-surface-raised)',
	sunken: 'var(--color-surface-sunken)',
	scrim: 'var(--color-surface-scrim)',
	scrimSoft: 'var(--color-surface-scrim-soft)',
} as const;

export const FONT_CSS_VAR = {
	sans: 'var(--font-sans)',
	display: 'var(--font-display)',
	mono: 'var(--font-mono)',
} as const;

export const LAYER_CSS_VAR = {
	sidebar: 'var(--z-sidebar)',
	panel: 'var(--z-panel)',
	modal: 'var(--z-modal)',
	toast: 'var(--z-toast)',
	command: 'var(--z-command)',
	popover: 'var(--z-popover)',
} as const;

export const MOTION_CSS_VAR = {
	durationFast: 'var(--motion-duration-fast)',
	durationBase: 'var(--motion-duration-base)',
	durationPanel: 'var(--motion-duration-panel)',
	durationData: 'var(--motion-duration-data)',
	durationStatusPulse: 'var(--motion-duration-status-pulse)',
	easeStandard: 'var(--motion-ease-standard)',
	easeOut: 'var(--motion-ease-out)',
	easeInOut: 'var(--motion-ease-in-out)',
} as const;

export const MOTION_DURATION_MS = {
	fast: 150,
	base: 200,
	panel: 300,
	data: 500,
	statusPulse: 1400,
} as const;

export const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)' as const;

export const EDITORIAL_CSS_VAR = {
	canvas: 'var(--gradient-editorial-canvas)',
	grid: 'var(--pattern-editorial-grid)',
	gridMask: 'var(--gradient-editorial-grid-mask)',
	cta: 'var(--gradient-editorial-cta)',
	mediaSurface: 'var(--color-surface-editorial-media)',
} as const;

export const CHART_COLORS = [
	'var(--color-chart-1)',
	'var(--color-chart-2)',
	'var(--color-chart-3)',
	'var(--color-chart-4)',
	'var(--color-chart-5)',
	'var(--color-chart-6)',
] as const;

export const TOPOLOGY_COLORS = {
	external: 'var(--color-topology-external)',
	shared: 'var(--color-topology-shared)',
	internal: 'var(--color-topology-internal)',
	router: 'var(--color-topology-router)',
	link: 'var(--color-topology-link)',
} as const;

export function usageTone(
	percent: number,
	thresholds: { warning: number; danger: number } = { warning: 80, danger: 95 },
): 'accent' | 'warning' | 'danger' {
	if (percent >= thresholds.danger) return 'danger';
	if (percent >= thresholds.warning) return 'warning';
	return 'accent';
}

export const CHAT_MESSAGE_CSS_VAR = {
	gap: 'var(--chat-message-gap)',
	metaGap: 'var(--chat-message-meta-gap)',
	metaInset: 'var(--chat-message-meta-inset)',
	metaSize: 'var(--chat-message-meta-size)',
	radius: 'var(--chat-message-radius)',
	directionalCorner: 'var(--chat-message-directional-corner)',
	paddingBlock: 'var(--chat-message-padding-block)',
	paddingInline: 'var(--chat-message-padding-inline)',
	assistantMaxInline: 'var(--chat-message-assistant-max-inline)',
	userMaxInline: 'var(--chat-message-user-max-inline)'
} as const;

export const SCROLLBAR_CSS_VAR = {
	size: 'var(--scrollbar-size)',
	track: 'var(--scrollbar-track)',
	thumb: 'var(--scrollbar-thumb)',
	thumbHover: 'var(--scrollbar-thumb-hover)'
} as const;
