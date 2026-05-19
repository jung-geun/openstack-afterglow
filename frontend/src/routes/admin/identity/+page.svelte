<script lang="ts">
	import { untrack } from 'svelte';
	import { auth, authReady } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import { StatTile, SectionHeader, Pill } from '$lib/components/ui';

	interface IdentitySummary {
		user_count: number;
		project_count: number;
		role_count: number;
		group_count: number;
		domain_count: number;
		partial?: boolean;
		partial_reasons?: string[];
		recent_users: { id: string; name: string; email: string; enabled: boolean }[];
		recent_projects: { id: string; name: string; enabled: boolean; description: string }[];
	}

	let data = $state<IdentitySummary | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let tab = $state<'users' | 'projects' | 'roles'>('users');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function fetchData() {
		if (!token || !projectId) return;
		loading = !data;
		error = null;
		try {
			data = await api.get<IdentitySummary>('/api/admin/identity/summary', token, projectId);
		} catch (e) {
			error = e instanceof Error ? e.message : '데이터 로딩 실패';
		} finally {
			loading = false;
		}
	}

	const ar = createAutoRefresh(fetchData, {
		storageKey: 'admin-identity',
		defaultActive: false,
		defaultInterval: 300,
		invokeOnMount: false,
	});

	$effect(() => {
		const ready = $authReady;
		void [token, projectId];
		if (!ready || !token || !projectId) return;
		untrack(() => fetchData());
	});

	const TABS = [
		{ id: 'users'    as const, label: '사용자',    href: '/admin/users' },
		{ id: 'projects' as const, label: '프로젝트',  href: '/admin/projects' },
		{ id: 'roles'    as const, label: '역할',      href: '/admin/roles' },
	];
</script>

