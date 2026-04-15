import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/public';

// 인증 없이 접근 가능한 경로
const PUBLIC_PATHS = ['/', '/auth/gitlab/callback'];

// 정적 파일로 판단할 확장자 패턴
const STATIC_EXT = /\.(js|css|svg|png|jpg|jpeg|ico|woff2?|ttf|eot|map|webp|gif)$/;

// connect-src에 API base URL 추가 (dev 환경에서 cross-origin 허용)
function buildConnectSrc(): string {
	const apiBase = env.PUBLIC_API_BASE;
	if (apiBase && apiBase !== '') {
		try {
			const url = new URL(apiBase);
			return `'self' ${url.origin}`;
		} catch {
			// 잘못된 URL이면 self만 사용
		}
	}
	return "'self'";
}

// 모든 응답에 추가할 보안 헤더
const SECURITY_HEADERS: Record<string, string> = {
	'X-Frame-Options': 'DENY',
	'X-Content-Type-Options': 'nosniff',
	'Referrer-Policy': 'strict-origin-when-cross-origin',
	'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
	'X-XSS-Protection': '0',
	'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
	// SvelteKit은 인라인 스타일/스크립트를 사용하므로 unsafe-inline 허용
	'Content-Security-Policy':
		`default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src ${buildConnectSrc()}; font-src 'self'; frame-ancestors 'none'`,
};

export const handle: Handle = async ({ event, resolve }) => {
	const path = event.url.pathname;

	// 공개 경로, 정적 리소스, SvelteKit 내부 경로는 통과
	if (
		PUBLIC_PATHS.includes(path) ||
		path.startsWith('/_app/') ||
		path.startsWith('/favicon') ||
		path.startsWith('/logo') ||
		STATIC_EXT.test(path)
	) {
		const response = await resolve(event);
		for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
			response.headers.set(key, value);
		}
		return response;
	}

	// 서버 사이드에서는 localStorage에 접근할 수 없으므로,
	// 클라이언트의 auth.ts에서 설정한 마커 쿠키로 로그인 여부를 판단.
	// (토큰 자체는 쿠키에 없으므로 쿠키 탈취 시 실제 API 호출은 불가)
	const sessionCookie = event.cookies.get('afterglow_session');
	if (!sessionCookie) {
		return new Response(null, {
			status: 302,
			headers: { Location: '/' }
		});
	}

	const response = await resolve(event);
	for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
		response.headers.set(key, value);
	}
	return response;
};
