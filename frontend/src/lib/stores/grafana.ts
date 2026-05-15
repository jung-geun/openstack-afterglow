import { writable, get } from 'svelte/store';
import { api } from '$lib/api/client';

export type GrafanaDashboardKey = 'node' | 'rabbitmq' | 'mysqld' | 'memcached' | 'etcd' | 'haproxy';

interface GrafanaContext {
	grafanaUrl: string;
	dashboards: Record<GrafanaDashboardKey, string>;
}

interface GrafanaContextStore {
	ctx: GrafanaContext | null;
	loading: boolean;
	error: boolean;
}

const store = writable<GrafanaContextStore>({ ctx: null, loading: false, error: false });

let _inflight: Promise<GrafanaContext | null> | null = null;

export async function loadGrafanaContext(
	token: string | undefined,
	projectId: string | undefined
): Promise<GrafanaContext | null> {
	const current = get(store);
	if (current.ctx) return current.ctx;
	if (current.loading && _inflight) return _inflight;

	store.update((s) => ({ ...s, loading: true, error: false }));

	_inflight = (async () => {
		try {
			const dashData = await api.get<{ grafana_url: string; dashboards: Record<string, string> }>(
				'/api/grafana/dashboards',
				token,
				projectId
			);

			if (!dashData.grafana_url) {
				store.update((s) => ({ ...s, loading: false, ctx: null }));
				return null;
			}

			const ctx: GrafanaContext = {
				grafanaUrl: dashData.grafana_url.replace(/\/$/, ''),
				dashboards: dashData.dashboards as Record<GrafanaDashboardKey, string>,
			};
			store.update((s) => ({ ...s, loading: false, ctx }));
			return ctx;
		} catch {
			store.update((s) => ({ ...s, loading: false, error: true, ctx: null }));
			return null;
		} finally {
			_inflight = null;
		}
	})();

	return _inflight;
}

export function resetGrafanaContext() {
	store.set({ ctx: null, loading: false, error: false });
	_inflight = null;
}

export const grafanaStore = { subscribe: store.subscribe };
