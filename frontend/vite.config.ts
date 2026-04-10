import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

const isDocker = process.env.DOCKER === 'true';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: isDocker
		? {
				host: '0.0.0.0',
				port: 3000,
				watch: {
					usePolling: true, // Docker 볼륨 마운트에서 파일 변경 감지
					interval: 1000,
				},
				hmr: {
					clientPort: 3000, // 브라우저 HMR WebSocket 포트
				},
			}
		: undefined,
	test: {
		include: ['src/**/*.{test,spec}.{js,ts}'],
		environment: 'jsdom',
		globals: true,
	},
});
