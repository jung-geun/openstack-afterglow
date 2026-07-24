export function pruneSelection(selected: Set<string>, items: { id: string }[]): Set<string> {
	return pruneSelectionByIds(selected, items.map((item) => item.id));
}

export function pruneSelectionByIds(selected: Set<string>, ids: Iterable<string>): Set<string> {
	const availableIds = new Set(ids);
	return new Set([...selected].filter((id) => availableIds.has(id)));
}

export function removeFromSelection(selected: Set<string>, ids: string[]): Set<string> {
	const next = new Set(selected);
	for (const id of ids) next.delete(id);
	return next;
}
