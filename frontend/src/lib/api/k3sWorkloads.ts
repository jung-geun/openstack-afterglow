import { api } from './client';
import type { DeploymentInfo, PodInfo, PodLogResponse, ReplicaSetInfo, ServiceInfo } from '$lib/types/k3s';

export async function listPods(
	clusterId: string,
	namespace: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<PodInfo[]> {
	return api.get<PodInfo[]>(
		`/api/k3s/clusters/${clusterId}/namespaces/${encodeURIComponent(namespace)}/pods`,
		token,
		projectId
	);
}

export async function deletePod(
	clusterId: string,
	namespace: string,
	name: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<void> {
	return api.delete<void>(
		`/api/k3s/clusters/${clusterId}/namespaces/${encodeURIComponent(namespace)}/pods/${encodeURIComponent(name)}`,
		token,
		projectId
	);
}

export async function getPodLog(
	clusterId: string,
	namespace: string,
	name: string,
	opts: { container?: string; tailLines?: number },
	token: string | undefined,
	projectId: string | undefined
): Promise<PodLogResponse> {
	const params = new URLSearchParams();
	if (opts.container) params.set('container', opts.container);
	if (opts.tailLines !== undefined) params.set('tail_lines', String(opts.tailLines));
	const qs = params.toString() ? `?${params.toString()}` : '';
	return api.get<PodLogResponse>(
		`/api/k3s/clusters/${clusterId}/namespaces/${encodeURIComponent(namespace)}/pods/${encodeURIComponent(name)}/log${qs}`,
		token,
		projectId
	);
}

export async function listServices(
	clusterId: string,
	namespace: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<ServiceInfo[]> {
	return api.get<ServiceInfo[]>(
		`/api/k3s/clusters/${clusterId}/namespaces/${encodeURIComponent(namespace)}/services`,
		token,
		projectId
	);
}

export async function deleteService(
	clusterId: string,
	namespace: string,
	name: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<void> {
	return api.delete<void>(
		`/api/k3s/clusters/${clusterId}/namespaces/${encodeURIComponent(namespace)}/services/${encodeURIComponent(name)}`,
		token,
		projectId
	);
}

export async function listDeployments(
	clusterId: string,
	namespace: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<DeploymentInfo[]> {
	return api.get<DeploymentInfo[]>(
		`/api/k3s/clusters/${clusterId}/namespaces/${encodeURIComponent(namespace)}/deployments`,
		token,
		projectId
	);
}

export async function listReplicaSets(
	clusterId: string,
	namespace: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<ReplicaSetInfo[]> {
	return api.get<ReplicaSetInfo[]>(
		`/api/k3s/clusters/${clusterId}/namespaces/${encodeURIComponent(namespace)}/replicasets`,
		token,
		projectId
	);
}

export async function restartDeployment(
	clusterId: string,
	namespace: string,
	name: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<DeploymentInfo> {
	return api.post<DeploymentInfo>(
		`/api/k3s/clusters/${clusterId}/namespaces/${encodeURIComponent(namespace)}/deployments/${encodeURIComponent(name)}/restart`,
		{},
		token,
		projectId
	);
}

export async function scaleDeployment(
	clusterId: string,
	namespace: string,
	name: string,
	replicas: number,
	token: string | undefined,
	projectId: string | undefined
): Promise<DeploymentInfo> {
	return api.patch<DeploymentInfo>(
		`/api/k3s/clusters/${clusterId}/namespaces/${encodeURIComponent(namespace)}/deployments/${encodeURIComponent(name)}/scale`,
		{ replicas },
		token,
		projectId
	);
}
