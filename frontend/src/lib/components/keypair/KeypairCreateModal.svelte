<script lang="ts">
	let {
		open = $bindable(),
		onCreate,
	}: {
		open: boolean;
		onCreate: (form: { name: string; public_key: string }) => Promise<{ private_key?: string } | string>;
	} = $props();

	let form = $state({ name: '', public_key: '' });
	let creating = $state(false);
	let error = $state('');
	let createdPrivateKey = $state<string | null>(null);

	$effect(() => {
		if (!open) {
			form = { name: '', public_key: '' };
			error = '';
			creating = false;
			createdPrivateKey = null;
		}
	});

	function handleFileUpload(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		if (file.size > 65536) {
			error = '파일이 너무 큽니다 (최대 64KB)';
			input.value = '';
			return;
		}
		const reader = new FileReader();
		reader.onload = (e) => {
			const content = ((e.target?.result as string) ?? '').trim();
			if (content && !/^(ssh-rsa|ssh-ed25519|ssh-dss|ecdsa-sha2-\S+)\s/.test(content)) {
				error = '유효한 SSH 공개키 형식이 아닙니다 (ssh-rsa, ssh-ed25519 등)';
				return;
			}
			form.public_key = content;
		};
		reader.readAsText(file);
		input.value = '';
	}

	async function submit() {
		if (!form.name.trim()) return;
		creating = true;
		error = '';
		const result = await onCreate({ ...form });
		creating = false;
		if (typeof result === 'string') {
			error = result;
		} else {
			if (result.private_key) {
				createdPrivateKey = result.private_key;
			} else {
				open = false;
			}
		}
	}
</script>

{#if open}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => (open = false)}
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && (open = false)}
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="none"
			onkeydown={(e) => e.stopPropagation()}
		>
			{#if createdPrivateKey}
				<h2 class="text-lg font-semibold text-white mb-3">개인키 다운로드</h2>
				<p class="text-sm text-yellow-300 mb-3">이 키는 다시 표시되지 않습니다. 지금 저장하세요.</p>
				<pre class="bg-gray-800 rounded p-3 text-xs text-green-300 overflow-auto max-h-48 mb-4">{createdPrivateKey}</pre>
				<button onclick={() => (open = false)} class="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors">확인</button>
			{:else}
				<h2 class="text-lg font-semibold text-white mb-5">키페어 생성</h2>
				<div class="space-y-4">
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
							<input bind:value={form.name} type="text" placeholder="my-keypair" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
						</label>
					</div>
					<div>
						<div class="flex items-center justify-between mb-1.5">
							<label for="keypair-pubkey" class="text-xs text-gray-400 uppercase tracking-wide">공개키 (선택 - 비우면 자동 생성)</label>
							<label class="text-xs text-blue-400 hover:text-blue-300 cursor-pointer transition-colors">
								파일 선택
								<input type="file" accept=".pub,.pem,.txt" class="hidden" onchange={handleFileUpload} />
							</label>
						</div>
						<textarea id="keypair-pubkey" bind:value={form.public_key} placeholder="ssh-rsa AAAA..." rows="3" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono resize-none"></textarea>
					</div>
				</div>
				{#if error}<div class="mt-3 text-red-400 text-xs">{error}</div>{/if}
				<div class="flex justify-end gap-3 mt-6">
					<button onclick={() => (open = false)} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
					<button onclick={submit} disabled={creating} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
				</div>
			{/if}
		</div>
	</div>
{/if}
