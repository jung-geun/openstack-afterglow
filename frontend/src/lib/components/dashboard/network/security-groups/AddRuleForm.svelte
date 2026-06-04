<script lang="ts">
	let {
		ruleForm = $bindable(),
		adding,
		error,
		onAdd,
		onCancel,
	}: {
		ruleForm: { direction: string; protocol: string; port_range_min: string; port_range_max: string; remote_ip_prefix: string; ethertype: string };
		adding: boolean;
		error: string;
		onAdd: () => Promise<void>;
		onCancel: () => void;
	} = $props();
</script>

<div class="mb-4 p-3.5 bg-[#0B1220] border border-gray-800 rounded-[10px]">
	<p class="text-xs text-gray-500 mb-2.5">규칙 추가</p>
	<div class="grid grid-cols-2 gap-2 mb-2 md:grid-cols-4">
		<select bind:value={ruleForm.direction}
			class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-blue-500">
			<option value="ingress">인바운드</option>
			<option value="egress">아웃바운드</option>
		</select>
		<select bind:value={ruleForm.ethertype}
			class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-blue-500">
			<option value="IPv4">IPv4</option>
			<option value="IPv6">IPv6</option>
		</select>
		<select bind:value={ruleForm.protocol}
			class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-blue-500">
			<option value="">전체 (Any)</option>
			<option value="tcp">TCP</option>
			<option value="udp">UDP</option>
			<option value="icmp">ICMP</option>
		</select>
		<input bind:value={ruleForm.remote_ip_prefix} placeholder="원격 IP (예: 0.0.0.0/0)"
			class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none" />
	</div>
	{#if ruleForm.protocol === 'tcp' || ruleForm.protocol === 'udp'}
		<div class="grid grid-cols-2 gap-2 mb-2 max-w-xs">
			<input bind:value={ruleForm.port_range_min} placeholder="시작 포트"
				class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none" />
			<input bind:value={ruleForm.port_range_max} placeholder="끝 포트"
				class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none" />
		</div>
	{/if}
	{#if error}
		<p class="text-xs text-red-400 mb-2">{error}</p>
	{/if}
	<div class="flex gap-2">
		<button onclick={onAdd} disabled={adding}
			class="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600">
			{adding ? '추가 중...' : '추가'}
		</button>
		<button onclick={onCancel}
			class="text-xs text-gray-400 hover:text-gray-200 px-2 py-1 border border-gray-700 rounded transition-colors">취소</button>
	</div>
</div>
