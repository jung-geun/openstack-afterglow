# Union Frontend

SvelteKit + TypeScript + Tailwind v4 기반의 Union 플랫폼 프론트엔드.

## 기술 스택

- **SvelteKit** (SPA + SSR)
- **TypeScript**
- **Tailwind CSS v4**
- **Bun** (패키지 매니저 / 빌드)

## 개발

```bash
npm install       # 의존성 설치 (bun install도 가능)
npm run dev       # 개발 서버 :3000
npm run build     # 프로덕션 빌드
npm run check     # svelte-check 타입 검사
npm test          # vitest 1회 실행
npm run test:watch  # vitest watch 모드
```

## 디렉토리 구조

```
src/
├── routes/
│   ├── +layout.svelte           # 인증 체크, 사이드바
│   ├── dashboard/               # 대시보드 (인스턴스, 볼륨, 네트워크, 파일스토리지, k3s, 컨테이너)
│   ├── admin/                   # 관리자 페이지
│   ├── create/                  # VM 생성 마법사
│   └── auth/gitlab/callback/    # GitLab OIDC 콜백
└── lib/
    ├── api/client.ts            # API 클라이언트 (base URL, 헤더, 30초 타임아웃)
    ├── stores/auth.ts           # 인증 상태 (token, projectId, isSystemAdmin)
    ├── types/resources.ts       # 공통 TypeScript 타입
    ├── config/site.ts           # 사이트 설정 (서비스 활성화 플래그)
    └── components/              # 슬라이드 패널, 위저드, 차트 등 UI 컴포넌트
```

## 환경 설정

백엔드 API는 `/api` 경로로 프록시됩니다.

- 개발: `vite.config.ts`의 프록시 설정으로 `http://localhost:8000` 연결
- 프로덕션: HAProxy / Nginx 리버스 프록시

모든 API 요청은 `X-Auth-Token`과 `X-Project-Id` 헤더를 포함합니다.
