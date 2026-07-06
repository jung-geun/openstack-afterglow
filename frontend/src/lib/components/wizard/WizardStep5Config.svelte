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
{#if $wizard.squashfsMode}
<div class="mb-4 p-3 rounded-lg bg-blue-900/20 border border-blue-800/40 text-blue-300 text-xs">
	squashfs 라이브러리 소비 VM은 선택한 레이어의 Glance base image에서 직접 부팅합니다. 루트 디스크 크기와 삭제 옵션은 이 베타 경로에서 적용되지 않습니다.
</div>
{:else if $wizard.bootSource === 'image'}
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

<!-- 파일 스토리지 마운트 -->
{#if s.fileStorages.length > 0}
<div class="mb-4">
	<div class="flex items-center justify-between mb-1.5">
		<label class="block text-[11.5px] font-semibold text-gray-300 tracking-tight">
			파일 스토리지 마운트 <span class="text-[10px] text-gray-500 font-normal px-1.5 py-0.5 rounded-full bg-gray-800">선택</span>
		</label>
		<button
			type="button"
			onclick={() => wizard.update(w => ({ ...w, dataMounts: [...w.dataMounts, { fileStorageId: '', mountPoint: '', readOnly: false }] }))}
			class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
		>+ 추가</button>
	</div>
	{#if $wizard.dataMounts.length === 0}
		<p class="text-[11px] text-gray-500">마운트할 파일 스토리지가 없습니다. "+ 추가"를 눌러 추가하세요.</p>
	{:else}
		<div class="space-y-2">
			{#each $wizard.dataMounts as mount, i}
				<div class="flex gap-2 items-start bg-gray-800/60 rounded-lg p-2.5">
					<div class="flex-1 grid grid-cols-1 @lg/panel:grid-cols-2 gap-2">
						<select
							value={mount.fileStorageId}
							onchange={e => wizard.update(w => {
								const m = [...w.dataMounts];
								m[i] = { ...m[i], fileStorageId: (e.target as HTMLSelectElement).value };
								return { ...w, dataMounts: m };
							})}
							class="bg-gray-700 border border-gray-600 text-gray-200 text-xs rounded px-2 py-1.5 focus:outline-none focus:border-blue-500"
						>
							<option value="">스토리지 선택...</option>
							{#each s.fileStorages.filter(fs => fs.status === 'available') as fs}
								<option value={fs.id}>{fs.name || fs.id.slice(0, 12)} ({fs.share_proto})</option>
							{/each}
						</select>
						<input
							type="text"
							value={mount.mountPoint}
							oninput={e => wizard.update(w => {
								const m = [...w.dataMounts];
								m[i] = { ...m[i], mountPoint: (e.target as HTMLInputElement).value };
								return { ...w, dataMounts: m };
							})}
							placeholder="/mnt/mydata"
							class="bg-gray-700 border border-gray-600 text-gray-200 text-xs rounded px-2 py-1.5 focus:outline-none focus:border-blue-500"
						/>
					</div>
					<label class="flex items-center gap-1.5 text-xs text-gray-400 shrink-0 mt-1.5">
						<input
							type="checkbox"
							checked={mount.readOnly}
							onchange={e => wizard.update(w => {
								const m = [...w.dataMounts];
								m[i] = { ...m[i], readOnly: (e.target as HTMLInputElement).checked };
								return { ...w, dataMounts: m };
							})}
							class="w-3.5 h-3.5 rounded border-gray-600 bg-gray-800 text-blue-500"
						/>읽기 전용
					</label>
					<button
						type="button"
						onclick={() => wizard.update(w => ({ ...w, dataMounts: w.dataMounts.filter((_, j) => j !== i) }))}
						class="text-gray-500 hover:text-red-400 transition-colors mt-0.5 shrink-0"
						aria-label="삭제"
					>
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
						</svg>
					</button>
				</div>
			{/each}
		</div>
		<p class="text-[10.5px] text-gray-600 mt-1">/mnt, /data, /srv, /home 하위 경로만 허용됩니다.</p>
	{/if}
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
