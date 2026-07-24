import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import ContainersTable from '../ContainersTable.svelte';
import type { ZunContainer } from '$lib/types/zunContainer';

const containers: ZunContainer[] = [
  {
    uuid: 'running-1', name: 'running', status: 'Running', status_reason: null,
    image: 'alpine', command: null, cpu: 1, memory: '512M', created_at: '2026-01-01T00:00:00Z',
  },
  {
    uuid: 'stopped-1', name: 'stopped', status: 'Stopped', status_reason: null,
    image: 'ubuntu', command: null, cpu: 2, memory: '1G', created_at: '2026-01-02T00:00:00Z',
  },
];

describe('ContainersTable selection', () => {
  it('renders visible row checkboxes and disables selection while a bulk action is busy', () => {
    const { container } = render(ContainersTable, {
      containers,
      selectedIds: new Set(['stopped-1']),
      selectableIds: new Set(containers.map((item) => item.uuid)),
      selectionDisabled: true,
      onToggleSelect: vi.fn(),
      onToggleAll: vi.fn(),
      onOpen: vi.fn(),
      onStart: vi.fn(),
      onStop: vi.fn(),
      onDelete: vi.fn(),
    });

    expect(screen.getByLabelText('running 선택')).toBeTruthy();
    expect(screen.getByLabelText('stopped 선택')).toBeTruthy();
    expect((container.querySelector('input[aria-label="running 선택"]') as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByText('1개 선택됨')).toBeTruthy();
  });

  it('marks the header indeterminate and toggles only selectable rows', async () => {
    const onToggleAll = vi.fn();
    const onToggleSelect = vi.fn();
    const { container } = render(ContainersTable, {
      containers,
      selectedIds: new Set(['stopped-1']),
      selectableIds: new Set(containers.map((item) => item.uuid)),
      onToggleSelect,
      onToggleAll,
      onOpen: vi.fn(),
      onStart: vi.fn(),
      onStop: vi.fn(),
      onDelete: vi.fn(),
    });

    const header = container.querySelector('input[aria-label="전체 컨테이너 선택"]') as HTMLInputElement;
    expect(header.indeterminate).toBe(true);
    await fireEvent.click(header);
    expect(onToggleAll).toHaveBeenCalledTimes(1);
    await fireEvent.click(screen.getByLabelText('running 선택'));
    expect(onToggleSelect).toHaveBeenCalledWith('running-1');
  });

  it('keeps checkbox activation isolated from detail navigation', async () => {
    const onOpen = vi.fn();
    const onToggleSelect = vi.fn();
    render(ContainersTable, {
      containers,
      selectedIds: new Set<string>(),
      selectableIds: new Set(containers.map((item) => item.uuid)),
      onToggleSelect,
      onToggleAll: vi.fn(),
      onOpen,
      onStart: vi.fn(),
      onStop: vi.fn(),
      onDelete: vi.fn(),
    });

    await fireEvent.click(screen.getByLabelText('running 선택'));
    expect(onToggleSelect).toHaveBeenCalledWith('running-1');
    expect(onOpen).not.toHaveBeenCalled();
  });

  it('opens a container detail when its name is activated', async () => {
    const onOpen = vi.fn();
    render(ContainersTable, {
      containers,
      selectedIds: new Set<string>(),
      selectableIds: new Set(containers.map((item) => item.uuid)),
      onToggleSelect: vi.fn(),
      onToggleAll: vi.fn(),
      onOpen,
      onStart: vi.fn(),
      onStop: vi.fn(),
      onDelete: vi.fn(),
    });

    await fireEvent.click(screen.getByRole('button', { name: 'running' }));
    expect(onOpen).toHaveBeenCalledWith('running-1');
  });
});
