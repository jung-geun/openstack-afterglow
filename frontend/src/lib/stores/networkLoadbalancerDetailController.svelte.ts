import { confirmDialog } from '$lib/stores/confirm.svelte';
import { api, ApiError } from '$lib/api/client';
import { goto } from '$app/navigation';
import type { LoadBalancerDetail, Listener, Pool, Member, LbStatusNode } from '$lib/types/resources';
import { toast } from '$lib/stores/toast';

export interface NetworkLbDetailOpts {
  lbId: () => string;
  token: () => string | undefined;
  projectId: () => string | undefined;
}

export function createNetworkLoadbalancerDetailController(opts: NetworkLbDetailOpts) {
  let lb = $state<LoadBalancerDetail | null>(null);
  let listeners = $state<Listener[]>([]);
  let pools = $state<Pool[]>([]);
  let selectedPoolMembers = $state<Member[]>([]);
  let selectedPoolId = $state<string | null>(null);
  let loading = $state(true);
  let error = $state('');
  let saving = $state(false);
  let statusTree = $state<LbStatusNode | null>(null);

  const id = opts.lbId;
  const tok = opts.token;
  const pid = opts.projectId;

  async function fetchAll() {
    loading = true;
    error = '';
    await Promise.allSettled([
      api.get<LoadBalancerDetail>(`/api/loadbalancers/${id()}`, tok(), pid())
        .then(v => {
          lb = v;
          loading = false;
          if (v.status === 'ERROR') {
            api.get<LbStatusNode>(`/api/loadbalancers/${id()}/status`, tok(), pid())
              .then(tree => { statusTree = tree; })
              .catch(() => {});
          }
        })
        .catch(e => { error = e instanceof ApiError ? e.message : '조회 실패'; loading = false; }),
      api.get<Listener[]>(`/api/loadbalancers/${id()}/listeners`, tok(), pid())
        .then(v => { listeners = v; }).catch(() => {}),
      api.get<Pool[]>(`/api/loadbalancers/${id()}/pools`, tok(), pid())
        .then(v => { pools = v; }).catch(() => {}),
    ]);
    loading = false;
  }

  async function loadPoolMembers() {
    if (!selectedPoolId) { selectedPoolMembers = []; return; }
    api.get<Member[]>(`/api/loadbalancers/${id()}/pools/${selectedPoolId}/members`, tok(), pid())
      .then(m => { selectedPoolMembers = m; })
      .catch(() => {});
  }

  async function createListener(form: { protocol: string; protocol_port: number; name: string }): Promise<boolean> {
    saving = true;
    try {
      await api.post(`/api/loadbalancers/${id()}/listeners`, form, tok(), pid());
      await fetchAll();
      return true;
    } catch (e) {
      toast.error('리스너 생성 실패: ' + (e instanceof ApiError ? e.message : String(e)));
      return false;
    } finally { saving = false; }
  }

  async function deleteListener(listenerId: string): Promise<void> {
    if (!await confirmDialog('리스너를 삭제하시겠습니까?')) return;
    saving = true;
    try {
      await api.delete(`/api/loadbalancers/${id()}/listeners/${listenerId}`, tok(), pid());
      await fetchAll();
    } catch (e) {
      toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally { saving = false; }
  }

  async function createPool(form: { protocol: string; lb_algorithm: string; name: string }): Promise<boolean> {
    saving = true;
    try {
      await api.post(`/api/loadbalancers/${id()}/pools`, form, tok(), pid());
      await fetchAll();
      return true;
    } catch (e) {
      toast.error('풀 생성 실패: ' + (e instanceof ApiError ? e.message : String(e)));
      return false;
    } finally { saving = false; }
  }

  async function deletePool(poolId: string): Promise<void> {
    if (!await confirmDialog('풀을 삭제하시겠습니까?')) return;
    saving = true;
    try {
      await api.delete(`/api/loadbalancers/${id()}/pools/${poolId}`, tok(), pid());
      if (selectedPoolId === poolId) selectedPoolId = null;
      await fetchAll();
    } catch (e) {
      toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally { saving = false; }
  }

  async function addMember(form: { address: string; protocol_port: number; weight: number; name: string }): Promise<boolean> {
    if (!selectedPoolId) return false;
    saving = true;
    try {
      await api.post(`/api/loadbalancers/${id()}/pools/${selectedPoolId}/members`, form, tok(), pid());
      selectedPoolMembers = await api.get<Member[]>(`/api/loadbalancers/${id()}/pools/${selectedPoolId}/members`, tok(), pid());
      return true;
    } catch (e) {
      toast.error('멤버 추가 실패: ' + (e instanceof ApiError ? e.message : String(e)));
      return false;
    } finally { saving = false; }
  }

  async function removeMember(memberId: string): Promise<void> {
    if (!selectedPoolId || !await confirmDialog('멤버를 제거하시겠습니까?')) return;
    saving = true;
    try {
      await api.delete(`/api/loadbalancers/${id()}/pools/${selectedPoolId}/members/${memberId}`, tok(), pid());
      selectedPoolMembers = selectedPoolMembers.filter(m => m.id !== memberId);
    } catch (e) {
      toast.error('제거 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally { saving = false; }
  }

  async function deleteLb() {
    if (!await confirmDialog(`로드밸런서 "${lb?.name || id()}"을 삭제하시겠습니까? (연결된 리스너/풀/멤버도 모두 삭제됩니다)`)) return;
    saving = true;
    try {
      await api.delete(`/api/loadbalancers/${id()}`, tok(), pid());
      goto('/dashboard/network/loadbalancers');
    } catch (e) {
      toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
      saving = false;
    }
  }

  return {
    get lb() { return lb; },
    get listeners() { return listeners; },
    get pools() { return pools; },
    get selectedPoolMembers() { return selectedPoolMembers; },
    get selectedPoolId() { return selectedPoolId; },
    set selectedPoolId(v: string | null) { selectedPoolId = v; },
    get loading() { return loading; },
    get error() { return error; },
    get saving() { return saving; },
    get statusTree() { return statusTree; },
    fetchAll,
    loadPoolMembers,
    createListener,
    deleteListener,
    createPool,
    deletePool,
    addMember,
    removeMember,
    deleteLb,
  };
}
