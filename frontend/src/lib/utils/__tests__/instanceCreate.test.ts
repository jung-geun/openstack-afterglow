import { describe, expect, it } from 'vitest';

import {
	isGithubSshEligible,
	isSshAccessReady,
	isUbuntuImage,
	isValidGithubUsername,
	normalizeRequestedInstanceName,
} from '../instanceCreate';

describe('VM creation helpers', () => {
	it('normalizes whitespace runs in the submitted instance name', () => {
		expect(normalizeRequestedInstanceName('  Open Crew\tHub  ')).toBe('Open-Crew-Hub');
		expect(normalizeRequestedInstanceName('   ')).toBeNull();
	});

	it('recognizes Ubuntu from distro metadata without a version allowlist', () => {
		expect(isUbuntuImage({ name: 'custom-image', os_distro: 'ubuntu' })).toBe(true);
		expect(isUbuntuImage({ name: 'Ubuntu 26.04 preview' })).toBe(true);
		expect(isUbuntuImage({ name: 'Rocky Linux 9', os_distro: 'rocky' })).toBe(false);
	});

	it('offers GitHub SSH only for direct Ubuntu images', () => {
		expect(isGithubSshEligible({ adminMode: false, bootSource: 'image', selectedImageIsUbuntu: true })).toBe(true);
		expect(isGithubSshEligible({ adminMode: false, bootSource: 'volume', selectedImageIsUbuntu: true })).toBe(false);
		expect(isGithubSshEligible({ adminMode: true, bootSource: 'image', selectedImageIsUbuntu: true })).toBe(false);
	});

	it('validates GitHub usernames and active SSH access source', () => {
		expect(isValidGithubUsername('octo-cat')).toBe(true);
		expect(isValidGithubUsername('octo--cat')).toBe(false);
		expect(isValidGithubUsername('octo cat')).toBe(false);
		expect(isSshAccessReady({ adminMode: false, sshAccessMode: 'github', keyName: null, githubUsername: 'octocat' })).toBe(true);
		expect(isSshAccessReady({ adminMode: false, sshAccessMode: 'github', keyName: null, githubUsername: 'bad name' })).toBe(false);
	});
});
