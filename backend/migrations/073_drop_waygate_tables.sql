-- Waygate data is copied to the dedicated Waygate database before this migration.
-- This migration runs only after the maintenance-window cutover verifier succeeds.
DELETE FROM resource_policies WHERE policy_key LIKE 'waygate.%';

DROP TABLE IF EXISTS waygate_jobs;
DROP TABLE IF EXISTS waygate_network_attachments;
DROP TABLE IF EXISTS waygate_clients;
DROP TABLE IF EXISTS waygate_servers;
