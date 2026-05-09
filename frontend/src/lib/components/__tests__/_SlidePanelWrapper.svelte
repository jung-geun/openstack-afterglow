<script lang="ts">
	import SlidePanel from '../SlidePanel.svelte';

	interface Props {
		onClose: () => void;
		content?: string;
	}

	let { onClose, content = '테스트 내용' }: Props = $props();
</script>

<SlidePanel {onClose}>
	{content}
</SlidePanel>
