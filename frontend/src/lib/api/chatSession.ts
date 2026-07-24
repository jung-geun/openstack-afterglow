const PREFIX = 'afterglow:chat:active-conversation:';

function storage(): Storage | null {
	return typeof window === 'undefined' ? null : window.sessionStorage;
}

function key(projectId: string): string {
	return `${PREFIX}${projectId}`;
}

/** Persistent chat IDs are non-secret routing state; message content is never stored here. */
export function loadActiveConversationId(projectId: string): string | null {
	try {
		return storage()?.getItem(key(projectId)) || null;
	} catch {
		return null;
	}
}

export function saveActiveConversationId(projectId: string, conversationId: string): void {
	try {
		storage()?.setItem(key(projectId), conversationId);
	} catch {
		// Private browsing/storage policy must not block chat navigation.
	}
}

export function clearActiveConversationId(projectId: string): void {
	try {
		storage()?.removeItem(key(projectId));
	} catch {
		// Private browsing/storage policy must not block chat navigation.
	}
}
