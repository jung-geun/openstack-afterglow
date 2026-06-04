export const KNOWN_DISTROS = [
	'ubuntu', 'centos', 'rocky', 'debian', 'fedora-coreos',
	'fedora', 'rhel', 'windows', 'cirros',
];

export const OS_LOGOS: Record<string, string> = {
	ubuntu: '/logos/Ubuntu.png',
	centos: '/logos/CentOS.png',
	fedora: '/logos/Fedora.png',
	'fedora-coreos': '/logos/coreos.png',
	windows: '/logos/Windows.png',
	coreos: '/logos/coreos.png',
};

export const OS_EMOJI: Record<string, string> = {
	rocky: '🪨',
	debian: '🌀',
	rhel: '🔴',
	cirros: '☁️',
};

export const OS_LABELS: Record<string, string> = {
	ubuntu: 'Ubuntu', centos: 'CentOS', rocky: 'Rocky Linux',
	debian: 'Debian', 'fedora-coreos': 'Fedora CoreOS', fedora: 'Fedora',
	rhel: 'RHEL', windows: 'Windows', cirros: 'CirrOS',
};

export function osLabel(distro: string | null): string {
	if (!distro) return '-';
	return OS_LABELS[distro] ?? distro.charAt(0).toUpperCase() + distro.slice(1);
}
