<script lang="ts">
	import SlidePanel from '../SlidePanel.svelte';

	interface Props {
		onClose: () => void;
		content?: string;
		dataTour?: string;
	}

	let { onClose, content = '테스트 내용', dataTour }: Props = $props();
</script>

<SlidePanel {onClose} {dataTour}>
	{content}
</SlidePanel>
