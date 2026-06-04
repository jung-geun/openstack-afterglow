export interface LayerInfo {
  id: string;
  name: string;
  version: string;
  sealed: boolean;
}

export interface TemplateInfo {
  name: string;
  version: number;
  created_at: string;
  created_by: string;
  parent_version: number | null;
  ubuntu_base: string;
  leaf_layer_id: string;
  note: string | null;
  resolved_stack: LayerInfo[] | null;
}
