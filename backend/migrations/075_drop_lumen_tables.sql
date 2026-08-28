-- Lumen cutover: chat state now belongs to the standalone Lumen database.
-- Apply only after services/lumen/lumen/scripts/cutover.py has copied every
-- baseline table and verified ciphertext equality in the destination database.

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS chat_tool_approvals;
DROP TABLE IF EXISTS chat_run_turns;
DROP TABLE IF EXISTS chat_run_segments;
DROP TABLE IF EXISTS chat_run_providers;
DROP TABLE IF EXISTS chat_run_interactions;
DROP TABLE IF EXISTS chat_run_events;
DROP TABLE IF EXISTS chat_run_assets;
DROP TABLE IF EXISTS chat_jobs;
DROP TABLE IF EXISTS chat_context_checkpoints;
DROP TABLE IF EXISTS chat_runs;
DROP TABLE IF EXISTS chat_message_assets;
DROP TABLE IF EXISTS chat_memory_provenance;
DROP TABLE IF EXISTS chat_input_derivations;
DROP TABLE IF EXISTS chat_messages;
DROP TABLE IF EXISTS chat_extension_package_components;
DROP TABLE IF EXISTS chat_conversations;
DROP TABLE IF EXISTS chat_code_workspace_assets;
DROP TABLE IF EXISTS llm_models;
DROP TABLE IF EXISTS chat_memory_outbox;
DROP TABLE IF EXISTS chat_extension_package_installs;
DROP TABLE IF EXISTS chat_commands;
DROP TABLE IF EXISTS chat_code_workspaces;
DROP TABLE IF EXISTS llm_providers;
DROP TABLE IF EXISTS chat_workspaces;
DROP TABLE IF EXISTS user_wallets;
DROP TABLE IF EXISTS chat_usage_logs;
DROP TABLE IF EXISTS chat_temp_threads;
DROP TABLE IF EXISTS chat_skills;
DROP TABLE IF EXISTS chat_scheduler_leases;
DROP TABLE IF EXISTS chat_memory_owner_locks;
DROP TABLE IF EXISTS chat_memories;
DROP TABLE IF EXISTS chat_mcp_credentials;
DROP TABLE IF EXISTS chat_mcp_servers;
DROP TABLE IF EXISTS chat_mcp_oauth_requests;
DROP TABLE IF EXISTS chat_mcp_oauth_connections;
DROP TABLE IF EXISTS chat_git_credentials;
DROP TABLE IF EXISTS chat_extension_packages;
DROP TABLE IF EXISTS chat_custom_tools;
DROP TABLE IF EXISTS chat_assets;
DROP TABLE IF EXISTS chat_api_keys;
DROP TABLE IF EXISTS chat_agents;

SET FOREIGN_KEY_CHECKS = 1;
