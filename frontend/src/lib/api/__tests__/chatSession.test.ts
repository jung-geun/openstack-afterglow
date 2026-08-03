import { afterEach, describe, expect, it } from 'vitest';
import {
	clearActiveConversationId,
	loadActiveConversationId,
	saveActiveConversationId
} from '../chatSession';

describe('persistent chat selection', () => {
	afterEach(() => sessionStorage.clear());

	it('stores only the selected conversation ID scoped to its project', () => {
		saveActiveConversationId('project-a', 'conversation-1');

		expect(loadActiveConversationId('project-a')).toBe('conversation-1');
		expect(loadActiveConversationId('project-b')).toBeNull();
	});

	it('clears the selection for a new conversation', () => {
		saveActiveConversationId('project-a', 'conversation-1');
		clearActiveConversationId('project-a');

		expect(loadActiveConversationId('project-a')).toBeNull();
	});
});
