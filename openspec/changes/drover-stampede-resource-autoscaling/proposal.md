## Why

Stampede currently reconciles enabled k3s clusters and nodegroups, but its scheduling math is CPU/memory-only and nodegroup lifecycle is partly metadata-only. GPU Pending pods can be missed or scaled by the wrong group, custom nodegroup `node_count` can appear successful without provisioning VMs, and unrestricted server nodegroups can silently create worker agents. Stampede v1 needs deterministic, resource-aware agent nodegroup autoscaling before GPU workloads are safe to expose.

## What Changes

- Make scalable Stampede nodegroups agent-only, homogeneous, and backed by an explicit `flavor_id`.
- Create default server/agent nodegroups for new clusters and mirror initial/legacy agent VM tracking into the default-agent nodegroup while preserving existing cluster API compatibility.
- Make agent nodegroup `node_count` create/update paths provision or delete VMs instead of only updating metadata.
- Extend Kubernetes resource accounting and Stampede decisions to CPU, memory, and `nvidia.com/gpu` requests/allocatable values.
- Assign each Pending pod to at most one eligible nodegroup using hard scheduler constraints: selectors, required node affinity, taints/tolerations, node pinning, flavor capacity, and GPU requirements.
- Use homogeneous flavor capacity plus existing free capacity to bin-pack unresolved pods and cap scale-up by max size and in-flight nodes.
- Precheck GPU quota before provisioning GPU nodes and emit blocked/skipped Stampede events with structured reasons when scaling cannot proceed.
- Improve scale-down by considering CPU, memory, GPU requests and simulating whether evicted pods fit elsewhere before deleting nodes.
- Surface nodegroup capacity, Pending pod assignment/block reasons, GPU flavor/quota indicators, in-flight nodes, and last scale decisions through the Stampede API and UI.
- Prefer `get_settings().k3s_stampede_interval` in the worker loop to avoid config/env drift and handle the unused `k3s_stampede_project_id` setting explicitly.

## Capabilities

### New Capabilities

- GPU-aware autoscale-up for Pending pods requesting `nvidia.com/gpu` when an explicit GPU-capable, quota-allowed agent nodegroup exists.
- Clear blocked events for unsupported or unsatisfied scheduling cases such as no matching nodegroup, flavor too small, missing GPU quota, unsupported affinity, pinned missing nodes, or unbound PVCs.
- Real VM provisioning/deletion from agent nodegroup create and update requests.
- Default nodegroup records for newly created clusters and mirrored VM rows for initial/legacy agents.
- API/UI visibility into nodegroup capacity, Pending pod decisions, GPU capability, quota status, and scale events.

### Modified Capabilities

- Stampede nodegroup autoscaling is restricted to agent nodegroups with explicit flavors.
- Server nodegroup scaling is rejected until HA server join semantics are designed.
- Existing cluster-level scale remains compatible and continues using `k3s_agent_vms`, while also mirroring default-agent nodegroup state.
- Scale-up and scale-down use Kubernetes scheduler requests/allocatable math rather than live utilization.
- GPU bootstrap remains an admin/image responsibility in v1; automatic NVIDIA driver/device-plugin installation is deliberately out of scope.

## Impact

Existing non-Stampede clusters and legacy cluster-level scale behavior remain compatible. Stampede-enabled nodegroups without an explicit flavor or with server role will be rejected or blocked with clear reasons instead of producing mixed or incorrectly provisioned nodes. GPU workloads require an admin-provided GPU-ready agent image/environment and a GPU-capable flavor with quota. Tests cover parser behavior, nodegroup lifecycle, pod-to-nodegroup assignment, bin packing, GPU quota blocking, scale-down fit checks, API status visibility, and frontend affordances.