<div class="p-4 md:p-6 max-w-7xl mx-auto flex flex-col gap-5">
	<!-- Header -->
	<div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
		<div>
			<p class="text-[10px] uppercase tracking-wide" style="color: var(--color-ink-3);">ADMIN · IDENTITY</p>
			<h1 class="text-2xl font-bold mt-1 leading-tight" style="color: var(--color-ink-0);">사용자 · 프로젝트</h1>
			<p class="text-sm mt-1" style="color: var(--color-ink-2);">
				Keystone v3 · {data ? `${data.user_count}명 · ${data.project_count}개 프로젝트 · 쿼터 관리` : '로딩 중...'}
			</p>
		</div>
		<div class="flex items-center gap-2">
			<a href="/admin/users"
			   class="px-3 h-8 rounded-md text-xs font-medium border flex items-center hover:opacity-80 transition-opacity"
			   style="background: var(--admin-soft); color: var(--admin-tone); border-color: var(--admin-ring);">
				<svg class="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
					<path d="M12 5v14M5 12h14"/>
				</svg>
				사용자 관리
			</a>
		</div>
	</div>

	{#if loading && !data}
		<div class="text-sm" style="color: var(--color-ink-3);">로딩 중...</div>
	{:else if error && !data}
		<div class="text-sm" style="color: var(--color-state-danger);">{error}</div>
	{:else}
		<!-- KPI Tiles -->
		<div class="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
			<StatTile label="사용자" value={data?.user_count ?? 0} unit="명" accent="amber">
				{#snippet icon()}
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
						<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/>
					</svg>
				{/snippet}
			</StatTile>
			<StatTile label="프로젝트" value={data?.project_count ?? 0} unit="활성" accent="blue">
				{#snippet icon()}
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
						<path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
					</svg>
				{/snippet}
			</StatTile>
			<StatTile label="역할" value={data?.role_count ?? 0} unit="정의됨" accent="violet">
				{#snippet icon()}
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
						<path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
					</svg>
				{/snippet}
			</StatTile>
			<StatTile label="그룹" value={data?.group_count ?? 0} unit="그룹" accent="cyan">
				{#snippet icon()}
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
						<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
						<circle cx="9" cy="7" r="4"/>
						<path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>
					</svg>
				{/snippet}
			</StatTile>
		</div>

		<!-- partial 경고 배지 (역할/사용자/프로젝트 조회 권한 부족 시) -->
		{#if data?.partial && data.partial_reasons && data.partial_reasons.length > 0}
			<div class="flex items-center gap-2.5 px-4 py-2.5 rounded-xl border text-xs"
			     style="background: color-mix(in oklab, var(--color-state-warning) 10%, transparent); border-color: color-mix(in oklab, var(--color-state-warning) 30%, transparent); color: var(--color-state-warning);">
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="flex-shrink-0">
					<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
					<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
				</svg>
				<span>일부 정보 미완 — {data.partial_reasons.map(r => r.includes('insufficient_privileges') ? r.split(':')[0] + ' 권한 부족 (system-scope 필요)' : r).join(', ')}</span>
			</div>
		{/if}

		<!-- Sub-tabs -->
		<div class="flex items-center gap-1 border-b" style="border-color: var(--color-line);">
			{#each TABS as t}
				{@const on = tab === t.id}
				<button
					onclick={() => { tab = t.id; }}
					class="relative px-4 h-10 text-sm font-medium transition-colors"
					style="color: {on ? 'var(--color-ink-0)' : 'var(--color-ink-3)'};"
				>
					{t.label}{data ? ` (${t.id === 'users' ? data.user_count : t.id === 'projects' ? data.project_count : data.role_count})` : ''}
					{#if on}
						<span class="absolute left-3 right-3 bottom-0 h-0.5 rounded-t-full"
						      style="background: var(--admin-tone);"></span>
					{/if}
				</button>
			{/each}
		</div>

		<!-- Tab content -->
		{#if tab === 'users'}
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<SectionHeader title="최근 사용자" meta="전체 목록은 사용자 관리 페이지에서">
					{#snippet right()}
						<a href="/admin/users" class="text-xs hover:underline" style="color: var(--admin-tone);">전체 보기 →</a>
					{/snippet}
				</SectionHeader>
				{#if !data?.recent_users || data.recent_users.length === 0}
					<div class="mt-6 text-center text-sm py-6" style="color: var(--color-ink-3);">사용자 없음</div>
				{:else}
					<div class="mt-4 overflow-x-auto">
						<table class="w-full text-sm">
							<thead>
								<tr class="text-[10px] uppercase tracking-wide border-b" style="color: var(--color-ink-3); border-color: var(--color-line);">
									<th class="text-left pb-2 pr-4 font-medium">사용자</th>
									<th class="text-left pb-2 pr-4 font-medium">이메일</th>
									<th class="text-left pb-2 font-medium">상태</th>
								</tr>
							</thead>
							<tbody>
								{#each data.recent_users as u}
									<tr class="transition-colors" style="border-color: color-mix(in oklab, var(--color-line) 60%, transparent);">
										<td class="py-2.5 pr-4">
											<div class="flex items-center gap-2.5">
												<div class="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold shrink-0"
												     style="background: var(--color-surface-sunken); color: var(--color-ink-2);">
													{u.name.slice(0, 2).toUpperCase()}
												</div>
												<span class="font-mono font-medium" style="color: var(--color-ink-0);">{u.name}</span>
											</div>
										</td>
										<td class="py-2.5 pr-4 font-mono text-xs" style="color: var(--color-ink-1);">{u.email}</td>
										<td class="py-2.5">
											{#if u.enabled}
												<Pill tone="success">활성</Pill>
											{:else}
												<Pill tone="neutral">비활성</Pill>
											{/if}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
				<div class="mt-4 pt-3 border-t flex justify-end" style="border-color: var(--color-line);">
					<a href="/admin/users" class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors hover:opacity-80"
					   style="background: var(--admin-soft); color: var(--admin-tone); border-color: var(--admin-ring);">
						전체 사용자 관리 →
					</a>
				</div>
			</div>

		{:else if tab === 'projects'}
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<SectionHeader title="최근 프로젝트" meta="전체 목록은 프로젝트 관리 페이지에서">
					{#snippet right()}
						<a href="/admin/projects" class="text-xs hover:underline" style="color: var(--admin-tone);">전체 보기 →</a>
					{/snippet}
				</SectionHeader>
				{#if !data?.recent_projects || data.recent_projects.length === 0}
					<div class="mt-6 text-center text-sm py-6" style="color: var(--color-ink-3);">프로젝트 없음</div>
				{:else}
					<div class="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
						{#each data.recent_projects as p}
							<a href="/admin/projects/{p.id}"
							   class="block p-4 rounded-xl border transition-colors hover:border-[var(--admin-ring)]"
							   style="background: var(--color-surface-canvas); border-color: var(--color-line);">
								<div class="flex items-center gap-2.5 mb-2">
									<div class="w-9 h-9 rounded-[9px] flex items-center justify-center font-bold text-xs border shrink-0"
									     style="background: color-mix(in oklab, var(--color-accent) 14%, transparent);
									            border-color: color-mix(in oklab, var(--color-accent) 30%, transparent);
									            color: var(--color-accent);">
										{p.name.slice(0, 2).toUpperCase()}
									</div>
									<div class="flex-1 min-w-0">
										<div class="font-semibold text-sm truncate" style="color: var(--color-ink-0);">{p.name}</div>
										<div class="text-[10px] font-mono mt-0.5 truncate" style="color: var(--color-ink-3);">{p.id.slice(0, 8)}</div>
									</div>
									{#if !p.enabled}
										<Pill tone="neutral">비활성</Pill>
									{/if}
								</div>
								{#if p.description}
									<p class="text-xs truncate" style="color: var(--color-ink-2);">{p.description}</p>
								{/if}
								<div class="flex gap-1.5 mt-3 pt-2 border-t" style="border-color: var(--color-line);">
									<span class="flex-1 text-center px-2 py-1 rounded-md text-[11px] border"
									      style="background: var(--admin-soft); color: var(--admin-tone); border-color: var(--admin-ring);">
										쿼터 조정
									</span>
								</div>
							</a>
						{/each}
					</div>
				{/if}
				<div class="mt-4 pt-3 border-t flex justify-end" style="border-color: var(--color-line);">
					<a href="/admin/projects" class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors hover:opacity-80"
					   style="background: var(--admin-soft); color: var(--admin-tone); border-color: var(--admin-ring);">
						전체 프로젝트 관리 →
					</a>
				</div>
			</div>

		{:else}
			<!-- roles tab -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<SectionHeader title="역할 관리">
					{#snippet right()}
						<a href="/admin/roles" class="text-xs hover:underline" style="color: var(--admin-tone);">전체 보기 →</a>
					{/snippet}
				</SectionHeader>
				<div class="mt-4 text-sm text-center py-8" style="color: var(--color-ink-3);">
					역할 세부 정보는
					<a href="/admin/roles" class="underline" style="color: var(--admin-tone);">역할 관리 페이지</a>에서 확인하세요
				</div>
				<div class="grid grid-cols-2 gap-2 mt-2">
					{#each [
						{ href: '/admin/users',   label: '사용자 관리', desc: '사용자 생성·수정·비활성화' },
						{ href: '/admin/projects',label: '프로젝트 관리',desc: '쿼터 조정·프로젝트 생성' },
						{ href: '/admin/roles',   label: '역할 관리',  desc: '역할 정의 및 권한 조정' },
						{ href: '/admin/groups',  label: '그룹 관리',  desc: '그룹 멤버 구성' },
					] as link}
						<a href={link.href}
						   class="p-3 rounded-xl border transition-colors hover:border-[var(--admin-ring)]"
						   style="background: var(--color-surface-canvas); border-color: var(--color-line);">
							<div class="text-sm font-medium" style="color: var(--color-ink-0);">{link.label}</div>
							<div class="text-xs mt-0.5" style="color: var(--color-ink-3);">{link.desc}</div>
						</a>
					{/each}
				</div>
			</div>
		{/if}
	{/if}
</div>
