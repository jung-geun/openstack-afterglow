<script lang="ts">
	import { api, ApiError } from '$lib/api/client';
	import { projectNames } from '$lib/stores/projectNames';

	interface AdminVolume {
		id: string;
		name: string;
		status: string;
		size: number;
		volume_type: string;
		project_id: string | null;
		attachments: Record<string, string>[];
		created_at: string | null;
		description: string;
		bootable: boolean | null;
		encrypted: boolean | null;
		multiattach: boolean | null;
		metadata: Record<string, string>;
	}

	interface Props {
		volumeId: string;
		onClose?: () => void;
		onRefresh?: () => void;
		token?: string;
		projectId?: string;
	}

	let { volumeId, onClose, onRefresh, token, projectId }: Props = $props();

	let volume = $state<AdminVolume | null>(null);
	let loading = $state(true);
	let error = $state('');

	const statusColor: Record<string, string> = {
		available: 'text-green-400',
		creating: 'text-yellow-400',
		error: 'text-red-400',
		in_use: 'text-blue-400',
		deleting: 'text-red-400',
	};

	$effect(() => {
		if (!volumeId) return;
		loading = true;
		error = '';
		volume = null;
		fetchVolume(volumeId);
	});

	async function fetchVolume(id: string) {
		try {
			volume = await api.get<AdminVolume>(`/api/admin/volumes/${id}`, token, projectId);
		} catch (e) {
			error = e instanceof ApiError ? e.message : '볼륨 조회 실패';
		} finally {
			loading = false;
		}
	}
</script>

<div class="flex flex-col h-full">
	<div class="flex items-center justify-between px-5 py-4 border-b border-gray-800 flex-shrink-0">
		<h2 class="text-sm font-semibold text-white truncate">{volume?.name || volumeId.slice(0, 12)}</h2>
		<button onclick={onClose} class="text-gray-400 hover:text-white text-xl leading-none ml-3 flex-shrink-0">×</button>
	</div>

	<div class="flex-1 overflow-y-auto p-5 space-y-4">
		{#if loading}
			<div class="text-gray-500 text-sm">로딩 중...</div>
		{:else if error}
			<div class="text-red-400 text-sm">{error}</div>
		{:else if volume}
			<!-- 헤더 -->
			<div class="flex items-center gap-3">
				<span class="text-lg font-semibold text-white">{volume.name || '-'}</span>
				<span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[volume.status] ?? 'text-gray-400'}">{volume.status}</span>
				<span class="text-gray-400 text-sm">{volume.size} GB</span>
			</div>

			<!-- 기본 정보 -->
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">기본 정보</h3>
				<dl class="space-y-2 text-xs">
					<div class="flex justify-between">
						<dt class="text-gray-400">ID</dt>
						<dd class="text-gray-300 font-mono text-xs">{volume.id}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">볼륨 유형</dt>
						<dd class="text-gray-300">{volume.volume_type || '-'}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">프로젝트</dt>
						<dd class="text-gray-300">{volume.project_id ? ($projectNames.get(volume.project_id) ?? volume.project_id.slice(0, 8)) : '-'}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">생성일</dt>
						<dd class="text-gray-300">{volume.created_at?.slice(0, 19) ?? '-'}</dd>
					</div>
					{#if volume.description}
						<div class="flex justify-between">
							<dt class="text-gray-400">설명</dt>
							<dd class="text-gray-300">{volume.description}</dd>
						</div>
					{/if}
				</dl>
			</div>

			<!-- 속성 -->
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">속성</h3>
				<dl class="space-y-2 text-xs">
					<div class="flex justify-between">
						<dt class="text-gray-400">부트 가능</dt>
						<dd class="{volume.bootable ? 'text-green-400' : 'text-gray-500'}">{volume.bootable ? '예' : '아니오'}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">암호화</dt>
						<dd class="{volume.encrypted ? 'text-yellow-400' : 'text-gray-500'}">{volume.encrypted ? '예' : '아니오'}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">다중 연결</dt>
						<dd class="{volume.multiattach ? 'text-blue-400' : 'text-gray-500'}">{volume.multiattach ? '예' : '아니오'}</dd>
					</div>
				</dl>
			</div>

			<!-- 연결 정보 -->
			{#if volume.attachments.length > 0}
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">연결 정보</h3>
					<div class="space-y-2">
						{#each volume.attachments as att}
							<div class="text-xs space-y-1">
								<div class="text-gray-300 font-mono">{att.server_id?.slice(0, 8)}...</div>
								<div class="text-gray-500">{att.device}</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}

			<!-- 메타데이터 -->
			{#if Object.keys(volume.metadata).length > 0}
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">메타데이터</h3>
					<dl class="space-y-1.5 text-xs">
						{#each Object.entries(volume.metadata) as [k, v]}
							<div class="flex gap-2">
								<dt class="text-gray-500 min-w-24">{k}</dt>
								<dd class="text-gray-300 break-all">{v}</dd>
							</div>
						{/each}
					</dl>
				</div>
			{/if}
		{/if}
	</div>
</div>
