export function usageBar(used: number, quota: number): string {
	if (quota <= 0) return '0';
	const pct = Math.min(100, Math.round((used / quota) * 100));
	return `${pct}`;
}

export function usageGrad(used: number, quota: number): string {
	if (quota <= 0) return '#374151';
	const pct = (used / quota) * 100;
	if (pct >= 95) return 'var(--gradient-usage-danger)';
	if (pct >= 80) return 'var(--gradient-usage-warning)';
	return 'var(--gradient-usage)';
}

export function formatQuota(used: number, quota: number, unit = ''): string {
	const u = unit === 'GB' ? Math.round(used) : used;
	const q = quota === -1 ? '∞' : (unit === 'GB' ? Math.round(quota) : quota);
	return `${u}/${q}${unit ? ' ' + unit : ''}`;
}

export function formatUptime(seconds: number): string {
	const d = Math.floor(seconds / 86400);
	const h = Math.floor((seconds % 86400) / 3600);
	const m = Math.floor((seconds % 3600) / 60);
	const parts: string[] = [];
	if (d > 0) parts.push(`${d}d`);
	if (h > 0) parts.push(`${h}h`);
	parts.push(`${m}m`);
	return parts.join(' ');
}
