export function pruneSelection(selected: Set<string>, items: { id: string }[]): Set<string> {
	return new Set([...selected].filter((id) => items.some((i) => i.id === id)));
}

export function removeFromSelection(selected: Set<string>, ids: string[]): Set<string> {
	const next = new Set(selected);
	for (const id of ids) next.delete(id);
	return next;
}
