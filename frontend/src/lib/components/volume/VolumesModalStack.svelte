<script lang="ts">
	import type { Volume } from '$lib/types/volume';
	import VolumeTransferModal from '$lib/components/volume/VolumeTransferModal.svelte';
	import VolumeExtendModal from '$lib/components/volume/VolumeExtendModal.svelte';
	import VolumeBackupModal from '$lib/components/volume/VolumeBackupModal.svelte';
	import VolumeSnapshotModal from '$lib/components/volume/VolumeSnapshotModal.svelte';

	let {
		transferVolumeId,
		transferVolumeName,
		showTransfer,
		extendTarget,
		backupTarget,
		snapshotTarget,
		volumeBackupsEnabled = true,
		volumeSnapshotsEnabled = true,
		onCloseTransfer,
		onTransferred,
		onCloseExtend,
		onExtendSuccess,
		onCloseBackup,
		onCloseSnapshot,
		onSnapshotSuccess,
	}: {
		transferVolumeId: string;
		transferVolumeName: string;
		showTransfer: boolean;
		extendTarget: Volume | null;
		backupTarget: Volume | null;
		snapshotTarget: Volume | null;
		volumeBackupsEnabled?: boolean;
		volumeSnapshotsEnabled?: boolean;
		onCloseTransfer: () => void;
		onTransferred: () => void;
		onCloseExtend: () => void;
		onExtendSuccess: () => void;
		onCloseBackup: () => void;
		onCloseSnapshot: () => void;
		onSnapshotSuccess: () => void;
	} = $props();
</script>

{#if showTransfer}
	<VolumeTransferModal
		volumeId={transferVolumeId}
		volumeName={transferVolumeName}
		onClose={onCloseTransfer}
		onTransferred={onTransferred}
	/>
{/if}

<VolumeExtendModal
	volume={extendTarget}
	onclose={onCloseExtend}
	onsuccess={onExtendSuccess}
/>

{#if volumeBackupsEnabled}
	<VolumeBackupModal
		volume={backupTarget}
		onclose={onCloseBackup}
		onsuccess={onCloseBackup}
	/>
{/if}

{#if volumeSnapshotsEnabled}
	<VolumeSnapshotModal
		volume={snapshotTarget}
		onclose={onCloseSnapshot}
		onsuccess={onSnapshotSuccess}
	/>
{/if}
