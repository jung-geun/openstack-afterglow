import { writable } from 'svelte/store';

export const wizardOpen = writable<boolean>(false);

export function openWizard() {
	wizardOpen.set(true);
}

export function closeWizard() {
	wizardOpen.set(false);
}

export interface NewVolumeSpec {
	name: string;
	size_gb: number;
}

export interface WizardState {
	step: number;
	bootSource: 'image' | 'volume';
	imageId: string | null;
	imageName: string | null;
	bootVolumeId: string | null;
	bootVolumeName: string | null;
	flavorId: string | null;
	flavorName: string | null;
	libraries: string[];
	strategy: 'prebuilt' | 'dynamic' | null;
	mountProtocol: 'CEPHFS' | 'NFS';
	templateName: string | null;
	templateVersion: number | null;
	instanceName: string;
	networkId: string | null;
	networkName: string | null;
	keyName: string | null;
	securityGroups: string[];
	availabilityZone: string | null;
	cloudInit: string;
	bootVolumeSizeGb: number;
	deleteBootVolumeOnTermination: boolean;
	additionalVolumeIds: string[];
	newVolumes: NewVolumeSpec[];
}

const initial: WizardState = {
	step: 1,
	bootSource: 'image',
	imageId: null,
	imageName: null,
	bootVolumeId: null,
	bootVolumeName: null,
	flavorId: null,
	flavorName: null,
	libraries: [],
	strategy: null,
	mountProtocol: 'NFS',
	templateName: null,
	templateVersion: null,
	instanceName: '',
	networkId: null,
	networkName: null,
	keyName: null,
	securityGroups: [],
	availabilityZone: null,
	cloudInit: '',
	bootVolumeSizeGb: 20,
	deleteBootVolumeOnTermination: false,
	additionalVolumeIds: [],
	newVolumes: [],
};

export const wizard = writable<WizardState>({ ...initial });

export function resetWizard() {
	wizard.set({ ...initial });
}
