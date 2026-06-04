export function downloadBlobAs(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function downloadAuthenticated(
  url: string,
  filename: string,
  token: string | undefined,
  projectId: string | undefined,
): Promise<void> {
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (projectId) headers['X-Project-Id'] = projectId;
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`다운로드 실패 (${res.status})`);
  downloadBlobAs(await res.blob(), filename);
}
