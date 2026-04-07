/** 천단위 쉼표 포맷 */
export function formatNumber(n: number): string {
	return n.toLocaleString();
}

/** GB 단위를 TB/PB로 자동 변환 (1,000 GB → 1 TB) */
export function formatStorage(gb: number): string {
	if (gb >= 1_000_000)
		return `${(gb / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 1 })} PB`;
	if (gb >= 1_000)
		return `${(gb / 1_000).toLocaleString(undefined, { maximumFractionDigits: 1 })} TB`;
	return `${gb.toLocaleString()} GB`;
}
