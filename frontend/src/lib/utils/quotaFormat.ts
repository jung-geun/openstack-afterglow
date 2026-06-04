export function formatRam(mb: number): string {
	if (mb >= 1024) return `${(mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)} GB`;
	return `${mb} MB`;
}
