<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import type { Project, Quotas, GpuQuota, GpuDefaultQuota } from '$lib/types/quotas';
	import GpuDefaultQuotaSection from '$lib/components/admin/quotas/GpuDefaultQuotaSection.svelte';
	import ProjectSelector from '$lib/components/admin/quotas/ProjectSelector.svelte';
	import ProjectQuotaForm from '$lib/components/admin/quotas/ProjectQuotaForm.svelte';
	import GpuQuotaTable from '$lib/components/admin/quotas/GpuQuotaTable.svelte';

	let projects = $state<Project[]>([]);
	let selectedProjectId = $state('');
	let selectedProjectName = $state('');
	let projectSearch = $state('');
	let quotas = $state<Quotas | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let quotaLoading = $state(false);
	let saving = $state(false);
	let saveError = $state('');
	let saveSuccess = $state('');

	let gpuAliases = $state<string[]>([]);
	let gpuQuotas = $state<GpuQuota[]>([]);
	let gpuDefaults = $state<GpuDefaultQuota[]>([]);
	let gpuQuotaLoading = $state(false);
	let gpuQuotaError = $state('');
	let gpuDefaultLoading = $state(false);
	let gpuDefaultError = $state('');
	let gpuDefaultSuccess = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const gpuQuotaMap = $derived(Object.fromEntries(gpuQuotas.map(q => [q.gpu_type, q])));
	const gpuDefaultMap = $derived(Object.fromEntries(gpuDefaults.map(q => [q.gpu_type, q.limit])));
	const allGpuTypes = $derived(
		[...new Set([...gpuAliases, ...gpuDefaults.map(d => d.gpu_type), ...gpuQuotas.map(q => q.gpu_type)])].sort()
	);

	async function loadProjects() {
		if (projects.length === 0) loading = true;
		else refreshing = true;
		try {
			const res = await api.get<{ id: string; name: string }[]>('/api/admin/projects/names', token, projectId);
			projects = res || [];
		} catch { projects = []; } finally { loading = false; refreshing = false; }
	}

	async function loadGpuAliases() {
		try {
			const res = await api.get<{ aliases: string[] }>('/api/admin/gpu-aliases', token, projectId);
			gpuAliases = res.aliases ?? [];
		} catch (e) {
			console.warn('[Quotas] GPU alias 로드 실패:', e instanceof ApiError ? e.message : e);
			gpuAliases = [];
		}
	}

	async function loadGpuDefaults() {
		gpuDefaultLoading = true; gpuDefaultError = '';
		try {
			gpuDefaults = await api.get<GpuDefaultQuota[]>('/api/admin/gpu-quotas/defaults', token, projectId);
		} catch (e) {
			gpuDefaultError = e instanceof ApiError ? e.message : '기본 GPU quota 조회 실패';
			gpuDefaults = [];
		} finally { gpuDefaultLoading = false; }
	}

	async function setGpuDefault(gpuType: string, limit: number) {
		gpuDefaultError = ''; gpuDefaultSuccess = '';
		try {
			await api.put('/api/admin/gpu-quotas/defaults', { gpu_type: gpuType, limit }, token, projectId);
			gpuDefaultSuccess = '기본 GPU quota 저장됨';
			await loadGpuDefaults();
			if (selectedProjectId) await loadGpuQuotas();
		} catch (e) {
			gpuDefaultError = e instanceof ApiError ? e.message : '기본 GPU quota 설정 실패';
		}
	}

	async function loadQuotas() {
		if (!selectedProjectId) { quotas = null; return; }
		quotaLoading = true; saveError = ''; saveSuccess = '';
		try {
			quotas = await api.get<Quotas>(`/api/admin/quotas/${selectedProjectId}`, token, projectId);
		} catch { quotas = null; } finally { quotaLoading = false; }
		await loadGpuQuotas();
	}

	async function loadGpuQuotas() {
		if (!selectedProjectId) { gpuQuotas = []; return; }
		gpuQuotaLoading = true; gpuQuotaError = '';
		try {
			gpuQuotas = await api.get<GpuQuota[]>(`/api/admin/gpu-quotas/${selectedProjectId}`, token, projectId);
		} catch (e) {
			gpuQuotaError = e instanceof ApiError ? e.message : 'GPU quota 조회 실패';
			gpuQuotas = [];
		} finally { gpuQuotaLoading = false; }
	}

	async function setGpuQuota(gpuType: string, limit: number) {
		if (!selectedProjectId) return;
		gpuQuotaError = '';
		try {
			await api.put(`/api/admin/gpu-quotas/${selectedProjectId}`, { gpu_type: gpuType, limit }, token, projectId);
			await loadGpuQuotas();
		} catch (e) {
			gpuQuotaError = e instanceof ApiError ? e.message : 'GPU quota 설정 실패';
		}
	}

	async function deleteGpuQuota(gpuType: string) {
		if (!selectedProjectId) return;
		try {
			await api.delete(`/api/admin/gpu-quotas/${selectedProjectId}/${encodeURIComponent(gpuType)}`, token, projectId);
			await loadGpuQuotas();
		} catch (e) {
			gpuQuotaError = e instanceof ApiError ? e.message : 'GPU quota 삭제 실패';
		}
	}

	async function saveQuotas(form: { instances: number; cores: number; ram: number; volumes: number; gigabytes: number }) {
		if (!selectedProjectId) return;
		saving = true; saveError = ''; saveSuccess = '';
		try {
			await api.put(`/api/admin/quotas/${selectedProjectId}`, form, token, projectId);
			saveSuccess = '저장되었습니다';
			await loadQuotas();
		} catch (e) { saveError = e instanceof ApiError ? e.message : '저장 실패'; } finally { saving = false; }
	}

	onMount(() => { loadProjects(); loadGpuAliases(); loadGpuDefaults(); });
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="IDENTITY / QUOTAS" title="쿼터" />

	{#if loading}
		<LoadingSkeleton variant="table" rows={3} />
	{:else}
		<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			<GpuDefaultQuotaSection
				defaults={gpuDefaultMap}
				allGpuTypes={allGpuTypes}
				loading={gpuDefaultLoading}
				error={gpuDefaultError}
				success={gpuDefaultSuccess}
				onChange={setGpuDefault}
			/>

			<ProjectSelector
				projects={projects}
				bind:search={projectSearch}
				bind:selectedId={selectedProjectId}
				bind:selectedName={selectedProjectName}
				onSelected={(id) => { if (id) loadQuotas(); else quotas = null; }}
			/>

			{#if selectedProjectId}
				{#if quotaLoading}
					<LoadingSkeleton variant="table" rows={3} />
				{:else if quotas}
					<ProjectQuotaForm
						quotas={quotas}
						saving={saving}
						saveError={saveError}
						saveSuccess={saveSuccess}
						onSave={saveQuotas}
					/>
					<GpuQuotaTable
						rows={gpuQuotas}
						defaults={gpuDefaultMap}
						loading={gpuQuotaLoading}
						error={gpuQuotaError}
						hasAnyAlias={allGpuTypes.length > 0}
						onSetLimit={setGpuQuota}
						onClear={deleteGpuQuota}
					/>
				{:else}
					<div class="text-gray-600 text-sm">쿼터를 불러올 수 없습니다</div>
				{/if}
			{/if}
		</div>
	{/if}
</div>
