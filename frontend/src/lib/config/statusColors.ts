// Afterglow Design System — Semantic status tone map
// Maps OpenStack resource statuses to 5 design-system tones.
// pulse=true on statuses that represent an in-progress transition.

export interface StatusStyle {
  tone: 'success' | 'warning' | 'danger' | 'info' | 'neutral';
  pulse?: boolean;
  label?: string;
}

export const STATUS_STYLES: Record<string, StatusStyle> = {
  // success — healthy / active
  ACTIVE:              { tone: 'success' },
  active:              { tone: 'success' },
  available:           { tone: 'success' },
  AVAILABLE:           { tone: 'success' },
  Running:             { tone: 'success' },
  running:             { tone: 'success' },
  ENABLED:             { tone: 'success' },
  enabled:             { tone: 'success' },
  ONLINE:              { tone: 'success' },
  UP:                  { tone: 'success' },
  healthy:             { tone: 'success' },
  HEALTHY:             { tone: 'success' },

  // warning + pulse — active transitions (building, deleting, detaching)
  BUILD:               { tone: 'warning', pulse: true },
  PENDING:             { tone: 'warning', pulse: true },
  PENDING_CREATE:      { tone: 'warning', pulse: true },
  PENDING_UPDATE:      { tone: 'warning', pulse: true },
  CREATING:            { tone: 'warning', pulse: true },
  creating:            { tone: 'warning', pulse: true },
  PENDING_DELETE:      { tone: 'warning', pulse: true },
  DELETING:            { tone: 'warning', pulse: true },
  deleting:            { tone: 'warning', pulse: true },
  detaching:           { tone: 'warning', pulse: true },
  DETACHING:           { tone: 'warning', pulse: true },
  retyping:            { tone: 'warning', pulse: true },

  // warning — stopped, non-transitioning
  SHUTOFF:             { tone: 'warning' },

  // neutral + pulse — Trove 비동기 삭제 진행 중 (ACTIVE → SHUTDOWN → 레코드 제거)
  SHUTDOWN:            { tone: 'neutral', pulse: true, label: '삭제 중' },

  // danger — errors / failures
  ERROR:               { tone: 'danger' },
  error:               { tone: 'danger' },
  error_deleting:      { tone: 'danger' },
  error_backing_up:    { tone: 'danger' },
  error_restoring:     { tone: 'danger' },
  error_extending:     { tone: 'danger' },
  FAILED:              { tone: 'danger' },
  DELETE_FAILED:       { tone: 'danger' },
  degraded:            { tone: 'danger' },
  unhealthy:           { tone: 'danger' },

  // info + pulse — in-progress I/O operations
  attaching:           { tone: 'info', pulse: true },
  ATTACHING:           { tone: 'info', pulse: true },
  extending:           { tone: 'info', pulse: true },
  'backing-up':        { tone: 'info', pulse: true },
  backing_up:          { tone: 'info', pulse: true },
  'restoring-backup':  { tone: 'info', pulse: true },
  restoring_backup:    { tone: 'info', pulse: true },
  downloading:         { tone: 'info', pulse: true },
  uploading:           { tone: 'info', pulse: true },

  // info — stable in-use / created states
  in_use:              { tone: 'info' },
  IN_USE:              { tone: 'info' },
  Created:             { tone: 'info' },
  ONLINE_STANDBY:      { tone: 'info' },
  SHARED:              { tone: 'info' },

  // neutral — shelved / reserved
  SHELVED:             { tone: 'neutral' },
  SHELVED_OFFLOADED:   { tone: 'neutral' },
  reserved:            { tone: 'neutral' },
  RESERVED:            { tone: 'neutral' },
};

const FALLBACK: StatusStyle = { tone: 'neutral' };

export function getStatusStyle(status: string | null | undefined): StatusStyle {
  if (!status) return FALLBACK;
  return STATUS_STYLES[status] ?? FALLBACK;
}
