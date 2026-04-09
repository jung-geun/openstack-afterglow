import { writable } from 'svelte/store';

export interface NewVolumeSpec {
	name: string;
	size_gb: number;
}

export interface WizardState {
	step: number;
	imageId: string | null;
	imageName: string | null;
	flavorId: string | null;
	flavorName: string | null;
	libraries: string[];
	strategy: 'prebuilt' | 'dynamic' | null;
	instanceName: string;
	networkId: string | null;
	networkName: string | null;
	authMode: 'keypair' | 'password';
	keyName: string | null;
	adminPassword: string;
	bootVolumeSizeGb: number;
	deleteBootVolumeOnTermination: boolean;
	additionalVolumeIds: string[];
	newVolumes: NewVolumeSpec[];
}

const initial: WizardState = {
	step: 1,
	imageId: null,
	imageName: null,
	flavorId: null,
	flavorName: null,
	libraries: [],
	strategy: null,
	instanceName: '',
	networkId: null,
	networkName: null,
	authMode: 'keypair',
	keyName: null,
	adminPassword: '',
	bootVolumeSizeGb: 20,
	deleteBootVolumeOnTermination: false,
	additionalVolumeIds: [],
	newVolumes: [],
};

export const wizard = writable<WizardState>({ ...initial });

export function resetWizard() {
	wizard.set({ ...initial });
}
