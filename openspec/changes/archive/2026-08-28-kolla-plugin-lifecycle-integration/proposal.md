## Why

Bare `kolla-ansible pull -i multinode` only runs the stock Kolla site playbook. Custom Afterglow-family roles participate only after the installer adds its marked aggregate-playbook import, and each enabled role needs a matching inventory group. Both shipped inventory samples omit `palimpsest`, causing its image pull and lifecycle work to be silently skipped. Afterglow upgrade also bypasses its shared pull task and can pull source-mode images contrary to the other custom roles.

The custom roles duplicate selected Kolla topology and transport defaults. A change to standard `globals.yml` should carry through to plugin OpenStack interface, internal API origin, and TLS/CA transport configuration unless an explicit plugin override is supplied.

## What Changes

- Make the installer and aggregate custom playbook fail clearly when an enabled custom service lacks its required inventory group; document and ship all five logical groups in both inventory samples.
- Make Afterglow upgrade reuse the existing source-mode-aware `pull.yml` task, matching Lumen, Drover, and Palimpsest.
- Derive safe plugin defaults from standard Kolla globals while preserving explicit plugin overrides: Kolla internal protocol/FQDN, OpenStack interface, and TLS trust settings.
- Extend lifecycle contracts to prove stock-site import, all service image pulls, role-group validation, upgrade pull ordering, and standard-global inheritance.

## Capabilities

### New Capabilities

- Standard Kolla lifecycle commands can reliably manage enabled custom roles after additive plugin installation, including image pull validation before no-op lifecycle execution.
- Standard Kolla `globals.yml` changes flow into custom-service runtime topology and OpenStack transport defaults.

### Modified Capabilities

- Afterglow upgrade uses the same image-selection semantics as `kolla-ansible pull`.
- Inventory examples include Palimpsest as a first-class plugin group.

## Impact

Changes remain limited to additive Afterglow Kolla plugin roles, installer validation, inventory samples, globals sample, and contract tests. The stock Kolla site is modified only through the existing marked import mechanism; stock globals/passwords/playbooks and explicit plugin overrides remain intact.
