import { api } from './client';
import type { K3sInterfaceInfo } from '$lib/types/k3s';

export async function listNodeInterfaces(
	clusterId: string,
	vmId: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<K3sInterfaceInfo[]> {
	return api.get<K3sInterfaceInfo[]>(
		`/api/v1/k3s/clusters/${clusterId}/nodes/${vmId}/interfaces`,
		token,
		projectId
	);
}

export async function attachNodeInterface(
	clusterId: string,
	vmId: string,
	netId: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<K3sInterfaceInfo> {
	return api.post<K3sInterfaceInfo>(
		`/api/v1/k3s/clusters/${clusterId}/nodes/${vmId}/interfaces`,
		{ net_id: netId },
		token,
		projectId
	);
}

export async function detachNodeInterface(
	clusterId: string,
	vmId: string,
	portId: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<void> {
	return api.delete<void>(
		`/api/v1/k3s/clusters/${clusterId}/nodes/${vmId}/interfaces/${portId}`,
		token,
		projectId
	);
}
