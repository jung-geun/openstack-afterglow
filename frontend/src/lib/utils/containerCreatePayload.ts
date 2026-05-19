import type { EnvVar, PortMapping } from '$lib/types/zunContainer';

export function buildContainerCreatePayload(payload: {
  name: string;
  image: string;
  command: string;
  cpu: number;
  memory: string;
  environment: EnvVar[];
  ports: PortMapping[];
}): Record<string, unknown> {
  const body: Record<string, unknown> = {
    name: payload.name,
    image: payload.image,
    cpu: payload.cpu,
    memory: payload.memory,
  };

  if (payload.command.trim()) body.command = payload.command;

  const envEntries = payload.environment.filter(e => e.key.trim());
  if (envEntries.length > 0) {
    const environment: Record<string, string> = {};
    envEntries.forEach(e => { environment[e.key.trim()] = e.value; });
    body.environment = environment;
  }

  const validPorts = payload.ports.filter(p => p.container_port > 0);
  if (validPorts.length > 0) {
    body.ports = validPorts.map(p => ({
      container_port: p.container_port,
      ...(p.host_port > 0 ? { host_port: p.host_port } : {}),
      protocol: p.protocol,
    }));
  }

  return body;
}
