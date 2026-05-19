import { api } from './client';
import type { ConfigMapInfo, SecretInfo, CloudShellTicket } from '$lib/types/k3s';

export async function listNamespaces(
	clusterId: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<string[]> {
	return api.get<string[]>(`/api/k3s/clusters/${clusterId}/namespaces`, token, projectId);
}

export async function listConfigMaps(
	clusterId: string,
	namespace: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<ConfigMapInfo[]> {
	return api.get<ConfigMapInfo[]>(
		`/api/k3s/clusters/${clusterId}/configmaps?namespace=${encodeURIComponent(namespace)}`,
		token,
		projectId
	);
}

export async function getConfigMap(
	clusterId: string,
	namespace: string,
	name: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<ConfigMapInfo> {
	return api.get<ConfigMapInfo>(
		`/api/k3s/clusters/${clusterId}/namespaces/${namespace}/configmaps/${name}`,
		token,
		projectId
	);
}

export async function createConfigMap(
	clusterId: string,
	namespace: string,
	payload: { name: string; data: Record<string, string> },
	token: string | undefined,
	projectId: string | undefined
): Promise<ConfigMapInfo> {
	return api.post<ConfigMapInfo>(
		`/api/k3s/clusters/${clusterId}/namespaces/${namespace}/configmaps`,
		payload,
		token,
		projectId
	);
}

export async function updateConfigMap(
	clusterId: string,
	namespace: string,
	name: string,
	payload: { data: Record<string, string> },
	token: string | undefined,
	projectId: string | undefined
): Promise<ConfigMapInfo> {
	return api.put<ConfigMapInfo>(
		`/api/k3s/clusters/${clusterId}/namespaces/${namespace}/configmaps/${name}`,
		payload,
		token,
		projectId
	);
}

export async function deleteConfigMap(
	clusterId: string,
	namespace: string,
	name: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<void> {
	return api.delete<void>(
		`/api/k3s/clusters/${clusterId}/namespaces/${namespace}/configmaps/${name}`,
		token,
		projectId
	);
}

export async function listSecrets(
	clusterId: string,
	namespace: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<SecretInfo[]> {
	return api.get<SecretInfo[]>(
		`/api/k3s/clusters/${clusterId}/secrets?namespace=${encodeURIComponent(namespace)}`,
		token,
		projectId
	);
}

export async function getSecret(
	clusterId: string,
	namespace: string,
	name: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<SecretInfo> {
	return api.get<SecretInfo>(
		`/api/k3s/clusters/${clusterId}/namespaces/${namespace}/secrets/${name}`,
		token,
		projectId
	);
}

export async function createSecret(
	clusterId: string,
	namespace: string,
	payload: { name: string; type: string; data: Record<string, string> },
	token: string | undefined,
	projectId: string | undefined
): Promise<SecretInfo> {
	return api.post<SecretInfo>(
		`/api/k3s/clusters/${clusterId}/namespaces/${namespace}/secrets`,
		payload,
		token,
		projectId
	);
}

export async function updateSecret(
	clusterId: string,
	namespace: string,
	name: string,
	payload: { type: string; data: Record<string, string> },
	token: string | undefined,
	projectId: string | undefined
): Promise<SecretInfo> {
	return api.put<SecretInfo>(
		`/api/k3s/clusters/${clusterId}/namespaces/${namespace}/secrets/${name}`,
		payload,
		token,
		projectId
	);
}

export async function deleteSecret(
	clusterId: string,
	namespace: string,
	name: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<void> {
	return api.delete<void>(
		`/api/k3s/clusters/${clusterId}/namespaces/${namespace}/secrets/${name}`,
		token,
		projectId
	);
}

export async function createShellTicket(
	clusterId: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<CloudShellTicket> {
	return api.post<CloudShellTicket>(
		`/api/k3s/clusters/${clusterId}/shell-ticket`,
		{},
		token,
		projectId
	);
}
