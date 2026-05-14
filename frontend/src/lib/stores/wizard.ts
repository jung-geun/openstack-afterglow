import { writable } from 'svelte/store';

export const wizardOpen = writable<boolean>(false);

export interface WizardOpenOptions {
	targetProjectId?: string;
	prefill?: Partial<WizardState>;
}

export function openWizard(opts?: WizardOpenOptions) {
	if (opts?.targetProjectId !== undefined || opts?.prefill) {
		wizard.update(w => ({
			...w,
			targetProjectId: opts?.targetProjectId ?? null,
			...(opts?.prefill ?? {}),
		}));
	}
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
	scheduling: 'standard' | 'ha';
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
	targetProjectId: string | null;
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
	scheduling: 'standard',
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
	targetProjectId: null,
};

export const wizard = writable<WizardState>({ ...initial });

export function resetWizard() {
	wizard.set({ ...initial });
}
