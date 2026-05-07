/**
 * 오브젝트 스토리지 버킷 이름 클라이언트 검증 (Phase 10).
 *
 * S3 RFC 1123 + Ceph/Swift/AWS 예약어 + 관리용 시스템 이름 차단.
 * backend `app/services/bucket_naming.py` 와 정책을 동일하게 유지해야 함.
 *
 * 통과 시 null, 위반 시 한국어 사유 메시지 반환.
 */

const RESERVED_EXACT: ReadonlySet<string> = new Set([
	'admin',
	'administrator',
	'root',
	'system',
	'default',
	'swift',
	'ceph',
	'rgw',
	's3',
	'aws',
	'bucket',
	'container',
	'account',
	'test-quarantine',
	'.well-known'
]);

const RESERVED_SUFFIXES: readonly string[] = ['-quarantine', '_segments'];
const RESERVED_PREFIXES: readonly string[] = ['aws-', 'amazon-', '_account', '_container'];

const FORMAT_RE = /^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/;
const IPV4_RE = /^(?:\d{1,3}\.){3}\d{1,3}$/;

export function validateBucketName(name: unknown): string | null {
	if (typeof name !== 'string') {
		return '이름은 문자열이어야 합니다.';
	}

	if (name !== name.trim()) {
		return '이름의 앞뒤 공백을 제거해 주세요.';
	}

	if (!name) {
		return '버킷 이름이 비어 있습니다.';
	}

	if (name.startsWith('.')) {
		return '버킷 이름은 점(.)으로 시작할 수 없습니다.';
	}
	if (name.startsWith('-')) {
		return '버킷 이름은 하이픈(-)으로 시작할 수 없습니다.';
	}

	const lower = name.toLowerCase();

	if (RESERVED_EXACT.has(lower)) {
		return `'${name}' 은(는) 관리용 예약 이름이라 사용할 수 없습니다.`;
	}

	for (const suf of RESERVED_SUFFIXES) {
		if (lower.endsWith(suf)) {
			return `'${suf}' 로 끝나는 이름은 시스템 예약 패턴이라 사용할 수 없습니다.`;
		}
	}

	for (const pre of RESERVED_PREFIXES) {
		if (lower.startsWith(pre)) {
			return `'${pre}' 로 시작하는 이름은 시스템 예약 패턴이라 사용할 수 없습니다.`;
		}
	}

	if (name.length < 3) return '버킷 이름은 3자 이상이어야 합니다.';
	if (name.length > 63) return '버킷 이름은 63자 이하여야 합니다.';

	if (!FORMAT_RE.test(name)) {
		if (/[A-Z]/.test(name)) return '버킷 이름은 소문자만 사용할 수 있습니다.';
		if (name.includes('.')) return '버킷 이름에 점(.)은 사용할 수 없습니다.';
		if (name.includes('_')) return '버킷 이름에 밑줄(_)은 사용할 수 없습니다.';
		if (name.includes(' ')) return '버킷 이름에 공백을 사용할 수 없습니다.';
		for (const ch of name) {
			if (!/[a-z0-9-]/.test(ch)) {
				return `'${ch}' 문자는 사용할 수 없습니다 (소문자, 숫자, 하이픈만 가능).`;
			}
		}
		if (name.endsWith('-')) return '버킷 이름은 하이픈(-)으로 끝날 수 없습니다.';
		return '버킷 이름이 명명 규칙과 맞지 않습니다.';
	}

	if (name.includes('--')) {
		return '버킷 이름에 연속된 하이픈(--)을 사용할 수 없습니다.';
	}

	if (IPV4_RE.test(name)) {
		return '버킷 이름은 IP 주소 형식일 수 없습니다.';
	}

	return null;
}
