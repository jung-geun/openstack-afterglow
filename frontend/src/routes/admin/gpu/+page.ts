import { redirect } from '@sveltejs/kit';

// GPU 페이지는 하이퍼바이저 페이지로 통합됨 (milestone §72)
export function load() {
	redirect(308, '/admin/hypervisors');
}
