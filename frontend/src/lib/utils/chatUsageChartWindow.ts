export type UsageChartBucket = '5m' | '15m' | 'hour' | 'day' | 'month';

export interface UsageChartWindow {
	milliseconds: number;
	label: string;
}

const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;

const WINDOWS: Partial<Record<UsageChartBucket, UsageChartWindow>> = {
	'5m': { milliseconds: 4 * HOUR, label: '최근 4시간' },
	'15m': { milliseconds: 12 * HOUR, label: '최근 12시간' },
	hour: { milliseconds: 48 * HOUR, label: '최근 48시간' },
	day: { milliseconds: 30 * DAY, label: '최근 30일' }
};

export function usageChartWindow(bucket: string): UsageChartWindow | null {
	return WINDOWS[bucket as UsageChartBucket] ?? null;
}
