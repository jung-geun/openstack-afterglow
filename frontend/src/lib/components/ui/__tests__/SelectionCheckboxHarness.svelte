<script lang="ts">
	import SelectionCheckbox from '../SelectionCheckbox.svelte';

	interface Props {
		disabled?: boolean;
		onSurfaceClick: () => void;
		onCheckboxClick?: () => void;
	}

	let { disabled = false, onSurfaceClick, onCheckboxClick = () => {} }: Props = $props();
</script>

<div role="button" tabindex="0" onclick={onSurfaceClick} onkeydown={() => {}}>
	<SelectionCheckbox ariaLabel="인스턴스 선택" {disabled} title="선택할 수 없습니다." onclick={onCheckboxClick} />
</div>
