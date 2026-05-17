<script lang="ts">
	import { wizard } from '$lib/stores/wizard';
	import { useVmCreate } from '$lib/stores/vmCreateStore.svelte';

	const s = useVmCreate();
</script>

<h2 class="text-lg font-semibold text-white mb-5">인스턴스 설정</h2>

<!-- VM 이름 -->
<div class="mb-4">
	<label for="vm-name" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
		VM 이름 <span class="text-red-400">*</span>
	</label>
	<input
		id="vm-name"
		bind:value={$wizard.instanceName}
		type="text"
		placeholder="my-vm"
		class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
	/>
</div>

<!-- 네트워크 + 키페어 -->
<div class="grid grid-cols-1 @lg/panel:grid-cols-2 gap-3.5 mb-4">
	<div>
		<label for="create-network" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
			네트워크 <span class="text-red-400">*</span>
		</label>
		<select
			id="create-network"
			value={$wizard.networkId ?? ''}
			onchange={e => s.selectNetwork((e.target as HTMLSelectElement).value || null)}
			class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
		>
			<option value="">기본 네트워크</option>
			{#each s.networks as net}
				<option value={net.id}>
					{net.name}{net.id === s.defaultNetworkId ? ' (기본)' : ''}{net.is_external ? ' (외부)' : ''}{net.is_shared ? ' (공유)' : ''}
				</option>
			{/each}
		</select>
	</div>
	<div>
		{#if s.adminMode}
			<label class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
				키페어 <span class="text-[10px] text-gray-500 font-normal px-1.5 py-0.5 rounded-full bg-gray-800">선택</span>
			</label>
			<div class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-gray-500 text-sm">
				없음 (관리자 생성 — 콘솔 비밀번호 사용)
			</div>
			<p class="text-xs text-amber-400/80 mt-1">admin 모드에서는 대상 프로젝트의 키페어에 접근할 수 없습니다.</p>
		{:else}
			<label for="create-keypair" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
				키페어 <span class="text-red-400">*</span>
			</label>
			<select
				id="create-keypair"
				value={$wizard.keyName ?? ''}
				onchange={e => wizard.update(w => ({ ...w, keyName: (e.target as HTMLSelectElement).value || null }))}
				class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
			>
				<option value="">키페어 선택</option>
				{#each s.keypairs as kp}
					<option value={kp.name}>{kp.name}</option>
				{/each}
			</select>
			{#if s.keypairs.length === 0}
				<p class="text-xs text-amber-400 mt-1">등록된 키페어가 없습니다.</p>
			{/if}
		{/if}
	</div>
</div>

<!-- 보안 그룹 + 가용 영역 -->
<div class="grid grid-cols-1 @lg/panel:grid-cols-2 gap-3.5 mb-4">
	<div>
		<label for="create-sg" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
			보안 그룹 <span class="text-[10px] text-gray-500 font-normal px-1.5 py-0.5 rounded-full bg-gray-800">선택</span>
		</label>
		<select
			id="create-sg"
			value={$wizard.securityGroups[0] ?? ''}
			onchange={e => {
				const v = (e.target as HTMLSelectElement).value;
				wizard.update(w => ({ ...w, securityGroups: v ? [v] : [] }));
			}}
			class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
		>
			<option value="">기본</option>
			{#each s.securityGroups as sg}
				<option value={sg.name}>{sg.name}</option>
			{/each}
		</select>
	</div>
	<div>
		<label for="create-az" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
			가용 영역 <span class="text-[10px] text-gray-500 font-normal px-1.5 py-0.5 rounded-full bg-gray-800">선택</span>
		</label>
		<select
			id="create-az"
			value={$wizard.availabilityZone ?? ''}
			onchange={e => {
				const v = (e.target as HTMLSelectElement).value;
				wizard.update(w => ({ ...w, availabilityZone: v || null }));
			}}
			class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
		>
			<option value="">자동 (nova)</option>
			{#each s.availabilityZones as az}
				<option value={az.name}>{az.name}</option>
			{/each}
		</select>
	</div>
</div>

<!-- 루트 디스크 -->
{#if $wizard.bootSource === 'image'}
<div class="grid grid-cols-1 @lg/panel:grid-cols-2 gap-3.5 mb-4">
	<div>
		<label for="boot-volume-size" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
			루트 디스크 <span class="text-red-400">*</span>
		</label>
		<div class="flex items-center gap-3">
			<input
				id="boot-volume-size"
				bind:value={$wizard.bootVolumeSizeGb}
				type="number"
				min="1"
				max="16384"
				class="w-24 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
			/>
			<span class="text-[11px] text-gray-500">1 – 16,384 GB</span>
		</div>
	</div>
	<div class="flex items-end pb-1">
		<label class="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800/60 border border-gray-700 cursor-pointer w-full">
			<input
				type="checkbox"
				bind:checked={$wizard.deleteBootVolumeOnTermination}
				class="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 flex-shrink-0"
			/>
			<span class="text-sm text-gray-300">VM 삭제 시 루트 디스크 함께 삭제</span>
		</label>
	</div>
</div>
{:else}
<div class="mb-4 p-3 rounded-lg bg-blue-900/20 border border-blue-800/40 text-blue-300 text-xs">
	기존 부팅 볼륨 사용 시 루트 디스크 크기 설정이 적용되지 않습니다. 볼륨: <span class="font-medium">{$wizard.bootVolumeName ?? $wizard.bootVolumeId}</span>
</div>
{/if}

<!-- cloud-init 다크 에디터 -->
<div class="mb-4">
	<label for="cloud-init" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
		CLOUD-INIT <span class="text-[10px] text-gray-500 font-normal px-1.5 py-0.5 rounded-full bg-gray-800">선택</span>
	</label>
	<div class="relative">
		<div class="absolute top-2 right-2 flex gap-1 z-[2] bg-gray-900 border border-gray-700 rounded-md p-0.5">
			<button type="button" disabled class="px-2 py-1 text-[10.5px] font-mono text-gray-500 rounded opacity-50 cursor-not-allowed">예제 ▾</button>
			<button type="button" disabled class="px-2 py-1 text-[10.5px] font-mono text-gray-500 rounded opacity-50 cursor-not-allowed">YAML ✓</button>
		</div>
		<textarea
			id="cloud-init"
			bind:value={$wizard.cloudInit}
			rows="8"
			placeholder="#cloud-config&#10;package_update: true&#10;packages:&#10;  - htop"
			class="w-full p-3.5 font-mono text-xs bg-[#0f172a] text-slate-200 rounded-lg border border-gray-700 outline-none min-h-[140px] resize-y leading-relaxed focus:border-blue-500"
		></textarea>
	</div>
</div>
