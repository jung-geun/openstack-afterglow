const TAG_PATTERN = /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$/;
const REPOSITORY_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]*(?::[0-9]{1,5})?(?:\/[A-Za-z0-9][A-Za-z0-9._-]*)*$/;

export interface ImageReferenceParts {
	repository: string;
	tag: string;
	name: string;
}

export function parseImageReference(value: string): ImageReferenceParts {
	const raw = value.trim();
	if (!raw || /\s|[\u0000-\u001f\u007f]/.test(raw) || raw.includes('@')) {
		throw new Error('이미지 이름은 Docker-style repository[:tag] 형식이어야 합니다.');
	}
	const slashIndex = raw.lastIndexOf('/');
	const colonIndex = raw.lastIndexOf(':');
	const hasTag = colonIndex > slashIndex;
	const repository = hasTag ? raw.slice(0, colonIndex) : raw;
	const tag = hasTag ? raw.slice(colonIndex + 1) : 'latest';
	if (!REPOSITORY_PATTERN.test(repository) || !TAG_PATTERN.test(tag)) {
		throw new Error('이미지 이름은 Docker-style repository[:tag] 형식이어야 합니다.');
	}
	return { repository, tag, name: `${repository}:${tag}` };
}

export function sanitizeImageFilename(filename: string): string {
	const basename = filename.replace(/\.[^.]+$/, '').trim().toLowerCase();
	const repository = basename.replace(/[^a-z0-9._/-]+/g, '-').replace(/-+/g, '-').replace(/^[-./]+|[-./]+$/g, '') || 'image';
	return `${repository}:latest`;
}
