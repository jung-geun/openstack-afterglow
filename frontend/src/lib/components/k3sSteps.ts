export const K3S_CREATE_STEPS = [
  { id: 'security_group',   label: '보안 그룹' },
  { id: 'server_volume',    label: '서버 볼륨' },
  { id: 'server_creating',  label: '서버 VM' },
  { id: 'waiting_callback', label: 'k3s 초기화' },
  { id: 'completed',        label: '완료' },
];

export const K3S_DELETE_STEPS = [
  { id: 'delete_init',           label: '준비' },
  { id: 'delete_lb_cleanup',     label: 'LB 정리' },
  { id: 'delete_app_credential', label: 'App Credential' },
  { id: 'delete_k8s_nodes',      label: 'K8s 노드' },
  { id: 'delete_agent_vms',      label: '에이전트 VM' },
  { id: 'delete_server_vm',      label: '서버 VM' },
  { id: 'delete_security_group', label: '보안 그룹' },
  { id: 'delete_record',         label: '이력 기록' },
  { id: 'completed',             label: '완료' },
];
