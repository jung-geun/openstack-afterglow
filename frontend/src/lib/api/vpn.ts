import { api } from './client';
import type {
	VpnServer,
	VpnClient,
	VpnClientCreateResult,
	VpnClientCreateRequest,
	VpnClientUpdateRequest,
} from '$lib/types/vpn';

const BASE = '/api/v1/vpn/servers';

export async function listServers(
	token: string | undefined,
	projectId: string | undefined
): Promise<VpnServer[]> {
	return api.get<VpnServer[]>(BASE, token, projectId);
}

export async function createServer(
	name: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<VpnServer> {
	return api.post<VpnServer>(BASE, { name }, token, projectId);
}

export async function getServer(
	serverId: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<VpnServer> {
	return api.get<VpnServer>(`${BASE}/${serverId}`, token, projectId);
}

export async function deleteServer(
	serverId: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<void> {
	return api.delete<void>(`${BASE}/${serverId}`, token, projectId);
}

export async function listClients(
	serverId: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<VpnClient[]> {
	return api.get<VpnClient[]>(`${BASE}/${serverId}/clients`, token, projectId);
}

export async function createClient(
	serverId: string,
	body: VpnClientCreateRequest,
	token: string | undefined,
	projectId: string | undefined
): Promise<VpnClientCreateResult> {
	return api.post<VpnClientCreateResult>(`${BASE}/${serverId}/clients`, body, token, projectId);
}

export async function updateClient(
	serverId: string,
	clientId: string,
	body: VpnClientUpdateRequest,
	token: string | undefined,
	projectId: string | undefined
): Promise<VpnClient> {
	return api.patch<VpnClient>(`${BASE}/${serverId}/clients/${clientId}`, body, token, projectId);
}

export async function deleteClient(
	serverId: string,
	clientId: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<void> {
	return api.delete<void>(`${BASE}/${serverId}/clients/${clientId}`, token, projectId);
}

export async function downloadClientConfig(
	serverId: string,
	clientId: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<{ blob: Blob; filename: string }> {
	return api.downloadBlob(`${BASE}/${serverId}/clients/${clientId}/config`, token, projectId);
}
