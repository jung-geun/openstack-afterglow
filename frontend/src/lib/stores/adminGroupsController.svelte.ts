import { api, ApiError } from '$lib/api/client';
import type { Group, GroupMember, User } from '$lib/types/adminGroup';

export interface AdminGroupsControllerOpts {
  token: () => string | undefined;
  projectId: () => string | undefined;
}

export function createAdminGroupsController(opts: AdminGroupsControllerOpts) {
  let groups = $state<Group[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let showCreate = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let editGroup = $state<Group | null>(null);
  let updating = $state(false);
  let editError = $state('');
  let deleteGroup = $state<Group | null>(null);
  let deleting = $state(false);
  let deleteError = $state('');
  let expandedGroup = $state<string | null>(null);
  let groupMembers = $state<Record<string, GroupMember[]>>({});
  let membersLoading = $state<Record<string, boolean>>({});
  let allUsers = $state<User[]>([]);
  let addMemberError = $state<Record<string, string>>({});
  let addMemberSaving = $state<Record<string, boolean>>({});

  const tok = opts.token;
  const pid = opts.projectId;

  async function load() {
    if (groups.length === 0) loading = true;
    else refreshing = true;
    error = '';
    try {
      const res = await api.get<Group[]>('/api/v1/admin/groups', tok(), pid());
      groups = res;
    } catch (e) {
      error = e instanceof ApiError ? e.message : '그룹 목록 조회 실패';
    } finally { loading = false; refreshing = false; }
  }

  async function loadUsers() {
    if (allUsers.length > 0) return;
    try {
      const res = await api.get<{ items: User[] }>('/api/v1/admin/users?limit=100', tok(), pid());
      allUsers = res.items;
    } catch {}
  }

  async function createGroup(name: string, description: string): Promise<boolean> {
    creating = true; createError = '';
    try {
      await api.post('/api/v1/admin/groups', { name, description: description || null }, tok(), pid());
      await load();
      return true;
    } catch (e) { createError = e instanceof ApiError ? e.message : '생성 실패'; return false; }
    finally { creating = false; }
  }

  async function updateGroup(form: { name: string; description: string }): Promise<boolean> {
    if (!editGroup) return false;
    updating = true; editError = '';
    try {
      await api.patch(`/api/v1/admin/groups/${editGroup.id}`, { name: form.name, description: form.description || null }, tok(), pid());
      await load();
      return true;
    } catch (e) { editError = e instanceof ApiError ? e.message : '수정 실패'; return false; }
    finally { updating = false; }
  }

  async function confirmDelete() {
    if (!deleteGroup) return;
    deleting = true; deleteError = '';
    try {
      await api.delete(`/api/v1/admin/groups/${deleteGroup.id}`, tok(), pid());
      deleteGroup = null;
      await load();
    } catch (e) { deleteError = e instanceof ApiError ? e.message : '삭제 실패'; }
    finally { deleting = false; }
  }

  async function loadGroupMembers(groupId: string) {
    membersLoading = { ...membersLoading, [groupId]: true };
    try {
      const res = await api.get<GroupMember[]>(`/api/v1/admin/groups/${groupId}/users`, tok(), pid());
      groupMembers = { ...groupMembers, [groupId]: res };
    } catch {
      groupMembers = { ...groupMembers, [groupId]: [] };
    } finally {
      membersLoading = { ...membersLoading, [groupId]: false };
    }
  }

  async function toggleMembers(g: Group) {
    if (expandedGroup === g.id) { expandedGroup = null; return; }
    expandedGroup = g.id;
    await loadGroupMembers(g.id);
    await loadUsers();
  }

  async function addMember(groupId: string, userId: string): Promise<boolean> {
    if (!userId) return false;
    addMemberSaving = { ...addMemberSaving, [groupId]: true };
    addMemberError = { ...addMemberError, [groupId]: '' };
    try {
      await api.put(`/api/v1/admin/groups/${groupId}/users/${userId}`, {}, tok(), pid());
      await loadGroupMembers(groupId);
      return true;
    } catch (e) {
      addMemberError = { ...addMemberError, [groupId]: e instanceof ApiError ? e.message : '추가 실패' };
      return false;
    } finally {
      addMemberSaving = { ...addMemberSaving, [groupId]: false };
    }
  }

  async function removeMember(groupId: string, userId: string) {
    try {
      await api.delete(`/api/v1/admin/groups/${groupId}/users/${userId}`, tok(), pid());
      try {
        await loadGroupMembers(groupId);
      } catch {
        // 그룹 멤버십 변경으로 Keystone 토큰이 무효화될 수 있음 — 페이지 새로고침
        window.location.reload();
      }
    } catch {}
  }

  return {
    get groups() { return groups; },
    get loading() { return loading; },
    get refreshing() { return refreshing; },
    get error() { return error; },
    get showCreate() { return showCreate; },
    set showCreate(v: boolean) { showCreate = v; },
    get creating() { return creating; },
    get createError() { return createError; },
    set createError(v: string) { createError = v; },
    get editGroup() { return editGroup; },
    set editGroup(v: Group | null) { editGroup = v; },
    get updating() { return updating; },
    get editError() { return editError; },
    set editError(v: string) { editError = v; },
    get deleteGroup() { return deleteGroup; },
    set deleteGroup(v: Group | null) { deleteGroup = v; },
    get deleting() { return deleting; },
    get deleteError() { return deleteError; },
    set deleteError(v: string) { deleteError = v; },
    get expandedGroup() { return expandedGroup; },
    get groupMembers() { return groupMembers; },
    get membersLoading() { return membersLoading; },
    get allUsers() { return allUsers; },
    get addMemberError() { return addMemberError; },
    get addMemberSaving() { return addMemberSaving; },
    load,
    loadUsers,
    createGroup,
    updateGroup,
    confirmDelete,
    toggleMembers,
    loadGroupMembers,
    addMember,
    removeMember,
  };
}
