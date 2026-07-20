/**
 * 채팅 첨부 업로드 — 전용 object storage 버킷(POST /api/v1/chat/attachments).
 *
 * 반환된 참조(key/mime/name)를 completions 요청의 attachments 로 넘기면 vision content 로 전달된다.
 */
import { getBaseUrl } from './client';

/** 백엔드 반환 참조 + 프론트 로컬 상태(썸네일·업로드 진행). */
export interface ChatAttachment {
	/** 업로드 완료 후 채워지는 object key */
	key?: string;
	mime: string;
	name: string;
	/** 로컬 미리보기(object URL) — 칩 썸네일용 */
	previewUrl?: string;
	status: 'uploading' | 'done' | 'error';
}

export interface AttachmentRef {
	key: string;
	mime: string;
	name: string;
}

/** 완료(done)된 첨부만 백엔드 전송용 참조로. */
export function toRefs(items: ChatAttachment[]): AttachmentRef[] {
	return items
		.filter((a) => a.status === 'done' && a.key)
		.map((a) => ({ key: a.key as string, mime: a.mime, name: a.name }));
}

interface UploadOptions {
	token?: string;
	projectId?: string;
	signal?: AbortSignal;
}

/** 이미지 파일 1개 업로드 → {key,mime,name}. 실패 시 throw. */
export async function uploadChatAttachment(
	file: File,
	{ token, projectId, signal }: UploadOptions = {}
): Promise<AttachmentRef> {
	const headers: Record<string, string> = {};
	if (token) headers['Authorization'] = `Bearer ${token}`;
	if (projectId) headers['X-Project-Id'] = projectId;

	const form = new FormData();
	form.append('file', file);

	const res = await fetch(`${getBaseUrl()}/api/v1/chat/attachments`, {
		method: 'POST',
		headers,
		body: form,
		signal
	});
	if (!res.ok) {
		let detail = res.statusText;
		try {
			const t = await res.text();
			if (t) detail = t;
		} catch {
			/* ignore */
		}
		throw new Error(detail || `첨부 업로드 실패 (${res.status})`);
	}
	return (await res.json()) as AttachmentRef;
}
