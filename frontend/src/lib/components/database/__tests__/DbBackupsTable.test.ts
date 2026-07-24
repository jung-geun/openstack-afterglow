import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import DbBackupsTable from '../DbBackupsTable.svelte';
import type { DbBackup } from '$lib/types/database';

const backups: DbBackup[] = [
  {
    id: 'backup-1', name: 'daily-backup', status: 'COMPLETED', size: 10,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'backup-2', name: 'building-backup', status: 'BUILDING', size: 20,
    created_at: '2026-01-02T00:00:00Z',
  },
];

describe('DbBackupsTable selection', () => {
  it('renders row checkboxes and disables them plus row actions while busy', () => {
    const { container } = render(DbBackupsTable, {
      backups,
      instances: [],
      selectedIds: new Set(['backup-1']),
      selectableIds: new Set(backups.map((backup) => backup.id)),
      selectionDisabled: true,
      onToggleSelect: vi.fn(),
      onToggleAll: vi.fn(),
      onRestore: vi.fn(),
      onDelete: vi.fn(),
    });
    expect(screen.getByLabelText('daily-backup 선택')).toBeTruthy();
    expect(screen.getByLabelText('building-backup 선택')).toBeTruthy();
    expect((container.querySelector('input[aria-label="daily-backup 선택"]') as HTMLInputElement).disabled).toBe(true);
    expect(screen.getAllByRole('button', { name: '복원' }).every((button) => (button as HTMLButtonElement).disabled)).toBe(true);
    expect(screen.getAllByRole('button', { name: '삭제' }).every((button) => (button as HTMLButtonElement).disabled)).toBe(true);
    expect(screen.getByText('1개 선택됨')).toBeTruthy();
  });

  it('reports indeterminate state and invokes callbacks without navigating', async () => {
    const onToggleAll = vi.fn();
    const onToggleSelect = vi.fn();
    const onRestore = vi.fn();
    const onDelete = vi.fn();
    const { container } = render(DbBackupsTable, {
      backups,
      instances: [],
      selectedIds: new Set(['backup-1']),
      selectableIds: new Set(backups.map((backup) => backup.id)),
      onToggleSelect,
      onToggleAll,
      onRestore,
      onDelete,
    });
    const header = container.querySelector('input[aria-label="전체 백업 선택"]') as HTMLInputElement;
    expect(header.indeterminate).toBe(true);
    await fireEvent.click(header);
    expect(onToggleAll).toHaveBeenCalledTimes(1);
    await fireEvent.click(screen.getByLabelText('building-backup 선택'));
    expect(onToggleSelect).toHaveBeenCalledWith('backup-2');
    await fireEvent.click(screen.getAllByRole('button', { name: '복원' })[0]);
    expect(onRestore).toHaveBeenCalledWith(backups[0]);
    await fireEvent.click(screen.getAllByRole('button', { name: '삭제' })[0]);
    expect(onDelete).toHaveBeenCalledWith('backup-1', 'daily-backup', false);
  });
});
