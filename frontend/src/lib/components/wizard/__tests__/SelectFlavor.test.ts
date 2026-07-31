import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import SelectFlavor from '../SelectFlavor.svelte';

vi.mock('$lib/api/client', () => ({
	api: { get: vi.fn().mockResolvedValue({ gpu_types: [] }) },
}));

const flavors = [
	{ id: 'cpu-1', name: 'cpu.1c_1g', vcpus: 1, ram: 1024, disk: 10, is_public: true },
	{ id: 'gpu-1', name: 'gpu.1c_8g', vcpus: 1, ram: 8192, disk: 40, is_public: false, extra_specs: { 'pci_passthrough:alias': 'RTX-4090:1' } },
];

const quota = {
	instances: { limit: 10, in_use: 2 },
	cores: { limit: 16, in_use: 4 },
	ram: { limit: 32768, in_use: 4096 },
	gigabytes: { limit: 500, in_use: 100 },
};

describe('SelectFlavor', () => {
	it('places quota first and exposes each narrow-panel flavor name without a wide table', () => {
		const onSelect = vi.fn();
		const { container } = render(SelectFlavor, { flavors, selectedId: null, onSelect, quota });

		const quotaHeading = screen.getByText('프로젝트 잔여 쿼터');
		const quotaPanel = quotaHeading.closest('.order-1');
		expect(quotaPanel).not.toBeNull();

		const mobileCards = container.querySelector('[class~="@2xl/panel:hidden"]');
		expect(mobileCards?.textContent).toContain('cpu.1c_1g');
		expect(mobileCards?.textContent).toContain('gpu.1c_8g');
		expect(mobileCards?.textContent).toContain('vCPU');
		expect(mobileCards?.textContent).toContain('Disk');
		expect(container.querySelector('[class~="@2xl/panel:block"]')).not.toBeNull();

		screen.getByRole('button', { name: 'cpu.1c_1g 플레이버 선택' }).click();
		expect(onSelect).toHaveBeenCalledWith('cpu-1', 'cpu.1c_1g');
	});
});
