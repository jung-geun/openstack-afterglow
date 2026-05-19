export interface Project {
	id: string;
	name: string;
	description: string;
	enabled: boolean;
	domain_id: string | null;
	created_at: string | null;
}

export interface ProjectMember {
	user_id: string;
	user_name: string;
	role_id: string;
	role_name: string;
	type?: 'user' | 'group';
	group_id?: string;
}
