<script lang="ts">
	let {
		submitting,
		onSubmit,
		onCancel,
	}: {
		submitting: boolean;
		onSubmit: (form: {
			direction: string;
			protocol: string;
			port_range_min: string;
			port_range_max: string;
			remote_ip_prefix: string;
			ethertype: string;
		}) => Promise<string | true>;
		onCancel: () => void;
	} = $props();

	let ruleForm = $state({
		direction: 'ingress',
		protocol: '',
		port_range_min: '',
		port_range_max: '',
		remote_ip_prefix: '',
		ethertype: 'IPv4',
	});
	let error = $state('');

	async function handleSubmit() {
		error = '';
		const result = await onSubmit({ ...ruleForm });
		if (result === true) {
			ruleForm = {
				direction: 'ingress',
				protocol: '',
				port_range_min: '',
				port_range_max: '',
				remote_ip_prefix: '',
				ethertype: 'IPv4',
			};
		} else {
			error = result;
		}
	}

	function handleCancel() {
		error = '';
		onCancel();
	}
</script>

<div class="px-4 pb-3 border-t border-gray-700 pt-3 bg-gray-900/30">
	<p class="text-xs text-gray-500 mb-2">규칙 추가</p>
	<div class="grid grid-cols-2 gap-2 mb-2 md:grid-cols-4">
		<select
			bind:value={ruleForm.direction}
			class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-blue-500"
		>
			<option value="ingress">인바운드</option>
			<option value="egress">아웃바운드</option>
		</select>
		<select
			bind:value={ruleForm.ethertype}
			class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-blue-500"
		>
			<option value="IPv4">IPv4</option>
			<option value="IPv6">IPv6</option>
		</select>
		<select
			bind:value={ruleForm.protocol}
			class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-blue-500"
		>
			<option value="">전체 (Any)</option>
			<option value="tcp">TCP</option>
			<option value="udp">UDP</option>
			<option value="icmp">ICMP</option>
		</select>
		<input
			bind:value={ruleForm.remote_ip_prefix}
			placeholder="원격 IP (예: 0.0.0.0/0)"
			class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
		/>
	</div>
	{#if ruleForm.protocol === 'tcp' || ruleForm.protocol === 'udp'}
		<div class="grid grid-cols-2 gap-2 mb-2 max-w-xs">
			<input
				bind:value={ruleForm.port_range_min}
				placeholder="시작 포트"
				class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
			/>
			<input
				bind:value={ruleForm.port_range_max}
				placeholder="끝 포트"
				class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
			/>
		</div>
	{/if}
	{#if error}
		<p class="text-xs text-red-400 mb-2">{error}</p>
	{/if}
	<div class="flex gap-2">
		<button
			onclick={handleSubmit}
			disabled={submitting}
			class="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600"
		>
			{submitting ? '추가 중...' : '추가'}
		</button>
		<button
			onclick={handleCancel}
			class="text-xs text-gray-400 hover:text-gray-200 px-2 py-1 border border-gray-700 rounded transition-colors"
		>취소</button>
	</div>
</div>
