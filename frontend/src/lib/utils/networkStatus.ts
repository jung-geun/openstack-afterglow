export const networkStatusColor: Record<string, string> = {
  ACTIVE: 'text-green-400 bg-green-900/30',
  DOWN: 'text-red-400 bg-red-900/30',
  BUILD: 'text-yellow-400 bg-yellow-900/30',
};

export function getNetworkStatusClass(status: string): string {
  return networkStatusColor[status] ?? 'text-gray-400 bg-gray-800';
}
