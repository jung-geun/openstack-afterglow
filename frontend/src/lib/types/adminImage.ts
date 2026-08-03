export interface AdminImage {
	id: string;
	name: string;
	status: string;
	repository?: string;
	tag?: string;
	size: number;
	min_disk: number;
	min_ram: number;
	disk_format: string;
	os_distro: string | null;
	visibility: string;
	owner: string;
	created_at: string | null;
	protected: boolean;
}

export interface ImageDetail extends AdminImage {
	virtual_size: number;
	container_format: string;
	checksum: string | null;
	updated_at: string | null;
	os_version?: string | null;
	tags: string[];
	properties: Record<string, string>;
	os_hash_algo?: string | null;
	os_hash_value?: string | null;
	direct_url?: string | null;
}

export interface ImageMember {
	member_id: string;
	status: string;
}

export interface PagedResponse<T> {
	items: T[];
	next_marker: string | null;
	count: number;
}

export const visibilityColor: Record<string, string> = {
	public:    'text-green-400 bg-green-900/30',
	community: 'text-blue-400 bg-blue-900/30',
	shared:    'text-yellow-400 bg-yellow-900/30',
	private:   'text-gray-400 bg-gray-800',
};
