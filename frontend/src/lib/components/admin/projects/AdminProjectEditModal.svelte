<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface Project {
		id: string;
		name: string;
		description: string;
		enabled: boolean;
		domain_id: string | null;
		created_at: string | null;
	}

	let {
		project,
		onClose,
		onSuccess,
	}: {
		project: Project | null;
		onClose: () => void;
		onSuccess: () => void;
	} = $props();

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let editName = $state('');
	let editDesc = $state('');
	let editEnabled = $state(true);
	let updating = $state(false);
	let editError = $state('');

	$effect(() => {
		if (project) {
			editName = project.name;
			editDesc = project.description;
			editEnabled = project.enabled;
			editError = '';
		}
	});

	async function updateProject() {
		if (!project) return;
		updating = true;
		editError = '';
		try {
			await api.patch(
				`/api/v1/admin/projects/${project.id}`,
				{ name: editName, description: editDesc || null, enabled: editEnabled },
				token,
				projectId,
			);
			onSuccess();
			onClose();
		} catch (e) {
			editError = e instanceof ApiError ? e.message : '수정 실패';
		} finally {
			updating = false;
		}
	}
</script>

{#if project}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={onClose}
		role="dialog" aria-modal="true" tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && onClose()}
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="none"
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 class="text-lg font-semibold text-white mb-5">프로젝트 수정</h2>
			{#if editError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{editError}</div>
			{/if}
			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
					<input bind:value={editName} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명</label>
					<input bind:value={editDesc} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
				</div>
				<div class="flex items-center gap-3">
					<button
						onclick={() => (editEnabled = !editEnabled)}
						class="relative w-11 h-6 rounded-full transition-colors {editEnabled ? 'bg-blue-600' : 'bg-gray-700'}"
					><span class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform {editEnabled ? 'translate-x-5' : ''}"></span></button>
					<span class="text-sm text-gray-300">{editEnabled ? '활성' : '비활성'}</span>
				</div>
				<div class="text-xs text-gray-500">ID: {project.id}</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={onClose} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={updateProject} disabled={updating} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{updating ? '수정 중...' : '수정'}</button>
			</div>
		</div>
	</div>
{/if}
