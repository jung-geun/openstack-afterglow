import { api, ApiError } from '$lib/api/client';
import type { Project, Quotas, GpuQuota, GpuDefaultQuota } from '$lib/types/quotas';

export interface AdminQuotasControllerOpts {
  token: () => string | undefined;
  projectId: () => string | undefined;
}

export function createAdminQuotasController(opts: AdminQuotasControllerOpts) {
  let projects = $state<Project[]>([]);
  let selectedProjectId = $state('');
  let selectedProjectName = $state('');
  let projectSearch = $state('');
  let quotas = $state<Quotas | null>(null);
  let loading = $state(true);
  let refreshing = $state(false);
  let quotaLoading = $state(false);
  let saving = $state(false);
  let saveError = $state('');
  let saveSuccess = $state('');
  let gpuAliases = $state<string[]>([]);
  let gpuQuotas = $state<GpuQuota[]>([]);
  let gpuDefaults = $state<GpuDefaultQuota[]>([]);
  let gpuQuotaLoading = $state(false);
  let gpuQuotaError = $state('');
  let gpuDefaultLoading = $state(false);
  let gpuDefaultError = $state('');
  let gpuDefaultSuccess = $state('');

  const gpuQuotaMap = $derived(Object.fromEntries(gpuQuotas.map(q => [q.gpu_type, q])));
  const gpuDefaultMap = $derived(Object.fromEntries(gpuDefaults.map(q => [q.gpu_type, q.limit])));
  const allGpuTypes = $derived(
    [...new Set([...gpuAliases, ...gpuDefaults.map(d => d.gpu_type), ...gpuQuotas.map(q => q.gpu_type)])].sort()
  );

  const tok = opts.token;
  const pid = opts.projectId;

  async function loadProjects() {
    if (projects.length === 0) loading = true;
    else refreshing = true;
    try {
      const res = await api.get<{ id: string; name: string }[]>('/api/admin/projects/names', tok(), pid());
      projects = res || [];
    } catch { projects = []; }
    finally { loading = false; refreshing = false; }
  }

  async function loadGpuAliases() {
    try {
      const res = await api.get<{ aliases: string[] }>('/api/admin/gpu-aliases', tok(), pid());
      gpuAliases = res.aliases ?? [];
    } catch (e) {
      console.warn('[Quotas] GPU alias 로드 실패:', e instanceof ApiError ? e.message : e);
      gpuAliases = [];
    }
  }

  async function loadGpuDefaults() {
    gpuDefaultLoading = true; gpuDefaultError = '';
    try {
      gpuDefaults = await api.get<GpuDefaultQuota[]>('/api/admin/gpu-quotas/defaults', tok(), pid());
    } catch (e) {
      gpuDefaultError = e instanceof ApiError ? e.message : '기본 GPU quota 조회 실패';
      gpuDefaults = [];
    } finally { gpuDefaultLoading = false; }
  }

  async function setGpuDefault(gpuType: string, limit: number) {
    gpuDefaultError = ''; gpuDefaultSuccess = '';
    try {
      await api.put('/api/admin/gpu-quotas/defaults', { gpu_type: gpuType, limit }, tok(), pid());
      gpuDefaultSuccess = '기본 GPU quota 저장됨';
      await loadGpuDefaults();
      if (selectedProjectId) await loadGpuQuotas();
    } catch (e) {
      gpuDefaultError = e instanceof ApiError ? e.message : '기본 GPU quota 설정 실패';
    }
  }

  async function loadQuotas() {
    if (!selectedProjectId) { quotas = null; return; }
    quotaLoading = true; saveError = ''; saveSuccess = '';
    try {
      quotas = await api.get<Quotas>(`/api/admin/quotas/${selectedProjectId}`, tok(), pid());
    } catch { quotas = null; }
    finally { quotaLoading = false; }
    await loadGpuQuotas();
  }

  async function loadGpuQuotas() {
    if (!selectedProjectId) { gpuQuotas = []; return; }
    gpuQuotaLoading = true; gpuQuotaError = '';
    try {
      gpuQuotas = await api.get<GpuQuota[]>(`/api/admin/gpu-quotas/${selectedProjectId}`, tok(), pid());
    } catch (e) {
      gpuQuotaError = e instanceof ApiError ? e.message : 'GPU quota 조회 실패';
      gpuQuotas = [];
    } finally { gpuQuotaLoading = false; }
  }

  async function setGpuQuota(gpuType: string, limit: number) {
    if (!selectedProjectId) return;
    gpuQuotaError = '';
    try {
      await api.put(`/api/admin/gpu-quotas/${selectedProjectId}`, { gpu_type: gpuType, limit }, tok(), pid());
      await loadGpuQuotas();
    } catch (e) {
      gpuQuotaError = e instanceof ApiError ? e.message : 'GPU quota 설정 실패';
    }
  }

  async function deleteGpuQuota(gpuType: string) {
    if (!selectedProjectId) return;
    try {
      await api.delete(`/api/admin/gpu-quotas/${selectedProjectId}/${encodeURIComponent(gpuType)}`, tok(), pid());
      await loadGpuQuotas();
    } catch (e) {
      gpuQuotaError = e instanceof ApiError ? e.message : 'GPU quota 삭제 실패';
    }
  }

  async function saveQuotas(form: { instances: number; cores: number; ram: number; volumes: number; gigabytes: number }) {
    if (!selectedProjectId) return;
    saving = true; saveError = ''; saveSuccess = '';
    try {
      await api.put(`/api/admin/quotas/${selectedProjectId}`, form, tok(), pid());
      saveSuccess = '저장되었습니다';
      await loadQuotas();
    } catch (e) { saveError = e instanceof ApiError ? e.message : '저장 실패'; }
    finally { saving = false; }
  }

  return {
    get projects() { return projects; },
    get selectedProjectId() { return selectedProjectId; },
    set selectedProjectId(v: string) { selectedProjectId = v; },
    get selectedProjectName() { return selectedProjectName; },
    set selectedProjectName(v: string) { selectedProjectName = v; },
    get projectSearch() { return projectSearch; },
    set projectSearch(v: string) { projectSearch = v; },
    get quotas() { return quotas; },
    get loading() { return loading; },
    get refreshing() { return refreshing; },
    get quotaLoading() { return quotaLoading; },
    get saving() { return saving; },
    get saveError() { return saveError; },
    get saveSuccess() { return saveSuccess; },
    get gpuQuotaMap() { return gpuQuotaMap; },
    get gpuDefaultMap() { return gpuDefaultMap; },
    get allGpuTypes() { return allGpuTypes; },
    get gpuQuotaLoading() { return gpuQuotaLoading; },
    get gpuQuotaError() { return gpuQuotaError; },
    get gpuDefaultLoading() { return gpuDefaultLoading; },
    get gpuDefaultError() { return gpuDefaultError; },
    get gpuDefaultSuccess() { return gpuDefaultSuccess; },
    get gpuQuotas() { return gpuQuotas; },
    loadProjects,
    loadGpuAliases,
    loadGpuDefaults,
    loadQuotas,
    loadGpuQuotas,
    setGpuDefault,
    setGpuQuota,
    deleteGpuQuota,
    saveQuotas,
  };
}
