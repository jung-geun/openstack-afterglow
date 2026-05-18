export interface PagedResponse<T> {
	items: T[];
	next_marker: string | null;
	count: number;
}

export interface ProjectName {
	id: string;
	name: string;
}
