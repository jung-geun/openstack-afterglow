# Proposal: Standard Kolla Plugin Reconfigure Invocation

## Goal

Allow an operator in `/etc/kolla` to deploy the installed Afterglow plugin with the normal command `kolla-ansible reconfigure --tags afterglow`, using the existing `/etc/kolla/multinode` inventory and standard Kolla globals/passwords.

## Scope
- Install a safe, marker-delimited import of the plugin aggregate playbook into Kolla's installed `site.yml`.
- Make Kolla's default inventory path resolve to `/etc/kolla/multinode` without an `-i` argument.
- Link the plugin-owned `/etc/kolla/afterglow/globals.yml` and `secrets.yml`
  into Kolla's native `/etc/kolla/globals.d/` loader. This preserves the
  existing single secret source without copying values into stock files.
  Validate the tag-selected task list before deployment so missing plugin
  variables cannot yield a successful no-op.
- Preserve the existing custom playbook and explicit command as a supported escape hatch.
- Make uninstall remove only the installer-owned import and inventory symlink.

## Constraints

- Modify no unrelated Kolla playbook content; fail if the managed marker is malformed.
- Do not copy or print secret values.
- Keep the existing `/etc/kolla/multinode` inventory authoritative; it already contains plugin groups.
- Verify the exact tag-only command on DMSLab.
