import { describe, expect, it } from 'vitest';
import { getStatusStyle } from './statusColors';

describe('chat run status style', () => {
	it('renders running durable conversations as an active status', () => {
		expect(getStatusStyle('chat_running')).toEqual({
			tone: 'info',
			pulse: true,
			label: '실행 중'
		});
	});

	it('uses explicit authority labels for MCP access levels and terminal grants', () => {
		expect(getStatusStyle('read')).toEqual({ tone: 'info', label: '읽기' });
		expect(getStatusStyle('manage')).toEqual({ tone: 'warning', label: '관리' });
		expect(getStatusStyle('revoked')).toEqual({ tone: 'neutral', label: '폐기됨' });
		expect(getStatusStyle('expired')).toEqual({ tone: 'neutral', label: '만료됨' });
	});
});
