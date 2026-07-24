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
});
