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
