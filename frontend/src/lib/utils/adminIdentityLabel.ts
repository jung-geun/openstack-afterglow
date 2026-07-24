export function abbreviatedIdentifier(id: string, length = 8): string {
	return id.length > length ? id.slice(0, length) : id;
}

export function adminIdentityLabel(name: string | null | undefined, id: string): string {
	const shortId = abbreviatedIdentifier(id);
	return name?.trim() ? `${name.trim()} (${shortId})` : `(${shortId})`;
}
