// Afterglow Design System — Canonical status color map
// Single source of truth for all OpenStack resource status colors.
// Replaces ~33 duplicate `statusColor` maps scattered across pages.

export interface StatusColor {
  bg: string;
  border: string;
  text: string;
  dot: string;
}

const STATUS_MAP: Record<string, StatusColor> = {
  // Green — healthy / active
  ACTIVE:              { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },
  active:              { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },
  available:           { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },
  AVAILABLE:           { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },
  Running:             { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },
  running:             { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },
  ENABLED:             { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },
  enabled:             { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },
  ONLINE:              { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },
  UP:                  { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },
  healthy:             { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },
  HEALTHY:             { bg: 'bg-green-900/30',  border: 'border-green-800',  text: 'text-green-400',  dot: 'bg-green-400' },

  // Yellow/Amber — transitional / building
  BUILD:               { bg: 'bg-yellow-900/30', border: 'border-yellow-800', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  PENDING:             { bg: 'bg-yellow-900/30', border: 'border-yellow-800', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  PENDING_CREATE:      { bg: 'bg-yellow-900/30', border: 'border-yellow-800', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  PENDING_UPDATE:      { bg: 'bg-yellow-900/30', border: 'border-yellow-800', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  CREATING:            { bg: 'bg-yellow-900/30', border: 'border-yellow-800', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  creating:            { bg: 'bg-yellow-900/30', border: 'border-yellow-800', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  PENDING_DELETE:      { bg: 'bg-yellow-900/30', border: 'border-yellow-800', text: 'text-yellow-400', dot: 'bg-yellow-400' },

  // Red — errors / failures
  ERROR:               { bg: 'bg-red-900/30',    border: 'border-red-800',    text: 'text-red-400',    dot: 'bg-red-400' },
  error:               { bg: 'bg-red-900/30',    border: 'border-red-800',    text: 'text-red-400',    dot: 'bg-red-400' },
  error_deleting:      { bg: 'bg-red-900/30',    border: 'border-red-800',    text: 'text-red-400',    dot: 'bg-red-400' },
  error_backing_up:    { bg: 'bg-red-900/30',    border: 'border-red-800',    text: 'text-red-400',    dot: 'bg-red-400' },
  error_restoring:     { bg: 'bg-red-900/30',    border: 'border-red-800',    text: 'text-red-400',    dot: 'bg-red-400' },
  error_extending:     { bg: 'bg-red-900/30',    border: 'border-red-800',    text: 'text-red-400',    dot: 'bg-red-400' },
  FAILED:              { bg: 'bg-red-900/30',    border: 'border-red-800',    text: 'text-red-400',    dot: 'bg-red-400' },
  DELETE_FAILED:       { bg: 'bg-red-900/30',    border: 'border-red-800',    text: 'text-red-400',    dot: 'bg-red-400' },
  degraded:            { bg: 'bg-red-900/30',    border: 'border-red-800',    text: 'text-red-400',    dot: 'bg-red-400' },
  unhealthy:           { bg: 'bg-red-900/30',    border: 'border-red-800',    text: 'text-red-400',    dot: 'bg-red-400' },

  // Orange — shutoff / deleting
  SHUTOFF:             { bg: 'bg-orange-900/30', border: 'border-orange-800', text: 'text-orange-400', dot: 'bg-orange-400' },
  DELETING:            { bg: 'bg-orange-900/30', border: 'border-orange-800', text: 'text-orange-400', dot: 'bg-orange-400' },
  deleting:            { bg: 'bg-orange-900/30', border: 'border-orange-800', text: 'text-orange-400', dot: 'bg-orange-400' },

  // Blue — in-use / created
  in_use:              { bg: 'bg-blue-900/30',   border: 'border-blue-800',   text: 'text-blue-400',   dot: 'bg-blue-400' },
  IN_USE:              { bg: 'bg-blue-900/30',   border: 'border-blue-800',   text: 'text-blue-400',   dot: 'bg-blue-400' },
  Created:             { bg: 'bg-blue-900/30',   border: 'border-blue-800',   text: 'text-blue-400',   dot: 'bg-blue-400' },
  ONLINE_STANDBY:      { bg: 'bg-blue-900/30',   border: 'border-blue-800',   text: 'text-blue-400',   dot: 'bg-blue-400' },

  // Purple — shelved / reserved
  SHELVED:             { bg: 'bg-purple-900/30', border: 'border-purple-800', text: 'text-purple-400', dot: 'bg-purple-400' },
  SHELVED_OFFLOADED:   { bg: 'bg-purple-900/30', border: 'border-purple-800', text: 'text-purple-400', dot: 'bg-purple-400' },
  reserved:            { bg: 'bg-purple-900/30', border: 'border-purple-800', text: 'text-purple-400', dot: 'bg-purple-400' },
  RESERVED:            { bg: 'bg-purple-900/30', border: 'border-purple-800', text: 'text-purple-400', dot: 'bg-purple-400' },

  // Amber — detaching
  detaching:           { bg: 'bg-amber-900/30',  border: 'border-amber-800',  text: 'text-amber-400',  dot: 'bg-amber-400' },
  DETACHING:           { bg: 'bg-amber-900/30',  border: 'border-amber-800',  text: 'text-amber-400',  dot: 'bg-amber-400' },

  // Cyan — attaching
  attaching:           { bg: 'bg-cyan-900/30',   border: 'border-cyan-800',   text: 'text-cyan-400',   dot: 'bg-cyan-400' },
  ATTACHING:           { bg: 'bg-cyan-900/30',   border: 'border-cyan-800',   text: 'text-cyan-400',   dot: 'bg-cyan-400' },
  extending:           { bg: 'bg-cyan-900/30',   border: 'border-cyan-800',   text: 'text-cyan-400',   dot: 'bg-cyan-400' },

  // Indigo — backing-up
  'backing-up':        { bg: 'bg-indigo-900/30', border: 'border-indigo-800', text: 'text-indigo-400', dot: 'bg-indigo-400' },
  backing_up:          { bg: 'bg-indigo-900/30', border: 'border-indigo-800', text: 'text-indigo-400', dot: 'bg-indigo-400' },

  // Teal — restoring
  'restoring-backup':  { bg: 'bg-teal-900/30',   border: 'border-teal-800',   text: 'text-teal-400',   dot: 'bg-teal-400' },
  restoring_backup:    { bg: 'bg-teal-900/30',   border: 'border-teal-800',   text: 'text-teal-400',   dot: 'bg-teal-400' },
  SHARED:              { bg: 'bg-teal-900/30',   border: 'border-teal-800',   text: 'text-teal-400',   dot: 'bg-teal-400' },

  // Sky — downloading / uploading
  downloading:         { bg: 'bg-sky-900/30',    border: 'border-sky-800',    text: 'text-sky-400',    dot: 'bg-sky-400' },
  uploading:           { bg: 'bg-sky-900/30',    border: 'border-sky-800',    text: 'text-sky-400',    dot: 'bg-sky-400' },

  // Violet — retyping
  retyping:            { bg: 'bg-violet-900/30', border: 'border-violet-800', text: 'text-violet-400', dot: 'bg-violet-400' },
};

const FALLBACK: StatusColor = {
  bg: 'bg-gray-800/60',
  border: 'border-gray-700',
  text: 'text-gray-400',
  dot: 'bg-gray-400',
};

export function getStatusColor(status: string | null | undefined): StatusColor {
  if (!status) return FALLBACK;
  return STATUS_MAP[status] ?? FALLBACK;
}
