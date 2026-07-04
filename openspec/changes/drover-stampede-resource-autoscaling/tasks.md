## Implementation Tasks

### 1. Nodegroup invariants and lifecycle

- [x] Enforce `stampede_enabled=true` nodegroups to use `role='agent'` and explicit `flavor_id` in create/update models or route validation.
- [x] Reject server custom nodegroup scaling and server `node_count` changes until HA server join is implemented.
- [x] Create `default-server` and `default-agent` nodegroups in `k3s_db.create_cluster_record()` for new clusters.
- [x] Mirror initial agent VMs from `k3s_provisioner.provision_agents()` into `k3s_nodegroup_vms` for `default-agent` while preserving `k3s_agent_vms`.
- [x] Make agent nodegroup create with `node_count > 0` start VM provisioning via `k3s_autoscale.provision_nodegroup_vms()` and reconcile failed attempts.
- [x] Make agent nodegroup patch compute desired-current delta, call provision/delete helpers, and reconcile failed attempts.
- [x] Keep legacy cluster `/scale` compatible while mirroring default-agent nodegroup count and VM rows for created/deleted agents.
- [x] Update nodegroup UI to hide/disable custom server role, require explicit flavor for Stampede, and describe nonzero count as provisioning start.
- [x] Add backend and frontend tests for nodegroup lifecycle invariants and UI affordances.

### 2. Resource accounting and pod assignment

- [x] Extend Kubernetes pod resource parsing to sum CPU, memory, and `nvidia.com/gpu` across containers and initContainers.
- [x] Keep scale-up decisions based on Kubernetes requests and node allocatable values, not live utilization.
- [x] Keep `nvidia.com/gpu` as the only supported extended resource for this change.
- [x] Build Stampede eligible nodegroups from enabled agent groups with explicit flavors, bounds, labels, taints, and resolved flavor capacity.
- [x] Match Pending pods to nodegroups using hard constraints: node pinning, nodeSelector, required node affinity, taints/tolerations, GPU requests, and flavor capacity.
- [x] Assign each Pending pod to exactly one best nodegroup, preferring sufficient smaller flavors and existing free capacity.
- [x] Emit structured blocked/skipped events when no candidate can scale a Pending pod.
- [x] Compute existing nodegroup free capacity with CPU, memory, and GPU allocatable minus running pod requests.
- [x] Bin-pack unresolved assigned pods against homogeneous nodegroup flavor capacity and cap by max size and in-flight nodes.
- [x] Use the existing Nova flavor wrapper so extra specs are available for GPU detection.
- [x] Precheck GPU quota for multi-node projected GPU requests before creating any GPU nodes.
- [x] Reconcile desired/in-flight counts on provisioning failure or Ready/GPU timeout.
- [x] Add backend tests for GPU fit, hard affinity, single assignment, blocked reasons, bin packing, in-flight cap, and quota blocking.

### 3. GPU node support path

- [x] Treat GPU support v1 as requiring an admin-provided GPU-ready agent image or environment.
- [x] Detect GPU-capable flavors from `pci_passthrough:alias`, existing `gpu_count`, or equivalent extra specs already used by the GPU quota/catalog code.
- [x] Restrict GPU Pending pods to nodegroups whose explicit flavor GPU count satisfies the pod request and whose taints are tolerated.
- [x] After GPU scale-up, verify the new node becomes Ready and exposes allocatable `nvidia.com/gpu`; mark failure as `gpu_not_allocatable` if not.
- [x] Do not add automatic NVIDIA driver, toolkit, or device-plugin bootstrap in this change.
- [x] Add UI badges/warnings for GPU flavors and quota state.

### 4. Scale-down correctness

- [x] Classify idle/removable nodes using CPU, memory, and GPU requests and exclude DaemonSet or mirror/static pods from evictable load.
- [x] Prefer deleting nodes with no non-DaemonSet/non-mirror pods.
- [x] Before deleting a non-empty node, simulate whether its evictable pods fit onto remaining Ready nodes in the same nodegroup.
- [x] Keep the existing drain path and respect PDB behavior.
- [x] Reset per-nodegroup idle checks when candidate nodes are not actually removable.
- [x] Never delete below `min_size`, in-flight nodes, or untracked nodes.
- [x] Add scale-down tests for reverse fit and resource-aware removability.

### 5. API and frontend visibility

- [x] Extend `GET /api/v1/k3s/clusters/{id}/stampede` with per-nodegroup flavor summary, capacity, Pending assignments, blocked reasons, in-flight nodes, and last scale decision.
- [x] Extend Stampede events with `action='blocked'` / `status='skipped'` and structured `extra.reason` payloads.
- [x] Render nodegroup capacity cards for requested, allocatable, and free CPU, memory, and GPU.
- [x] Render Pending pod mapping and blocked reasons in the Stampede tab.
- [x] Render GPU nodegroup badges and quota status in the Stampede UI.
- [x] Avoid Svelte 5 duplicate fetch loops by using `untrack(() => void load())` for async stateful loaders and avoiding duplicate initial auto-refresh.
- [x] Add frontend tests for badges, blocked reasons, capacity rendering, and duplicate fetch avoidance.

### 6. Operational hardening

- [x] Make the worker Stampede loop read `get_settings().k3s_stampede_interval` instead of relying only on `STAMPEDE_INTERVAL`.
- [x] Remove or implement `k3s_stampede_project_id` so config does not imply unused isolation semantics.
- [x] Add structured logs for blocked reasons and provisioning failures without exposing kubeconfig, tokens, or secrets.

### 7. Verification

- [x] Run focused backend tests for Kubernetes parsing, Stampede assignment, nodegroups, clusters, and GPU quota.
- [x] Run focused frontend tests for nodegroup and Stampede UI behavior.
- [x] Run `npm run test:backend`.
- [x] Run `npm run test:frontend`.
- [x] Run `npm run lint:backend`.
- [x] Run project-required `npm run test:all` and `npm run lint:backend` before commit.
