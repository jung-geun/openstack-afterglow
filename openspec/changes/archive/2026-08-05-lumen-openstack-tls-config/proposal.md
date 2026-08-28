# Lumen canonical OpenStack TLS configuration

## Goal
Map Afterglow's canonical `[openstack]` TLS settings into Lumen's Keystone client settings.

## Scope
- Map `insecure` to Lumen's `insecure` setting.
- Map `cacert` to Lumen's `os_cacert` setting.
- Cover both mappings in the canonical-section configuration test.

## Non-goals
- Change explicit `[keystone]` configuration behavior.
- Change certificate verification policy.