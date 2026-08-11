# Proposal: Kolla Standard-Command Safety

## Why

Importing the plugin aggregate playbook into Kolla's stock `site.yml` must not
expand a tag-selected reconfigure into every plugin service or make ordinary
Kolla lifecycle commands fail for unimplemented plugin actions.

## What Changes

- Restrict plugin lifecycle dispatchers to their inherited service tags instead
  of `always`.
- Treat Kolla's stock `config_validate`, `stop`, `deploy-containers`, and
  `check` actions as supported no-ops when the plugin has no matching task
  file; retain failure for unknown actions.
- Run plugin HAProxy work only for applicable lifecycle actions and skip
  Afterglow image pulls in source mode.
- Make the globals normalizer clean up a newly-created backup after a failed
  replacement, and harden stock-playbook marker handling.
- Correct installation and recovery documentation and add safety-refusal
  regression coverage.

## Constraints

- Do not print, copy, or weaken protection for secrets.
- Preserve the bare command contract: from `/etc/kolla`,
  `kolla-ansible reconfigure --tags afterglow` selects only Afterglow and its
  HAProxy route work.
- Verify both tag selection and safe stock lifecycle command planning on
  DMSLab.
