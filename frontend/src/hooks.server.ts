import type { Handle } from '@sveltejs/kit';

// 인증 없이 접근 가능한 경로
const PUBLIC_PATHS = ['/', '/auth/gitlab/callback'];

export const handle: Handle = async ({ event, resolve }) => {
	const path = event.url.pathname;

	// 공개 경로, 정적 리소스, SvelteKit 내부 경로는 통과
	if (
		PUBLIC_PATHS.includes(path) ||
		path.startsWith('/_app/') ||
		path.startsWith('/favicon') ||
		path.startsWith('/logo') ||
		path.includes('.')
	) {
		return resolve(event);
	}

	// 서버 사이드에서는 localStorage에 접근할 수 없으므로,
	// 클라이언트의 auth.ts에서 설정한 마커 쿠키로 로그인 여부를 판단.
	// (토큰 자체는 쿠키에 없으므로 쿠키 탈취 시 실제 API 호출은 불가)
	const sessionCookie = event.cookies.get('union_session');
	if (!sessionCookie) {
		return new Response(null, {
			status: 302,
			headers: { Location: '/' }
		});
	}

	return resolve(event);
};
