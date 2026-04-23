/** ISO 날짜 문자열을 짧은 날짜 형식으로 포맷 (예: "2024. 03. 15.") */
export function formatDate(iso: string): string {
	if (!iso) return '-';
	const d = new Date(iso);
	if (isNaN(d.getTime())) return '-';
	return d.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

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
