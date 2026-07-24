import { writable } from 'svelte/store';
import { api } from '$lib/api/client';
import { getActiveMockupProfile } from '$lib/mockup/transport';
import { getMockupRevision, onMockupRevisionChange } from '$lib/mockup/state';
import type { MockupProfileId } from '$lib/mockup/contracts';

export interface ProjectNamesScope {
	token?: string;
	projectId?: string;
	mockProfile: MockupProfileId | null;
	mockRevision: number;
}

const nameMap = writable<Map<string, string>>(new Map());
let generation = 0;
let currentScope: ProjectNamesScope | null = null;
let currentScopeKey: string | null = null;
let settledValue: Map<string, string> | null = null;
let inFlight: { scopeKey: string; promise: Promise<Map<string, string>> } | null = null;

function scopeKey(scope: ProjectNamesScope): string {
	return JSON.stringify([
		scope.token ?? null,
		scope.projectId ?? null,
		scope.mockProfile,
		scope.mockRevision,
	]);
}

function scope(token?: string, projectId?: string): ProjectNamesScope {
	return {
		token,
		projectId,
		mockProfile: getActiveMockupProfile(),
		mockRevision: getMockupRevision(),
	};
}

function clearInFlight(requestGeneration: number, requestedScopeKey: string): void {
	if (generation === requestGeneration && inFlight?.scopeKey === requestedScopeKey) {
		inFlight = null;
	}
}

async function load(token?: string, projectId?: string): Promise<ReadonlyMap<string, string>> {
	const requestedScope = scope(token, projectId);
	const requestedScopeKey = scopeKey(requestedScope);
	if (currentScopeKey === requestedScopeKey && settledValue) return new Map(settledValue);
	if (inFlight?.scopeKey === requestedScopeKey) {
		return inFlight.promise.then((value) => new Map(value));
	}

	generation += 1;
	const requestGeneration = generation;
	currentScope = requestedScope;
	currentScopeKey = requestedScopeKey;
	settledValue = null;
	inFlight = null;
	nameMap.set(new Map());

	const promise = (async () => {
		try {
			const data = await api.get<Array<{ id: string; name: string }>>(
				'/api/v1/admin/projects/names',
				token,
				projectId,
			);
			const loaded = new Map(data.map((project) => [project.id, project.name]));
			if (
				generation === requestGeneration
				&& currentScopeKey === requestedScopeKey
				&& scopeKey(scope(token, projectId)) === requestedScopeKey
			) {
				settledValue = loaded;
				nameMap.set(new Map(loaded));
			}
			return loaded;
		} catch {
			return new Map<string, string>();
		} finally {
			clearInFlight(requestGeneration, requestedScopeKey);
		}
	})();
	inFlight = { scopeKey: requestedScopeKey, promise };
	return promise.then((value) => new Map(value));
}

function invalidate(targetScope?: ProjectNamesScope): void {
	if (!currentScope || !currentScopeKey) return;
	if (targetScope && scopeKey(targetScope) !== currentScopeKey) return;
	generation += 1;
	currentScope = null;
	currentScopeKey = null;
	settledValue = null;
	inFlight = null;
	nameMap.set(new Map());
}

export const projectNames = {
	subscribe: nameMap.subscribe,
	load,
	scope,
	invalidate,
};

onMockupRevisionChange(() => projectNames.invalidate());
