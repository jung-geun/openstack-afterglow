import { getContext, setContext, untrack } from 'svelte';
import { api, ApiError } from '$lib/api/client';
import type {
  LoadBalancerDetail,
  Listener,
  Pool,
  Member,
  LbStatusNode,
} from '$lib/types/resources';

export function provisioningColor(status: string): string {
  return status === 'ERROR' ? 'text-red-400' : 'text-gray-400';
}

export interface LoadBalancerDetailOpts {
  lbId: () => string;
  token: () => string | undefined;
  projectId: () => string | undefined;
  onDeleted?: () => void;
  onClose?: () => void;
}

export function createLoadBalancerDetailStore(opts: LoadBalancerDetailOpts) {
  let lb = $state<LoadBalancerDetail | null>(null);
  let listeners = $state<Listener[]>([]);
  let pools = $state<Pool[]>([]);
  let selectedPoolMembers = $state<Member[]>([]);
  let statusTree = $state<LbStatusNode | null>(null);
  let selectedPoolId = $state<string | null>(null);
  let loading = $state(true);
  let error = $state('');
  let saving = $state(false);

  let showAddListener = $state(false);
  let listenerForm = $state({ protocol: 'HTTP', protocol_port: 80, name: '' });
  let showAddPool = $state(false);
  let poolForm = $state({ protocol: 'HTTP', lb_algorithm: 'ROUND_ROBIN', name: '' });
  let showAddMember = $state(false);
  let memberForm = $state({ address: '', protocol_port: 80, weight: 1, name: '' });

  const isErrored = $derived(
    !!lb && (lb.status === 'ERROR' || lb.status?.includes('ERROR')),
  );

  // selectedPoolId 변화 시 멤버 fetch (token/projectId는 untrack)
  $effect(() => {
    const poolId = selectedPoolId;
    if (!poolId) {
      selectedPoolMembers = [];
      return;
    }
    const t = untrack(() => opts.token());
    const pid = untrack(() => opts.projectId());
    api
      .get<Member[]>(`/api/loadbalancers/${opts.lbId()}/pools/${poolId}/members`, t, pid)
      .then((m) => {
        selectedPoolMembers = m;
      })
      .catch(() => {});
  });

  async function fetchAll() {
    const id = opts.lbId();
    const t = opts.token();
    const pid = opts.projectId();
    loading = true;
    try {
      const [lbData, listenersData, poolsData] = await Promise.all([
        api.get<LoadBalancerDetail>(`/api/loadbalancers/${id}`, t, pid),
        api.get<Listener[]>(`/api/loadbalancers/${id}/listeners`, t, pid),
        api.get<Pool[]>(`/api/loadbalancers/${id}/pools`, t, pid),
      ]);
      lb = lbData;
      listeners = listenersData;
      pools = poolsData;
      error = '';
      if (lbData.status === 'ERROR') {
        api
          .get<LbStatusNode>(`/api/loadbalancers/${id}/status`, t, pid)
          .then((tree) => {
            statusTree = tree;
          })
          .catch(() => {});
      }
    } catch (e) {
      error = e instanceof ApiError ? e.message : '조회 실패';
    } finally {
      loading = false;
    }
  }

  async function createListener() {
    saving = true;
    try {
      await api.post(
        `/api/loadbalancers/${opts.lbId()}/listeners`,
        listenerForm,
        opts.token(),
        opts.projectId(),
      );
      showAddListener = false;
      listenerForm = { protocol: 'HTTP', protocol_port: 80, name: '' };
      await fetchAll();
    } catch (e) {
      alert('리스너 생성 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      saving = false;
    }
  }

  async function deleteListener(listenerId: string) {
    if (!confirm('리스너를 삭제하시겠습니까?')) return;
    saving = true;
    try {
      await api.delete(
        `/api/loadbalancers/${opts.lbId()}/listeners/${listenerId}`,
        opts.token(),
        opts.projectId(),
      );
      await fetchAll();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      saving = false;
    }
  }

  function toggleAddListener() {
    showAddListener = !showAddListener;
  }

  async function createPool() {
    saving = true;
    try {
      await api.post(
        `/api/loadbalancers/${opts.lbId()}/pools`,
        poolForm,
        opts.token(),
        opts.projectId(),
      );
      showAddPool = false;
      poolForm = { protocol: 'HTTP', lb_algorithm: 'ROUND_ROBIN', name: '' };
      await fetchAll();
    } catch (e) {
      alert('풀 생성 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      saving = false;
    }
  }

  async function deletePool(poolId: string) {
    if (!confirm('풀을 삭제하시겠습니까?')) return;
    saving = true;
    try {
      await api.delete(
        `/api/loadbalancers/${opts.lbId()}/pools/${poolId}`,
        opts.token(),
        opts.projectId(),
      );
      if (selectedPoolId === poolId) selectedPoolId = null;
      await fetchAll();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      saving = false;
    }
  }

  function togglePool(id: string) {
    selectedPoolId = selectedPoolId === id ? null : id;
  }

  function toggleAddPool() {
    showAddPool = !showAddPool;
  }

  async function addMember() {
    if (!selectedPoolId) return;
    saving = true;
    try {
      await api.post(
        `/api/loadbalancers/${opts.lbId()}/pools/${selectedPoolId}/members`,
        memberForm,
        opts.token(),
        opts.projectId(),
      );
      showAddMember = false;
      memberForm = { address: '', protocol_port: 80, weight: 1, name: '' };
      selectedPoolMembers = await api.get<Member[]>(
        `/api/loadbalancers/${opts.lbId()}/pools/${selectedPoolId}/members`,
        opts.token(),
        opts.projectId(),
      );
    } catch (e) {
      alert('멤버 추가 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      saving = false;
    }
  }

  async function removeMember(memberId: string) {
    if (!selectedPoolId || !confirm('멤버를 제거하시겠습니까?')) return;
    saving = true;
    try {
      await api.delete(
        `/api/loadbalancers/${opts.lbId()}/pools/${selectedPoolId}/members/${memberId}`,
        opts.token(),
        opts.projectId(),
      );
      selectedPoolMembers = selectedPoolMembers.filter((m) => m.id !== memberId);
    } catch (e) {
      alert('제거 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      saving = false;
    }
  }

  function toggleAddMember() {
    showAddMember = !showAddMember;
  }

  async function deleteLb() {
    const id = opts.lbId();
    if (!confirm(`로드밸런서 "${lb?.name || id}"을 삭제하시겠습니까? (연결된 리스너/풀/멤버도 모두 삭제됩니다)`))
      return;
    saving = true;
    try {
      await api.delete(`/api/loadbalancers/${id}`, opts.token(), opts.projectId());
      opts.onDeleted?.();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
      saving = false;
    }
  }

  return {
    // State getters
    get lb() { return lb; },
    get listeners() { return listeners; },
    get pools() { return pools; },
    get selectedPoolMembers() { return selectedPoolMembers; },
    get statusTree() { return statusTree; },
    get selectedPoolId() { return selectedPoolId; },
    get loading() { return loading; },
    get error() { return error; },
    get saving() { return saving; },
    // Form state (mutable via bind:)
    get showAddListener() { return showAddListener; },
    set showAddListener(v: boolean) { showAddListener = v; },
    get listenerForm() { return listenerForm; },
    get showAddPool() { return showAddPool; },
    set showAddPool(v: boolean) { showAddPool = v; },
    get poolForm() { return poolForm; },
    get showAddMember() { return showAddMember; },
    set showAddMember(v: boolean) { showAddMember = v; },
    get memberForm() { return memberForm; },
    // Derived
    get isErrored() { return isErrored; },
    // Handlers
    fetchAll,
    createListener,
    deleteListener,
    toggleAddListener,
    createPool,
    deletePool,
    togglePool,
    toggleAddPool,
    addMember,
    removeMember,
    toggleAddMember,
    deleteLb,
  };
}

export type LoadBalancerDetailStore = ReturnType<typeof createLoadBalancerDetailStore>;

const LB_DETAIL_KEY = Symbol('lb-detail');

export function provideLoadBalancerDetail(store: LoadBalancerDetailStore) {
  setContext(LB_DETAIL_KEY, store);
}

export function useLoadBalancerDetail(): LoadBalancerDetailStore {
  const store = getContext<LoadBalancerDetailStore | undefined>(LB_DETAIL_KEY);
  if (!store) throw new Error('useLoadBalancerDetail must be called within LoadBalancerDetailPanel');
  return store;
}
