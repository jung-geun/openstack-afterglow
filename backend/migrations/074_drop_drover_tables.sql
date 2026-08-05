-- Drover cutover: all K3s data and its manager credential cache move to Drover.
-- Apply only after services/drover/drover/scripts/cutover.py verifies row counts
-- and ciphertext byte equality in the destination database.

DELETE FROM resource_policies WHERE policy_key LIKE 'k3s.%';
DELETE FROM runtime_settings WHERE setting_key = 'k3s.version';

DROP TABLE IF EXISTS k3s_nodegroup_vms;
DROP TABLE IF EXISTS k3s_nodegroups;
DROP TABLE IF EXISTS k3s_agent_vms;
DROP TABLE IF EXISTS drover_jobs;
DROP TABLE IF EXISTS k3s_cluster_templates;
DROP TABLE IF EXISTS project_manager_credentials;
DROP TABLE IF EXISTS k3s_clusters;
DROP TABLE IF EXISTS gpu_quotas;
