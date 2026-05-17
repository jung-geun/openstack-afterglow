export interface AdminInstance {
	id: string;
	name: string;
	status: string;
	project_id: string | null;
	user_id: string | null;
	flavor: string;
	host: string | null;
	created_at: string | null;
	fault?: string | null;
}

export interface PagedResponse<T> {
	items: T[];
	next_marker: string | null;
	count: number;
}

export interface TsPoint {
	ts: number;
	total?: number;
	active?: number;
	shutoff?: number;
	error?: number;
	shelved?: number;
	[key: string]: number | undefined;
}
