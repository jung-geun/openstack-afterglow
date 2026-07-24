import { api } from './client';
import type {
	WaygateServer,
	WaygateClient,
	WaygateClientCreateResult,
	WaygateClientCreateRequest,
	WaygateClientUpdateRequest,
} from '$lib/types/waygate';

const BASE = '/api/v1/waygate/servers';

export async function listServers(
	token: string | undefined,
	projectId: string | undefined
): Promise<WaygateServer[]> {
	return api.get<WaygateServer[]>(BASE, token, projectId);
}

export async function createServer(
	name: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<WaygateServer> {
	return api.post<WaygateServer>(BASE, { name }, token, projectId);
}

export async function getServer(
	serverId: string,
	token: string | undefined,
	projectId: string | undefined
): Promise<WaygateServer> {
	return api.get<WaygateServer>(`${BASE}/${serverId}`, token, projectId);
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
): Promise<WaygateClient[]> {
	return api.get<WaygateClient[]>(`${BASE}/${serverId}/clients`, token, projectId);
}

export async function createClient(
	serverId: string,
	body: WaygateClientCreateRequest,
	token: string | undefined,
	projectId: string | undefined
): Promise<WaygateClientCreateResult> {
	return api.post<WaygateClientCreateResult>(`${BASE}/${serverId}/clients`, body, token, projectId);
}

export async function updateClient(
	serverId: string,
	clientId: string,
	body: WaygateClientUpdateRequest,
	token: string | undefined,
	projectId: string | undefined
): Promise<WaygateClient> {
	return api.patch<WaygateClient>(`${BASE}/${serverId}/clients/${clientId}`, body, token, projectId);
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
