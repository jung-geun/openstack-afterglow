<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { SvelteMap, SvelteSet } from 'svelte/reactivity';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError, getBaseUrl } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import UploadModal from '$lib/components/UploadModal.svelte';
	import { formatStorage, formatDate, shortContentType } from '$lib/utils/format';
	import FileIcon from '$lib/components/ui/FileIcon.svelte';
	import StatTile from '$lib/components/ui/StatTile.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { uploadQueue } from '$lib/stores/uploadQueue';

	interface ObjectItem {
		name: string;
		bytes: number;
		content_type: string;
		last_modified: string;
		etag: string;
		is_dir?: boolean;
	}

	interface ObjectMeta extends ObjectItem {
		container: string;
		content_encoding: string;
		content_disposition: string;
		delete_at: string;
	}

	interface ContainerMeta {
		name: string;
		count: number;
		bytes: number;
	}

	interface ContainerInfo {
		name: string;
		count: number;
		bytes: number;
	}

	const containerName = $derived(decodeURIComponent($page.params.name ?? ''));
	let objects = $state<ObjectItem[]>([]);
	let loading = $state(true);
	let prefix = $state('');
	let deleting = $state<string | null>(null);
	let downloading = $state<string | null>(null);
	let selected = $state<Set<string>>(new Set());
	let bulkDeleting = $state(false);

	// 검색/필터
	let filterText = $state('');
	// 검색 모드: current(현재 폴더) | expanded(펼친 트리) | all(전체 버킷)
	let searchScope = $state<'current' | 'expanded' | 'all'>('current');
	// 정렬
	let sortKey = $state<'name' | 'bytes' | 'last_modified'>('name');
	let sortAsc = $state(true);

	// 트리 펼침 상태 (폴더 prefix는 끝에 "/" 포함)
	let expandedDirs = $state<SvelteSet<string>>(new SvelteSet());
	// prefix별 listing 캐시 (key: 폴더 prefix 끝에 "/" 포함, value: 해당 폴더 직속 항목 배열)
	let dirCache = $state<SvelteMap<string, ObjectItem[]>>(new SvelteMap());
	// 페치 중인 prefix 집합 (스피너용)
	let dirLoading = $state<SvelteSet<string>>(new SvelteSet());
	// searchScope='all' 전용 — 버킷 전체 객체 캐시
	let allObjectsCache = $state<ObjectItem[] | null>(null);
	let allObjectsLoading = $state(false);

	type TreeRow = {
		obj: ObjectItem;
		depth: number;
		isDir: boolean;
		isExpanded: boolean;
		isLoading: boolean;
		fullPath: boolean; // searchScope='all'일 때 풀 경로 표기
	};

	function sortItems(items: ObjectItem[]): ObjectItem[] {
		return [...items].sort((a, b) => {
			const aDir = isDirectory(a) ? 0 : 1;
			const bDir = isDirectory(b) ? 0 : 1;
			if (aDir !== bDir) return aDir - bDir;
			let cmp = 0;
			if (sortKey === 'name') {
				cmp = baseName(a.name).localeCompare(baseName(b.name));
			} else if (sortKey === 'bytes') {
				cmp = (a.bytes || 0) - (b.bytes || 0);
			} else if (sortKey === 'last_modified') {
				cmp = (a.last_modified || '').localeCompare(b.last_modified || '');
			}
			return sortAsc ? cmp : -cmp;
		});
	}

	function baseName(fullName: string): string {
		const stripped = fullName.endsWith('/') ? fullName.slice(0, -1) : fullName;
		const idx = stripped.lastIndexOf('/');
		return idx >= 0 ? stripped.slice(idx + 1) : stripped;
	}

	// 폴더 직속 항목만 추출 (자기 자신 marker 및 하위 디렉토리 소속 파일 제외)
	function directChildren(parentPrefix: string, items: ObjectItem[] | undefined): ObjectItem[] {
		if (!items) return [];
		return items.filter(o => {
			if (o.name === parentPrefix) return false;
			const rel = parentPrefix && o.name.startsWith(parentPrefix) ? o.name.slice(parentPrefix.length) : o.name;
			const check = rel.endsWith('/') ? rel.slice(0, -1) : rel;
			if (check.includes('/')) return false;
			return true;
		});
	}

	function buildTreeRows(
		p: string,
		depth: number,
		effectiveExpanded: Set<string> | SvelteSet<string>,
		matchSet: Set<string> | null
	): TreeRow[] {
		const items = sortItems(directChildren(p, dirCache.get(p)));
		const rows: TreeRow[] = [];
		for (const obj of items) {
			const isDir = isDirectory(obj);
			let children: TreeRow[] = [];
			if (isDir && effectiveExpanded.has(obj.name)) {
				children = buildTreeRows(obj.name, depth + 1, effectiveExpanded, matchSet);
			}
			if (matchSet) {
				const selfMatch = matchSet.has(obj.name);
				if (!selfMatch && children.length === 0) continue;
			}
			const isLoading = isDir && effectiveExpanded.has(obj.name) && dirLoading.has(obj.name) && !dirCache.has(obj.name);
			rows.push({
				obj,
				depth,
				isDir,
				isExpanded: isDir && effectiveExpanded.has(obj.name),
				isLoading,
				fullPath: false,
			});
			rows.push(...children);
		}
		return rows;
	}

	// 매칭된 항목의 모든 조상 prefix를 모음
	function ancestorPrefixes(name: string): string[] {
		const stripped = name.endsWith('/') ? name.slice(0, -1) : name;
		const parts = stripped.split('/').filter(Boolean);
		const result: string[] = [];
		let acc = '';
		for (let i = 0; i < parts.length - 1; i++) {
			acc += parts[i] + '/';
			result.push(acc);
		}
		// 항목이 디렉토리이면 자신도 조상으로 (자식 매칭일 때 자기 자신을 펼치도록)
		if (name.endsWith('/')) result.push(name);
		return result;
	}

	const treeRows = $derived(() => {
		const q = filterText.trim().toLowerCase();
		// 검색 없음: 일반 트리 빌드
		if (!q) {
			return buildTreeRows(prefix, 0, expandedDirs, null);
		}
		// 검색 활성: 모드별 분기
		if (searchScope === 'all') {
			if (!allObjectsCache) return [];
			const matched = allObjectsCache
				.filter(o => o.name.toLowerCase().includes(q))
				.filter(o => !o.name.endsWith('/')); // 폴더 marker는 제외 (검색 결과는 파일 위주)
			return sortItems(matched).map(obj => ({
				obj,
				depth: 0,
				isDir: false,
				isExpanded: false,
				isLoading: false,
				fullPath: true,
			}));
		}
		if (searchScope === 'expanded') {
			// dirCache 모든 항목에서 매칭 → matchSet + ancestorSet
			const matchSet = new Set<string>();
			const ancestorSet = new Set<string>();
			for (const items of dirCache.values()) {
				for (const o of items) {
					if (baseName(o.name).toLowerCase().includes(q)) {
						matchSet.add(o.name);
						for (const a of ancestorPrefixes(o.name)) ancestorSet.add(a);
					}
				}
			}
			const effective = new Set<string>([...expandedDirs, ...ancestorSet]);
			return buildTreeRows(prefix, 0, effective, matchSet);
		}
		// searchScope === 'current': view root 직속만 매칭 (기존 동작)
		const items = sortItems(
			directChildren(prefix, dirCache.get(prefix)).filter(o =>
				baseName(o.name).toLowerCase().includes(q)
			)
		);
		return items.map(obj => ({
			obj,
			depth: 0,
			isDir: isDirectory(obj),
			isExpanded: false,
			isLoading: false,
			fullPath: false,
		}));
	});

	function toggleSort(key: typeof sortKey) {
		if (sortKey === key) { sortAsc = !sortAsc; }
		else { sortKey = key; sortAsc = true; }
	}

	// 업로드 모달
	let showUpload = $state(false);

	// 드래그앤드롭
	let dragActive = $state(false);

	// 디렉토리 생성 모달
	let showNewDir = $state(false);
	let newDirName = $state('');
	let creatingDir = $state(false);
	let dirError = $state('');

	// 이름 변경 모달
	let showRename = $state(false);
	let renameTarget = $state('');
	let renameNew = $state('');
	let renameIsDir = $state(false);
	let renaming = $state(false);
	let renameError = $state('');

	// 이동 모달
	let showMove = $state(false);
	let moveTarget = $state('');
	let moveDest = $state('');
	let moveDestContainer = $state('');
	let moving = $state(false);
	let moveError = $state('');
	let moveContainers = $state<ContainerInfo[]>([]); // 버킷 목록
	let moveDirectories = $state<string[]>([]); // 선택된 버킷의 디렉토리 목록
	let moveLoadingDirs = $state(false);
	let moveSelectedDir = $state(''); // 선택된 디렉토리 경로

	// 일괄 이동 모달
	let showBulkMove = $state(false);
	let bulkMoving = $state(false);

	// 미리보기 패널
	let showPreview = $state(false);
	let previewName = $state('');
	let previewContentType = $state('');
	let previewText = $state('');
	let loadingPreview = $state(false);
	let previewUrl = $state('');

	// 오브젝트 상세
	let selectedMeta = $state<ObjectMeta | null>(null);
	let loadingMeta = $state(false);

	// 컨테이너 메타데이터
	let containerMeta = $state<ContainerMeta | null>(null);

	// 컬럼 리사이즈
	let tableRef = $state<HTMLTableElement | null>(null);
	let colWidths = $state({ name: 38, bytes: 12, type: 16, modified: 16, action: 12 }); // %
	function onResizeStart(e: MouseEvent, col: keyof typeof colWidths) {
		e.preventDefault();
		const startX = e.clientX;
		const startW = colWidths[col];
		const tableW = tableRef?.offsetWidth ?? 800;
		const onMove = (ev: MouseEvent) => {
			const diff = ((ev.clientX - startX) / tableW) * 100;
			colWidths[col] = Math.max(5, startW + diff);
		};
		const onUp = () => {
			document.removeEventListener('mousemove', onMove);
			document.removeEventListener('mouseup', onUp);
		};
		document.addEventListener('mousemove', onMove);
		document.addEventListener('mouseup', onUp);
	}

	async function loadContainerMeta() {
		try {
			containerMeta = await api.get<ContainerMeta>(
				`/api/object-storage/${encodeURIComponent(containerName)}`,
				token, projectId
			);
		} catch { containerMeta = null; }
	}

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	// breadcrumb 세그먼트 계산
	const breadcrumbs = $derived(
		prefix ? prefix.replace(/\/$/, '').split('/').filter(Boolean) : []
	);

	function encObj(name: string) {
		return name.split('/').map(encodeURIComponent).join('/');
	}

	async function fetchDir(p: string): Promise<ObjectItem[]> {
		dirLoading.add(p);
		try {
			const qs = new URLSearchParams({ delimiter: '/' });
			if (p) qs.set('prefix', p);
			const items = await api.get<ObjectItem[]>(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects?${qs}`,
				token, projectId
			);
			dirCache.set(p, items);
			return items;
		} finally {
			dirLoading.delete(p);
		}
	}

	async function load(opts: { silent?: boolean } = {}) {
		if (!opts.silent) loading = true;
		try {
			const items = await fetchDir(prefix);
			objects = items;
		} catch {
			if (!opts.silent) objects = [];
		} finally {
			if (!opts.silent) loading = false;
		}
	}

	async function fetchAllObjects(opts: { silent?: boolean } = {}): Promise<void> {
		if (!opts.silent) allObjectsLoading = true;
		try {
			const qs = new URLSearchParams({ delimiter: '' });
			const items = await api.get<ObjectItem[]>(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects?${qs}`,
				token, projectId
			);
			allObjectsCache = items;
		} catch {
			if (!opts.silent) allObjectsCache = [];
		} finally {
			if (!opts.silent) allObjectsLoading = false;
		}
	}

	// 펼친 모든 prefix를 동시성 4로 병렬 재페치
	async function refreshAll(opts: { silent?: boolean } = {}): Promise<void> {
		if (!opts.silent) loading = true;
		try {
			const queue = [prefix, ...expandedDirs];
			while (queue.length) {
				const batch = queue.splice(0, 4);
				await Promise.all(batch.map(p => fetchDir(p).catch(() => [])));
			}
			objects = dirCache.get(prefix) ?? [];
			if (searchScope === 'all' && filterText.trim()) {
				await fetchAllObjects({ silent: true });
			}
		} catch {
			// 개별 fetchDir 실패는 무시
		} finally {
			if (!opts.silent) loading = false;
		}
	}

	// 캐시된 모든 prefix에서 이름으로 객체 찾기
	function findObject(name: string): ObjectItem | undefined {
		for (const items of dirCache.values()) {
			for (const o of items) {
				if (o.name === name) return o;
			}
		}
		if (allObjectsCache) {
			return allObjectsCache.find(o => o.name === name);
		}
		return undefined;
	}

	async function toggleExpand(dirName: string): Promise<void> {
		if (expandedDirs.has(dirName)) {
			expandedDirs.delete(dirName);
			return;
		}
		expandedDirs.add(dirName);
		if (!dirCache.has(dirName)) {
			try {
				await fetchDir(dirName);
			} catch {
				// 실패 시 펼침 해제
				expandedDirs.delete(dirName);
			}
		}
	}

	function handleDrop(e: DragEvent) {
		const files = Array.from(e.dataTransfer?.files ?? []);
		for (const f of files) {
			uploadQueue.enqueue(f, {
				containerName,
				prefix,
				token,
				projectId,
				onComplete: (job) => { if (job.status === 'success') refreshAll({ silent: true }); }
			});
		}
	}

	function hasFiles(e: DragEvent): boolean {
		const types = e.dataTransfer?.types;
		if (!types) return false;
		for (let i = 0; i < types.length; i++) if (types[i] === 'Files') return true;
		return false;
	}

	function onWindowDragEnter(e: DragEvent) {
		if (!hasFiles(e)) return;
		e.preventDefault();
		dragActive = true;
	}
	function onWindowDragOver(e: DragEvent) {
		if (!hasFiles(e)) return;
		e.preventDefault();
		dragActive = true;
	}
	function onWindowDragLeave(e: DragEvent) {
		if (!hasFiles(e)) return;
		// 뷰포트 바깥으로 나갔을 때만 overlay 해제
		if (e.clientX <= 0 || e.clientY <= 0 || e.clientX >= window.innerWidth || e.clientY >= window.innerHeight) {
			dragActive = false;
		}
	}
	function onWindowDrop(e: DragEvent) {
		if (!hasFiles(e)) return;
		e.preventDefault();
		dragActive = false;
		handleDrop(e);
	}

	function navigatePrefix(newPrefix: string) {
		prefix = newPrefix;
		selectedMeta = null;
		showPreview = false;
		filterText = '';
		searchScope = 'current';
		selected = new Set();
		expandedDirs.clear();
		dirCache.clear();
		allObjectsCache = null;
		load();
	}

	function toggleSelect(name: string) {
		const next = new Set(selected);
		if (next.has(name)) next.delete(name);
		else next.add(name);
		selected = next;
	}

	function toggleSelectAll() {
		const all = treeRows();
		if (selected.size === all.length && all.length > 0) {
			selected = new Set();
		} else {
			selected = new Set(all.map(r => r.obj.name));
		}
	}

	async function bulkDelete() {
		const dirs = [...selected].filter(n => {
			const obj = findObject(n);
			return obj && isDirectory(obj);
		});
		let msg = `${selected.size}개 항목을 삭제하시겠습니까?`;
		if (dirs.length > 0) {
			msg += `\n\n⚠️ ${dirs.length}개 디렉토리 포함 — 하위 파일이 모두 삭제됩니다.`;
		}
		if (!confirm(msg)) return;
		bulkDeleting = true;
		try {
			await api.post(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/bulk-delete`,
				{ objects: [...selected], recursive: true },
				token, projectId
			);
			selected = new Set();
			await refreshAll();
			loadContainerMeta();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			bulkDeleting = false;
		}
	}

	function openDir(dirName: string) {
		navigatePrefix(dirName);
	}

	function breadcrumbPrefix(idx: number) {
		return breadcrumbs.slice(0, idx + 1).join('/') + '/';
	}

	function displayName(fullName: string) {
		if (prefix && fullName.startsWith(prefix)) return fullName.slice(prefix.length);
		return fullName;
	}

	function isDirectory(obj: ObjectItem) {
		return obj.is_dir === true
			|| obj.content_type === 'application/directory'
			|| obj.name.endsWith('/');
	}

	function isPreviewable(contentType: string) {
		return contentType.startsWith('text/') || contentType.startsWith('image/') ||
			contentType === 'application/pdf' || contentType === 'application/json';
	}

	async function downloadObject(name: string) {
		downloading = name;
		try {
			const { url } = await api.post<{ url: string; expires_in: number }>(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/${encObj(name)}/download-token`,
				{},
				token, projectId
			);
			const absoluteUrl = url.startsWith('http') ? url : `${getBaseUrl()}${url}`;
			const a = document.createElement('a');
			a.href = absoluteUrl;
			a.rel = 'noopener';
			document.body.appendChild(a);
			a.click();
			a.remove();
		} catch (e) {
			alert('다운로드 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			downloading = null;
		}
	}

	async function deleteObject(name: string) {
		if (!confirm(`"${displayName(name)}" 오브젝트를 삭제하시겠습니까?`)) return;
		deleting = name;
		try {
			await api.delete(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/${encObj(name)}`,
				token, projectId
			);
			await refreshAll();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = null;
		}
	}

	async function showMeta(name: string) {
		showPreview = false;
		loadingMeta = true; selectedMeta = null;
		try {
			selectedMeta = await api.get<ObjectMeta>(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/${encObj(name)}/metadata`,
				token, projectId
			);
		} catch { /* ignore */ }
		finally { loadingMeta = false; }
	}

	async function openPreview(obj: ObjectItem) {
		selectedMeta = null;
		showPreview = true;
		previewName = obj.name;
		previewContentType = obj.content_type;
		previewText = ''; previewUrl = '';
		loadingPreview = true;
		const base = getBaseUrl();
		const headers: Record<string, string> = {};
		if (token) headers['X-Auth-Token'] = token;
		if (projectId) headers['X-Project-Id'] = projectId;
		const encodedPath = `/api/object-storage/${encodeURIComponent(containerName)}/objects/${encObj(obj.name)}/preview`;
		try {
			if (obj.content_type.startsWith('image/') || obj.content_type === 'application/pdf') {
				const res = await fetch(`${base}${encodedPath}`, { headers });
				const blob = await res.blob();
				previewUrl = URL.createObjectURL(blob);
			} else {
				const res = await fetch(`${base}${encodedPath}`, { headers });
				previewText = await res.text();
			}
		} catch {
			previewText = '미리보기를 불러오지 못했습니다.';
		} finally {
			loadingPreview = false;
		}
	}

	function closePreview() {
		showPreview = false;
		if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = ''; }
	}

	// 디렉토리 생성
	async function createDirectory() {
		if (!newDirName.trim()) { dirError = '폴더 이름을 입력하세요.'; return; }
		creatingDir = true; dirError = '';
		try {
			const path = prefix + newDirName.trim().replace(/\/$/, '') + '/';
			await api.post(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/directory`,
				{ path }, token, projectId
			);
			showNewDir = false; newDirName = '';
			await refreshAll();
		} catch (e) {
			dirError = e instanceof ApiError ? e.message : '폴더 생성 실패';
		} finally {
			creatingDir = false;
		}
	}

	// 이름 변경
	function openRename(name: string) {
		renameTarget = name;
		renameIsDir = isDirectory(findObject(name) ?? { name, bytes: 0, content_type: '', last_modified: '', etag: '' });
		renameNew = displayName(name).replace(/\/$/, '');
		renameError = ''; showRename = true;
	}

	async function doRename() {
		if (!renameNew.trim()) { renameError = '새 이름을 입력하세요.'; return; }
		renaming = true; renameError = '';
		try {
			let newFullName = prefix + renameNew.trim();
			if (renameIsDir) newFullName = newFullName.replace(/\/$/, '') + '/';
			await api.post(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/rename`,
				{ source: renameTarget, new_name: newFullName }, token, projectId
			);
			showRename = false;
			await refreshAll();
		} catch (e) {
			renameError = e instanceof ApiError ? e.message : '이름 변경 실패';
		} finally {
			renaming = false;
		}
	}

	// 이동 — 버킷/디렉토리 로드 함수
	async function loadMoveContainers() {
		try {
			moveContainers = await api.get<ContainerInfo[]>('/api/object-storage', token, projectId);
		} catch {
			moveContainers = [];
		}
	}

	async function loadMoveDirectories(targetContainer: string) {
		moveLoadingDirs = true;
		try {
			const all = await api.get<ObjectItem[]>(
				`/api/object-storage/${encodeURIComponent(targetContainer)}/objects?delimiter=/`,
				token, projectId
			);
			moveDirectories = ['/ (루트)', ...all
				.filter(o => o.is_dir === true || o.content_type === 'application/directory' || o.name.endsWith('/'))
				.map(o => o.name)];
		} catch {
			moveDirectories = ['/ (루트)'];
		} finally {
			moveLoadingDirs = false;
		}
	}

	async function openMove(name: string) {
		moveTarget = name;
		moveDest = '';
		moveDestContainer = containerName;
		moveSelectedDir = '';
		moveError = '';
		showMove = true;
		await Promise.all([
			loadMoveContainers(),
			loadMoveDirectories(containerName),
		]);
	}

	function selectMoveDir(dir: string) {
		// trailing / 제거 후 마지막 세그먼트 추출, 디렉토리면 / 복원
		const stripped = moveTarget.replace(/\/$/, '');
		const baseName = stripped.split('/').pop() || stripped;
		const filename = moveTarget.endsWith('/') ? baseName + '/' : baseName;
		if (dir === '/ (루트)') {
			moveSelectedDir = '';
			moveDest = filename;
		} else {
			moveSelectedDir = dir;
			moveDest = dir + filename;
		}
	}

	async function onMoveContainerChange(newContainer: string) {
		moveDestContainer = newContainer;
		moveSelectedDir = '';
		moveDest = '';
		await loadMoveDirectories(newContainer);
	}

	async function doMove() {
		if (!moveDest.trim()) { moveError = '대상 경로를 선택하세요.'; return; }
		moving = true; moveError = '';
		try {
			await api.post(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/move`,
				{
					source: moveTarget,
					destination: moveDest.trim(),
					dest_container: moveDestContainer || null
				},
				token, projectId
			);
			showMove = false;
			await refreshAll();
		} catch (e) {
			moveError = e instanceof ApiError ? e.message : '이동 실패';
		} finally {
			moving = false;
		}
	}

	async function openBulkMove() {
		moveDest = '';
		moveDestContainer = containerName;
		moveSelectedDir = '';
		moveError = '';
		showBulkMove = true;
		await Promise.all([loadMoveContainers(), loadMoveDirectories(containerName)]);
	}

	async function doBulkMove() {
		if (!moveDest.trim()) { moveError = '대상 경로를 선택하세요.'; return; }
		bulkMoving = true; moveError = '';
		try {
			for (const name of selected) {
				const isDir = isDirectory(findObject(name) ?? { name, bytes: 0, content_type: '', last_modified: '', etag: '' });
				let dest: string;
				if (isDir) {
					const dirname = name.replace(/\/$/, '').split('/').pop() || name;
					dest = moveDest ? moveDest.replace(/\/$/, '') + '/' + dirname + '/' : dirname + '/';
				} else {
					const filename = name.split('/').pop() || name;
					dest = moveDest ? moveDest.replace(/\/$/, '') + '/' + filename : filename;
				}
				await api.post(
					`/api/object-storage/${encodeURIComponent(containerName)}/objects/move`,
					{ source: name, destination: dest, dest_container: moveDestContainer || null },
					token, projectId
				);
			}
			showBulkMove = false;
			selected = new Set();
			await refreshAll();
			loadContainerMeta();
		} catch (e) {
			moveError = e instanceof ApiError ? e.message : '이동 실패';
		} finally {
			bulkMoving = false;
		}
	}

	function sortIcon(key: typeof sortKey) {
		if (sortKey !== key) return '';
		return sortAsc ? '↑' : '↓';
	}

	const ar = createAutoRefresh(() => refreshAll({ silent: true }), {
		storageKey: 'dashboard-bucket-detail',
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60]
	});

	// searchScope 변경 시 'all' 모드면 lazy fetch
	$effect(() => {
		if (searchScope === 'all' && filterText.trim() && allObjectsCache === null && !allObjectsLoading) {
			fetchAllObjects();
		}
	});

	onMount(() => {
		load();
		loadContainerMeta();
	});
</script>

<svelte:window
	ondragenter={onWindowDragEnter}
	ondragover={onWindowDragOver}
	ondragleave={onWindowDragLeave}
	ondrop={onWindowDrop}
/>

{#if dragActive}
	<div class="fixed inset-0 z-50 pointer-events-none flex items-center justify-center bg-indigo-950/40 backdrop-blur-sm border-4 border-dashed border-indigo-500">
		<div class="text-center">
			<svg class="w-16 h-16 mx-auto text-indigo-300 mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
			<p class="text-indigo-100 font-semibold text-xl">{containerName}{prefix ? ` / ${prefix}` : ''} 에 업로드</p>
			<p class="text-indigo-300 text-sm mt-1">파일을 여기에 떨어뜨리세요</p>
		</div>
	</div>
{/if}

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<!-- breadcrumb -->
	<div class="flex items-center gap-1 mb-2 flex-wrap text-sm">
		<a href="/dashboard/object-storage/buckets" class="text-gray-500 hover:text-gray-300 flex items-center gap-1">
			<svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd"/></svg>
			버킷 목록
		</a>
	</div>

	<div class="text-[10px] text-gray-600 uppercase tracking-widest mb-3">OBJECT STORAGE / EXPLORER</div>

	<!-- 컨테이너 헤더 -->
	<div class="flex items-start justify-between mb-4">
		<div>
			<h1 class="text-2xl font-bold text-white">{containerName}</h1>
			{#if containerMeta}
				<p class="text-gray-500 text-xs mt-1">데이터 동기화 완료</p>
			{/if}
		</div>
		{#if containerMeta}
			<div class="flex gap-4 text-center">
				<div class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2">
					<div class="text-[10px] text-gray-500 uppercase tracking-wider">총 용량</div>
					<div class="text-lg font-bold text-white">
						{containerMeta.bytes >= 1073741824
							? (containerMeta.bytes / 1073741824).toFixed(2)
							: containerMeta.bytes >= 1048576
							? (containerMeta.bytes / 1048576).toFixed(1)
							: Math.round(containerMeta.bytes / 1024).toString()}
						<span class="text-xs text-gray-500 font-normal">{containerMeta.bytes >= 1073741824 ? 'GB' : containerMeta.bytes >= 1048576 ? 'MB' : 'KB'}</span>
					</div>
				</div>
				<div class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2">
					<div class="text-[10px] text-gray-500 uppercase tracking-wider">객체 수</div>
					<div class="text-lg font-bold text-white">{containerMeta.count} <span class="text-xs text-gray-500 font-normal">Items</span></div>
				</div>
			</div>
		{/if}
	</div>

	<!-- 현재 경로 (breadcrumb) -->
	<div class="flex items-center gap-1 mb-4 text-sm">
		<button onclick={() => navigatePrefix('')} class="text-indigo-400 hover:text-indigo-300 font-medium">{containerName}</button>
		{#each breadcrumbs as seg, i}
			<svg class="w-3 h-3 text-gray-600 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/></svg>
			<button onclick={() => navigatePrefix(breadcrumbPrefix(i))} class="text-indigo-400 hover:text-indigo-300 font-medium">{seg}</button>
		{/each}
	</div>

	<!-- 툴바: 검색 + 정렬 + 액션 버튼 -->
	<div class="flex items-center gap-2 mb-4 flex-wrap">
		<div class="relative flex-1 min-w-[200px] max-w-xs">
			<svg class="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" viewBox="0 0 20 20" fill="currentColor">
				<path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/>
			</svg>
			<input
				type="text"
				bind:value={filterText}
				placeholder="파일 필터..."
				class="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500 placeholder-gray-600"
			/>
		</div>
		{#if filterText.trim()}
			<select
				bind:value={searchScope}
				title="검색 범위"
				class="text-xs text-gray-300 bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 focus:outline-none focus:border-indigo-500"
			>
				<option value="current">현재 폴더</option>
				<option value="expanded">펼친 트리</option>
				<option value="all">전체 버킷</option>
			</select>
			{#if searchScope === 'all' && allObjectsLoading}
				<span class="text-xs text-gray-500">전체 인덱싱 중...</span>
			{/if}
		{/if}
		<button onclick={() => toggleSort('name')}
			class="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600 transition-colors">
			이름순 {sortIcon('name')}
		</button>
		<div class="flex-1"></div>
		{#if prefix}
			<button
				onclick={() => {
					const parts = prefix.replace(/\/$/, '').split('/');
					parts.pop();
					navigatePrefix(parts.length ? parts.join('/') + '/' : '');
				}}
				class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600"
			>← 상위</button>
		{/if}
		<button onclick={() => { showNewDir = true; newDirName = ''; dirError = ''; }}
			class="text-xs text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 transition-colors px-3 py-1.5 rounded border border-gray-700">새 폴더</button>
		<button onclick={() => { showUpload = true; }}
			class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 transition-colors px-3 py-1.5 rounded border border-indigo-500">+ 업로드</button>
		<AutoRefreshControl
			bind:active={ar.active}
			bind:intervalSeconds={ar.intervalSeconds}
			intervalOptions={ar.intervalOptions}
			refreshing={loading}
			onManualRefresh={() => { refreshAll(); loadContainerMeta(); }}
		/>
	</div>

	<!-- 일괄 삭제 툴바 -->
	{#if selected.size > 0}
		<div class="flex items-center gap-3 mb-3 px-3 py-2 bg-indigo-950/40 border border-indigo-800/50 rounded-lg">
			<span class="text-xs text-indigo-300">{selected.size}개 선택됨</span>
			<div class="flex-1"></div>
			<button onclick={() => selected = new Set()} class="text-xs text-gray-400 hover:text-white transition-colors">선택 해제</button>
			<button onclick={openBulkMove}
				class="text-xs text-white bg-indigo-700 hover:bg-indigo-600 transition-colors px-3 py-1.5 rounded border border-indigo-600">
				선택 이동
			</button>
			<button onclick={bulkDelete} disabled={bulkDeleting}
				class="text-xs text-white bg-red-700 hover:bg-red-600 disabled:bg-gray-700 disabled:text-gray-500 transition-colors px-3 py-1.5 rounded border border-red-600 disabled:border-gray-600">
				{bulkDeleting ? '삭제 중...' : '선택 삭제'}
			</button>
		</div>
	{/if}

	<!-- 업로드 모달 -->
	{#if showUpload}
		<UploadModal {containerName} {prefix} {token} {projectId} onSuccess={() => refreshAll({ silent: true })} onClose={() => { showUpload = false; }} />
	{/if}

	<!-- 새 폴더 모달 -->
	{#if showNewDir}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-sm shadow-2xl">
				<h2 class="text-white font-semibold mb-4">새 폴더 만들기</h2>
				{#if dirError}<p class="text-red-400 text-xs mb-2">{dirError}</p>{/if}
				<input type="text" bind:value={newDirName} placeholder="폴더 이름"
					class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm mb-4 focus:outline-none focus:border-indigo-500"
					onkeydown={(e) => e.key === 'Enter' && createDirectory()} />
				<div class="flex gap-2 justify-end">
					<button onclick={() => { showNewDir = false; }}
						class="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-700">취소</button>
					<button onclick={createDirectory} disabled={creatingDir}
						class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 px-3 py-1.5 rounded border border-indigo-500 disabled:border-gray-600">
						{creatingDir ? '생성 중...' : '만들기'}
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- 이름 변경 모달 -->
	{#if showRename}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-sm shadow-2xl">
				<h2 class="text-white font-semibold mb-1">이름 변경</h2>
				<p class="text-gray-500 text-xs mb-4 break-all">{displayName(renameTarget)}</p>
				{#if renameError}<p class="text-red-400 text-xs mb-2">{renameError}</p>{/if}
				<input type="text" bind:value={renameNew} placeholder="새 이름"
					class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm mb-4 focus:outline-none focus:border-indigo-500"
					onkeydown={(e) => e.key === 'Enter' && doRename()} />
				<div class="flex gap-2 justify-end">
					<button onclick={() => { showRename = false; }}
						class="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-700">취소</button>
					<button onclick={doRename} disabled={renaming}
						class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 px-3 py-1.5 rounded border border-indigo-500 disabled:border-gray-600">
						{renaming ? '변경 중...' : '변경'}
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- 이동 모달 (개선: 버킷 선택 + 디렉토리 브라우저) -->
	{#if showMove}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
			onclick={() => { showMove = false; }} role="dialog" aria-modal="true" tabindex="-1"
			onkeydown={(e) => e.key === 'Escape' && (showMove = false)}>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-md shadow-2xl"
				onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
				<h2 class="text-white font-semibold mb-1">파일 이동</h2>
				<p class="text-indigo-400 text-sm mb-4 break-all">{displayName(moveTarget)}</p>

				{#if moveError}
					<div class="bg-red-900/20 border border-red-800 rounded-lg px-3 py-2 text-red-400 text-xs mb-3">{moveError}</div>
				{/if}

				<!-- 대상 버킷 선택 -->
				<label class="text-gray-400 text-xs mb-1 block font-medium">대상 버킷</label>
				{#if moveContainers.length > 0}
					<select
						value={moveDestContainer}
						onchange={(e) => onMoveContainerChange((e.target as HTMLSelectElement).value)}
						class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white mb-4 focus:outline-none focus:border-indigo-500"
					>
						{#each moveContainers as c}
							<option value={c.name}>{c.name} ({c.count} items)</option>
						{/each}
					</select>
				{:else}
					<input type="text" bind:value={moveDestContainer} placeholder="버킷 이름"
						class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white mb-4 focus:outline-none focus:border-indigo-500" />
				{/if}

				<!-- 대상 디렉토리 선택 -->
				<label class="text-gray-400 text-xs mb-1 block font-medium">대상 디렉토리</label>
				{#if moveLoadingDirs}
					<div class="bg-gray-800 border border-gray-700 rounded-lg p-3 mb-3">
						<p class="text-gray-500 text-xs">디렉토리 목록 로딩 중...</p>
					</div>
				{:else}
					<div class="bg-gray-800 border border-gray-700 rounded-lg max-h-48 overflow-y-auto mb-3">
						{#each moveDirectories.filter(d => d === '/ (루트)' || (d !== moveTarget && !d.startsWith(moveTarget))) as dir}
							{@const isSelected = (dir === '/ (루트)' && moveSelectedDir === '') || dir === moveSelectedDir}
							<button
								onclick={() => selectMoveDir(dir)}
								class="w-full text-left px-3 py-2 text-sm flex items-center gap-2 transition-colors {isSelected ? 'bg-indigo-600/20 text-indigo-300 border-l-2 border-indigo-500' : 'text-gray-300 hover:bg-gray-700/50'}"
							>
								<svg class="w-4 h-4 shrink-0 {isSelected ? 'text-indigo-400' : 'text-amber-400'}" viewBox="0 0 20 20" fill="currentColor">
									<path d="M2 6a2 2 0 012-2h4l2 2h6a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/>
								</svg>
								<span class="truncate">{dir === '/ (루트)' ? '/ (루트)' : dir}</span>
								{#if isSelected}
									<svg class="w-4 h-4 ml-auto text-indigo-400 shrink-0" viewBox="0 0 20 20" fill="currentColor">
										<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
									</svg>
								{/if}
							</button>
						{/each}
						{#if moveDirectories.length <= 1}
							<p class="text-gray-600 text-xs px-3 py-2">디렉토리가 없습니다. 루트로 이동됩니다.</p>
						{/if}
					</div>
				{/if}

				<!-- 최종 경로 미리보기 -->
				{#if moveDest}
					<div class="bg-gray-800/50 border border-gray-700 rounded px-3 py-2 mb-4">
						<p class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">이동 경로</p>
						<p class="text-white text-sm font-mono break-all">{moveDestContainer} / {moveDest}</p>
					</div>
				{/if}

				<div class="flex gap-2 justify-end">
					<button onclick={() => { showMove = false; }}
						class="text-xs text-gray-400 hover:text-white px-4 py-2 rounded-lg border border-gray-700 transition-colors">취소</button>
					<button onclick={doMove} disabled={moving || !moveDest.trim()}
						class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 px-4 py-2 rounded-lg border border-indigo-500 disabled:border-gray-600 transition-colors">
						{moving ? '이동 중...' : '이동'}
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- 일괄 이동 모달 -->
	{#if showBulkMove}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
			onclick={() => { showBulkMove = false; }} role="dialog" aria-modal="true" tabindex="-1"
			onkeydown={(e) => e.key === 'Escape' && (showBulkMove = false)}>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-md shadow-2xl"
				onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
				<h2 class="text-white font-semibold mb-1">일괄 이동</h2>
				<p class="text-indigo-400 text-xs mb-4">{selected.size}개 항목 선택됨</p>

				{#if moveError}
					<div class="bg-red-900/20 border border-red-800 rounded-lg px-3 py-2 text-red-400 text-xs mb-3">{moveError}</div>
				{/if}

				<label class="text-gray-400 text-xs mb-1 block font-medium">대상 버킷</label>
				{#if moveContainers.length > 0}
					<select
						value={moveDestContainer}
						onchange={(e) => onMoveContainerChange((e.target as HTMLSelectElement).value)}
						class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white mb-4 focus:outline-none focus:border-indigo-500"
					>
						{#each moveContainers as c}
							<option value={c.name}>{c.name} ({c.count} items)</option>
						{/each}
					</select>
				{:else}
					<input type="text" bind:value={moveDestContainer} placeholder="버킷 이름"
						class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white mb-4 focus:outline-none focus:border-indigo-500" />
				{/if}

				<label class="text-gray-400 text-xs mb-1 block font-medium">대상 디렉토리</label>
				{#if moveLoadingDirs}
					<div class="bg-gray-800 border border-gray-700 rounded-lg p-3 mb-3">
						<p class="text-gray-500 text-xs">디렉토리 목록 로딩 중...</p>
					</div>
				{:else}
					<div class="bg-gray-800 border border-gray-700 rounded-lg max-h-48 overflow-y-auto mb-3">
						{#each moveDirectories.filter(d => d === '/ (루트)' || ![...selected].some(s => d === s || d.startsWith(s))) as dir}
							{@const isSelected = (dir === '/ (루트)' && moveSelectedDir === '') || dir === moveSelectedDir}
							<button
								onclick={() => selectMoveDir(dir)}
								class="w-full text-left px-3 py-2 text-sm flex items-center gap-2 transition-colors {isSelected ? 'bg-indigo-600/20 text-indigo-300 border-l-2 border-indigo-500' : 'text-gray-300 hover:bg-gray-700/50'}"
							>
								<svg class="w-4 h-4 shrink-0 {isSelected ? 'text-indigo-400' : 'text-amber-400'}" viewBox="0 0 20 20" fill="currentColor">
									<path d="M2 6a2 2 0 012-2h4l2 2h6a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/>
								</svg>
								<span class="truncate">{dir}</span>
								{#if isSelected}
									<svg class="w-4 h-4 ml-auto text-indigo-400 shrink-0" viewBox="0 0 20 20" fill="currentColor">
										<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
									</svg>
								{/if}
							</button>
						{/each}
					</div>
				{/if}

				{#if moveDest}
					<div class="bg-gray-800/50 border border-gray-700 rounded px-3 py-2 mb-4">
						<p class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">이동 위치</p>
						<p class="text-white text-sm font-mono break-all">{moveDestContainer} / {moveDest || '(루트)'}</p>
					</div>
				{/if}

				<div class="flex gap-2 justify-end">
					<button onclick={() => { showBulkMove = false; moveError = ''; }}
						class="text-xs text-gray-400 hover:text-white px-4 py-2 rounded-lg border border-gray-700 transition-colors">취소</button>
					<button onclick={doBulkMove} disabled={bulkMoving || !moveSelectedDir && moveDest === ''}
						class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 px-4 py-2 rounded-lg border border-indigo-500 disabled:border-gray-600 transition-colors">
						{bulkMoving ? '이동 중...' : `${selected.size}개 이동`}
					</button>
				</div>
			</div>
		</div>
	{/if}

	<div class="flex gap-6">
		<!-- 오브젝트 목록 -->
		<div class="flex-1 min-w-0 relative">
			{#if loading}
				<LoadingSkeleton variant="table" rows={5} />
			{:else if treeRows().length === 0}
				<div class="text-gray-600 text-sm py-8 text-center">
					<svg class="w-12 h-12 mx-auto text-gray-700 mb-3" viewBox="0 0 20 20" fill="currentColor"><path d="M2 6a2 2 0 012-2h4l2 2h6a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg>
					{#if filterText.trim()}
						<p>검색 결과가 없습니다</p>
						<p class="text-gray-700 text-xs mt-1">다른 키워드를 입력하거나 검색 범위를 넓혀보세요</p>
					{:else}
						<p>오브젝트가 없습니다</p>
						<p class="text-gray-700 text-xs mt-1">파일을 업로드하거나 새 폴더를 만들어보세요</p>
					{/if}
				</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm table-fixed" bind:this={tableRef}>
						<colgroup>
							<col style="width: 2.5rem" />
							<col style="width: {colWidths.name}%" />
							<col style="width: {colWidths.bytes}%" />
							<col style="width: {colWidths.type}%" />
							<col style="width: {colWidths.modified}%" />
							<col style="width: {colWidths.action}%" />
						</colgroup>
						<thead>
							<tr class="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wide">
								<th class="py-3 px-4 w-10">
									<input type="checkbox"
										checked={selected.size > 0 && selected.size === treeRows().length}
										onchange={toggleSelectAll}
										class="w-3.5 h-3.5 rounded border-gray-600 bg-gray-800 accent-indigo-500 cursor-pointer" />
								</th>
								<th class="text-left py-3 px-4 font-medium relative">
									<button onclick={() => toggleSort('name')} class="hover:text-gray-300 transition-colors">이름 {sortIcon('name')}</button>
									<div class="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-500/40 active:bg-indigo-500/60"
										onmousedown={(e) => onResizeStart(e, 'name')}></div>
								</th>
								<th class="text-left py-3 px-4 font-medium relative">
									<button onclick={() => toggleSort('bytes')} class="hover:text-gray-300 transition-colors">크기 {sortIcon('bytes')}</button>
									<div class="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-500/40 active:bg-indigo-500/60"
										onmousedown={(e) => onResizeStart(e, 'bytes')}></div>
								</th>
								<th class="text-left py-3 px-4 font-medium relative">
									타입
									<div class="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-500/40 active:bg-indigo-500/60"
										onmousedown={(e) => onResizeStart(e, 'type')}></div>
								</th>
								<th class="text-left py-3 px-4 font-medium relative">
									<button onclick={() => toggleSort('last_modified')} class="hover:text-gray-300 transition-colors">수정일 {sortIcon('last_modified')}</button>
									<div class="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-500/40 active:bg-indigo-500/60"
										onmousedown={(e) => onResizeStart(e, 'modified')}></div>
								</th>
								<th class="text-right py-3 px-4 font-medium">액션</th>
							</tr>
						</thead>
						<tbody>
							{#each treeRows() as row (row.obj.name)}
								{@const obj = row.obj}
								{@const isDir = row.isDir}
								{@const rowLabel = row.fullPath ? obj.name : (baseName(obj.name) || obj.name)}
								<tr
									class="group border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors cursor-pointer {selected.has(obj.name) ? 'bg-indigo-950/20' : ''}"
									onclick={(e) => {
										const t = e.target as HTMLElement;
										if (t.closest('button, input, a, label')) return;
										if (isDir && !row.fullPath) {
											openDir(obj.name);
										} else {
											toggleSelect(obj.name);
										}
									}}
								>
									<td class="py-3 px-4">
										<input type="checkbox"
											checked={selected.has(obj.name)}
											onchange={() => toggleSelect(obj.name)}
											class="w-3.5 h-3.5 rounded border-gray-600 bg-gray-800 accent-indigo-500 cursor-pointer" />
									</td>
									<td class="py-3 px-4">
										<div class="flex items-center gap-2.5" style="padding-left: {row.depth * 16}px">
											{#if isDir && !row.fullPath && (!filterText.trim() || searchScope === 'expanded')}
												<button
													onclick={(e) => { e.stopPropagation(); toggleExpand(obj.name); }}
													title={row.isExpanded ? '접기' : '펼치기'}
													class="w-4 h-4 shrink-0 flex items-center justify-center text-gray-500 hover:text-gray-200 transition-colors"
												>
													{#if row.isLoading}
														<svg class="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
															<path d="M12 2a10 10 0 0110 10" stroke-linecap="round"/>
														</svg>
													{:else}
														<svg class="w-3 h-3 transition-transform {row.isExpanded ? 'rotate-90' : ''}" viewBox="0 0 20 20" fill="currentColor">
															<path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/>
														</svg>
													{/if}
												</button>
											{:else}
												<span class="w-4 h-4 shrink-0"></span>
											{/if}
											<FileIcon name={obj.name} contentType={obj.content_type} isDir={isDir} />
											{#if isDir && !row.fullPath}
												<button onclick={() => openDir(obj.name)}
													class="text-white hover:text-indigo-300 text-left truncate max-w-md font-medium hover:underline">
													{rowLabel}
												</button>
											{:else}
												<button onclick={() => showMeta(obj.name)}
													class="text-gray-200 hover:text-white text-left truncate max-w-md hover:underline {row.fullPath ? 'font-mono text-xs' : ''}">
													{rowLabel}
												</button>
											{/if}
										</div>
									</td>
									<td class="py-3 px-4 text-gray-400 whitespace-nowrap">
										{isDir ? '-' : obj.bytes >= 1073741824
											? formatStorage(Math.round(obj.bytes / 1073741824))
											: obj.bytes >= 1048576
											? `${(obj.bytes / 1048576).toFixed(1)} MB`
											: `${(obj.bytes / 1024).toFixed(1)} KB`}
									</td>
									<td
										class="py-3 px-4 text-gray-500 text-xs whitespace-nowrap"
										title={isDir ? 'folder' : obj.content_type || '-'}
									>
										{isDir ? '폴더' : shortContentType(obj.content_type)}
									</td>
									<td class="py-3 px-4 text-gray-500 text-xs whitespace-nowrap">
										{isDir ? '-' : formatDate(obj.last_modified)}
									</td>
									<td class="py-3 px-4 text-right">
										<div class="flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
											{#if !isDir && isPreviewable(obj.content_type)}
												<button onclick={() => openPreview(obj)} title="미리보기"
													class="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors">
													<svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/><path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/></svg>
												</button>
											{/if}
											{#if !isDir}
												<button onclick={() => downloadObject(obj.name)} title="다운로드"
													class="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors">
													<svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
												</button>
											{/if}
											<button onclick={() => openRename(obj.name)} title="이름변경"
												class="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors">
												<svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"/></svg>
											</button>
											<button onclick={() => openMove(obj.name)} title="이동"
												class="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors">
												<svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M8 5a1 1 0 000 2h5.586l-1.293 1.293a1 1 0 001.414 1.414l3-3a1 1 0 000-1.414l-3-3a1 1 0 10-1.414 1.414L13.586 5H8zM12 15a1 1 0 100-2H6.414l1.293-1.293a1 1 0 10-1.414-1.414l-3 3a1 1 0 000 1.414l3 3a1 1 0 001.414-1.414L6.414 15H12z"/></svg>
											</button>
											<button onclick={() => deleteObject(obj.name)} title="삭제"
												class="p-1.5 text-red-400 hover:text-red-300 hover:bg-gray-700 rounded transition-colors">
												<svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
											</button>
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>

		<!-- 오른쪽 패널: 메타데이터 또는 미리보기 -->
		{#if loadingMeta}
			<div class="w-72 shrink-0 bg-gray-900 border border-gray-800 rounded-xl p-4">
				<LoadingSkeleton variant="detail" rows={6} />
			</div>
		{:else if selectedMeta}
			<div class="w-72 shrink-0 bg-gray-900 border border-gray-800 rounded-xl p-4 text-sm">
				<div class="flex items-center justify-between mb-3">
					<h3 class="text-white font-medium text-xs">오브젝트 정보</h3>
					<button onclick={() => selectedMeta = null} class="text-gray-600 hover:text-gray-400 text-xs">✕</button>
				</div>
				<div class="space-y-2">
					<div><div class="text-gray-500 text-xs">이름</div><div class="text-white break-all">{selectedMeta.name}</div></div>
					<div><div class="text-gray-500 text-xs">크기</div><div class="text-white">{selectedMeta.bytes.toLocaleString()} bytes</div></div>
					<div><div class="text-gray-500 text-xs">Content-Type</div><div class="text-white">{selectedMeta.content_type || '-'}</div></div>
					<div><div class="text-gray-500 text-xs">ETag (MD5)</div><div class="text-gray-400 font-mono text-xs break-all">{selectedMeta.etag || '-'}</div></div>
					<div><div class="text-gray-500 text-xs">수정일</div><div class="text-white">{selectedMeta.last_modified ? selectedMeta.last_modified.slice(0, 19) : '-'}</div></div>
					{#if selectedMeta.content_encoding}
						<div><div class="text-gray-500 text-xs">Content-Encoding</div><div class="text-white">{selectedMeta.content_encoding}</div></div>
					{/if}
				</div>
			</div>
		{:else if showPreview}
			<div class="w-96 shrink-0 bg-gray-900 border border-gray-800 rounded-xl p-4 text-sm flex flex-col">
				<div class="flex items-center justify-between mb-3">
					<h3 class="text-white font-medium text-xs truncate flex-1 mr-2">{displayName(previewName)}</h3>
					<button onclick={closePreview} class="text-gray-600 hover:text-gray-400 text-xs shrink-0">✕</button>
				</div>
				{#if loadingPreview}
					<div class="text-gray-500 text-xs">로딩 중...</div>
				{:else if previewContentType.startsWith('image/')}
					<img src={previewUrl} alt={previewName} class="max-w-full rounded object-contain max-h-96" />
				{:else if previewContentType === 'application/pdf'}
					<embed src={previewUrl} type="application/pdf" class="w-full h-96 rounded" />
				{:else}
					<pre class="text-gray-300 text-xs overflow-auto max-h-96 whitespace-pre-wrap break-all bg-gray-950 rounded p-2">{previewText}</pre>
				{/if}
			</div>
		{/if}
	</div>
</div>
