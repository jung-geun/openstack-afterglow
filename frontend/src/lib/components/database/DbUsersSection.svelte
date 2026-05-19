<script lang="ts">
	import { useDbInstanceDetail } from '$lib/stores/dbInstanceDetail.svelte';
	import type { DbUser } from '$lib/types/database';

	const s = useDbInstanceDetail();

	let showUserForm = $state(false);
	let newUser = $state<{ name: string; password: string; host: string; dbNames: string[] }>({
		name: '', password: '', host: '%', dbNames: []
	});

	async function handleCreateUser() {
		if (!newUser.name.trim() || !newUser.password) return;
		const ok = await s.createUser(newUser);
		if (ok) {
			showUserForm = false;
			newUser = { name: '', password: '', host: '%', dbNames: [] };
		}
	}

	function userKey(u: DbUser) {
		return u.host && u.host !== '%' ? `${u.name}@${u.host}` : u.name;
	}
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
	<div class="flex items-center justify-between mb-3">
		<h2 class="text-sm font-semibold text-white">유저</h2>
		<button onclick={() => { showUserForm = !showUserForm; s.userError = ''; }}
			class="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 px-2 py-1 rounded transition-colors">
			{showUserForm ? '취소' : '+ 추가'}
		</button>
	</div>
	{#if showUserForm}
		<div class="bg-gray-800 rounded-lg p-3 mb-3 space-y-2">
			<input type="text" bind:value={newUser.name} placeholder="username"
				class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
			<input type="password" bind:value={newUser.password} placeholder="비밀번호"
				class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
			<input type="text" bind:value={newUser.host} placeholder="host (예: %, localhost, 10.0.0.%)"
				class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
			{#if s.databases.length > 0}
				<div>
					<div class="text-gray-400 text-xs mb-1.5">DB 접근 권한 (선택)</div>
					<div class="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
						{#each s.databases as db}
							<label class="flex items-center gap-1.5 text-xs text-white bg-gray-700 hover:bg-gray-600 border border-gray-600 px-2 py-1 rounded cursor-pointer">
								<input type="checkbox" bind:group={newUser.dbNames} value={db.name} class="accent-amber-500" />
								{db.name}
							</label>
						{/each}
					</div>
				</div>
			{:else}
				<div class="text-gray-600 text-xs">먼저 데이터베이스를 생성하면 권한을 부여할 수 있습니다</div>
			{/if}
			{#if s.userError}<p class="text-red-400 text-xs">{s.userError}</p>{/if}
			<button onclick={handleCreateUser} disabled={s.creatingUser || !newUser.name.trim() || !newUser.password}
				class="text-xs bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 disabled:text-gray-500 text-white px-3 py-1.5 rounded transition-colors">
				{s.creatingUser ? '생성 중...' : '생성'}
			</button>
		</div>
	{/if}
	{#if s.users.length === 0}
		<div class="text-gray-600 text-xs">유저가 없습니다</div>
	{:else}
		<div class="space-y-1">
			{#each s.users as u (u.name + '@' + u.host)}
				<div class="flex items-center justify-between py-1.5 border-b border-gray-800/50">
					<div>
						<span class="text-white text-sm font-medium font-mono">
							{u.name}<span class="text-gray-500">@{u.host || '%'}</span>
						</span>
						{#if u.databases?.length}
							<span class="text-gray-500 text-xs ml-2">{u.databases.map(d => d.name).join(', ')}</span>
						{/if}
					</div>
					<button onclick={() => s.deleteUser(u)} disabled={s.deletingUser === userKey(u)}
						class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-red-900 hover:border-red-700 transition-colors">
						{s.deletingUser === userKey(u) ? '...' : '삭제'}
					</button>
				</div>
			{/each}
		</div>
	{/if}
</div>
