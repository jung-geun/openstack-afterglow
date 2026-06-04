export function createDroverClusterPanel() {
	let selectedClusterId = $state<string | null>(null);

	function open(id: string) {
		selectedClusterId = id;
		history.pushState({ clusterId: id }, '', `/dashboard/drover/${id}`);
	}

	function close() {
		selectedClusterId = null;
		history.pushState({}, '', '/dashboard/drover');
	}

	$effect(() => {
		function onPop(e: PopStateEvent) {
			selectedClusterId = e.state?.clusterId ?? null;
		}
		window.addEventListener('popstate', onPop);
		return () => window.removeEventListener('popstate', onPop);
	});

	return {
		get selectedClusterId() {
			return selectedClusterId;
		},
		open,
		close,
	};
}
