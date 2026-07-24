import { pruneSelectionByIds, removeFromSelection } from './selectionSet';

export interface ResourceSelection {
	readonly ids: ReadonlySet<string>;
	readonly count: number;
	has(id: string): boolean;
	toggle(id: string): void;
	toggleAll(ids: Iterable<string>): void;
	retain(ids: Iterable<string>): void;
	remove(ids: Iterable<string>): void;
	clear(): void;
}

export function createResourceSelection(): ResourceSelection {
	const state = $state({ ids: new Set<string>() });

	function replace(next: Set<string>) {
		if (next.size === state.ids.size && [...next].every((id) => state.ids.has(id))) return;
		state.ids = next;
	}

	return {
		get ids() {
			return state.ids;
		},
		get count() {
			return state.ids.size;
		},
		has(id) {
			return state.ids.has(id);
		},
		toggle(id) {
			const next = new Set(state.ids);
			if (next.has(id)) next.delete(id);
			else next.add(id);
			replace(next);
		},
		toggleAll(ids) {
			const selectableIds = new Set(ids);
			const next = selectableIds.size > 0 && [...selectableIds].every((id) => state.ids.has(id))
				? new Set<string>()
				: selectableIds;
			replace(next);
		},
		retain(ids) {
			replace(pruneSelectionByIds(state.ids, ids));
		},
		remove(ids) {
			replace(removeFromSelection(state.ids, [...ids]));
		},
		clear() {
			if (state.ids.size > 0) state.ids = new Set();
		},
	};
}
