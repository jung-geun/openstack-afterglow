export const EXT_COLORS = ['#ea580c', '#f97316'];
export const SHR_COLORS = ['#0d9488', '#14b8a6'];
export const INT_COLORS = ['#3b82f6', '#22c55e', '#a855f7', '#f59e0b', '#06b6d4', '#ec4899', '#ef4444'];

export const LANE_W = 180;
export const LANE_GAP = 16;
export const LANE_PAD = 16;
export const SIDEBAR_W = 300;

export function _ipToNum(ip: string): number | null {
	const parts = ip.split('.');
	if (parts.length !== 4) return null;
	const nums = parts.map(Number);
	if (nums.some(n => isNaN(n) || n < 0 || n > 255)) return null;
	return ((nums[0] << 24) | (nums[1] << 16) | (nums[2] << 8) | nums[3]) >>> 0;
}

export function _ipv4InCidr(ip: string, cidr: string): boolean {
	const si = cidr.lastIndexOf('/');
	if (si < 0) return false;
	const mask = parseInt(cidr.slice(si + 1));
	if (isNaN(mask) || mask < 0 || mask > 32) return false;
	const ipN = _ipToNum(ip), netN = _ipToNum(cidr.slice(0, si));
	if (ipN === null || netN === null) return false;
	const mb = mask === 0 ? 0 : ((0xFFFFFFFF << (32 - mask)) >>> 0);
	return (ipN & mb) === (netN & mb);
}

export function formatBps(bps: number): string {
	if (bps >= 1e9) return `${(bps / 1e9).toFixed(1)}G`;
	if (bps >= 1e6) return `${(bps / 1e6).toFixed(1)}M`;
	if (bps >= 1e3) return `${(bps / 1e3).toFixed(0)}k`;
	if (bps > 0) return `${bps.toFixed(0)}b`;
	return '0';
}

export function edgeIntensity(bps: number): { opacity: number; width: number } {
	if (bps >= 1e8) return { opacity: 1.00, width: 3.5 };
	if (bps >= 1e7) return { opacity: 0.90, width: 3.0 };
	if (bps >= 1e6) return { opacity: 0.80, width: 2.5 };
	if (bps >= 1e5) return { opacity: 0.65, width: 2.0 };
	return { opacity: 0.40, width: 1.5 };
}
