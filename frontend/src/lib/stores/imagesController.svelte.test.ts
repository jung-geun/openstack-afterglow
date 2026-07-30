import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '$lib/api/client';
import type { ImageInfo } from '$lib/types/compute';
import { createImagesController } from './imagesController.svelte';

vi.mock('$lib/api/client', () => ({
  ApiError: class ApiError extends Error {},
  api: {
    get: vi.fn(),
    delete: vi.fn(),
    post: vi.fn(),
  },
}));

const images: ImageInfo[] = [
  {
    id: 'ubuntu-latest',
    name: 'ubuntu:latest',
    repository: 'ubuntu',
    tag: 'latest',
    status: 'active',
    os_distro: 'ubuntu',
    updated_at: '2026-07-03T00:00:00Z',
  },
  {
    id: 'ubuntu-2404',
    name: 'ubuntu:24.04',
    repository: 'ubuntu',
    tag: '24.04',
    status: 'active',
    os_distro: 'ubuntu',
    updated_at: '2026-07-02T00:00:00Z',
  },
  {
    id: 'ubuntu-minimal-2404',
    name: 'ubuntu-minimal:24.04',
    repository: 'ubuntu-minimal',
    tag: '24.04',
    status: 'active',
    os_distro: 'ubuntu',
    updated_at: '2026-07-01T00:00:00Z',
  },
  {
    id: 'ubuntu-2404-extended',
    name: 'ubuntu:24.04-extended',
    repository: 'ubuntu',
    tag: '24.04-extended',
    status: 'active',
    os_distro: 'ubuntu',
    updated_at: '2026-07-01T12:00:00Z',
  },
];

describe('createImagesController repository catalog', () => {
  beforeEach(() => vi.clearAllMocks());

  async function createController() {
    vi.mocked(api.get).mockResolvedValue(images);
    const controller = createImagesController({
      token: () => 'token',
      projectId: () => 'project-1',
    });
    await controller.fetchImages();
    return controller;
  }

  it('groups repository tags and puts the newest tag first', async () => {
    const controller = await createController();

    expect(controller.repositoryGroups).toHaveLength(2);
    expect(controller.repositoryGroups[0].repository).toBe('ubuntu');
    expect(controller.repositoryGroups[0].images.map((image) => image.tag)).toEqual([
      'latest',
      '24.04',
      '24.04-extended',
    ]);
    expect(controller.repositoryGroups[0].latest.id).toBe('ubuntu-latest');
  });

  it('keeps the detail view unfiltered while the catalog respects tag filters', async () => {
    const controller = await createController();
    controller.tagFilter = 'latest';

    expect(controller.repositoryGroups).toHaveLength(1);
    expect(controller.repositoryGroups[0].images).toHaveLength(1);
    expect(controller.allRepositoryGroups[0].images).toHaveLength(3);
  });

  it('ranks an exact repository tag reference above a substring match', async () => {
    const controller = await createController();
    controller.searchQuery = 'ubuntu:24.04';

    expect(controller.filteredImages.map((image) => image.id)).toEqual([
      'ubuntu-2404',
      'ubuntu-2404-extended',
    ]);
  });
});
