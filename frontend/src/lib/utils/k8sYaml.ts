import yaml from 'js-yaml';

export interface MaskedKey {
  key: string;
  value: string;
}

export function toConfigMapYaml(
  name: string,
  namespace: string,
  data: Record<string, string>
): string {
  const obj: Record<string, unknown> = {
    apiVersion: 'v1',
    kind: 'ConfigMap',
    metadata: { name: name || '(새 ConfigMap)', namespace },
    data: Object.keys(data).length > 0 ? data : null,
  };
  return yaml.dump(obj, { lineWidth: -1, forceQuotes: false });
}

export function toSecretReadYaml(
  name: string,
  namespace: string,
  type: string,
  data: Record<string, string>
): { text: string; maskedKeys: MaskedKey[] } {
  const maskedKeys: MaskedKey[] = Object.entries(data).map(([key, value]) => ({ key, value }));

  // Replace values with stable placeholder so position tracking is unnecessary
  const placeholderData: Record<string, string> = {};
  for (const key of Object.keys(data)) {
    placeholderData[key] = `__MASK_${key}__`;
  }

  const obj: Record<string, unknown> = {
    apiVersion: 'v1',
    kind: 'Secret',
    type,
    metadata: { name, namespace },
    data: Object.keys(placeholderData).length > 0 ? placeholderData : null,
  };

  const raw = yaml.dump(obj, { lineWidth: -1 });
  const text = raw.replace(/__MASK_(.+?)__/g, '••••••••••');
  return { text, maskedKeys };
}

export function toSecretEditYaml(
  name: string,
  type: string,
  namespace?: string
): string {
  const obj: Record<string, unknown> = {
    apiVersion: 'v1',
    kind: 'Secret',
    type,
    metadata: namespace
      ? { name: name || '(새 Secret)', namespace }
      : { name: name || '(새 Secret)' },
    stringData: {},
  };
  return yaml.dump(obj, { lineWidth: -1 });
}

export function fromConfigMapEditYaml(text: string): Record<string, string> {
  let parsed: unknown;
  try {
    parsed = yaml.load(text);
  } catch (e) {
    throw new Error(`YAML 파싱 오류: ${e instanceof Error ? e.message : e}`);
  }
  if (!parsed || typeof parsed !== 'object') throw new Error('유효하지 않은 YAML');
  const p = parsed as Record<string, unknown>;
  if (p.kind && p.kind !== 'ConfigMap') throw new Error('kind가 ConfigMap이어야 합니다');
  const data = p.data;
  if (data === null || data === undefined) return {};
  if (typeof data !== 'object' || Array.isArray(data)) throw new Error('data 필드가 올바르지 않습니다');
  const result: Record<string, string> = {};
  for (const [k, v] of Object.entries(data as Record<string, unknown>)) {
    result[k] = v === null || v === undefined ? '' : String(v);
  }
  return result;
}

export function fromSecretEditYaml(text: string): Record<string, string> {
  let parsed: unknown;
  try {
    parsed = yaml.load(text);
  } catch (e) {
    throw new Error(`YAML 파싱 오류: ${e instanceof Error ? e.message : e}`);
  }
  if (!parsed || typeof parsed !== 'object') throw new Error('유효하지 않은 YAML');
  const p = parsed as Record<string, unknown>;
  if (p.kind && p.kind !== 'Secret') throw new Error('kind가 Secret이어야 합니다');
  if (p.data) throw new Error('Secret 편집은 data 대신 stringData를 사용하세요 (plain text 입력)');
  const stringData = p.stringData;
  if (stringData === null || stringData === undefined) return {};
  if (typeof stringData !== 'object' || Array.isArray(stringData))
    throw new Error('stringData 필드가 올바르지 않습니다');
  const result: Record<string, string> = {};
  for (const [k, v] of Object.entries(stringData as Record<string, unknown>)) {
    result[k] = v === null || v === undefined ? '' : String(v);
  }
  return result;
}
