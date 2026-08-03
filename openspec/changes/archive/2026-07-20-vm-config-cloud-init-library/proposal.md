# VM configuration and cloud-init library

## Goal

Simplify VM configuration layout and provide private reusable cloud-init history and presets.

## Scope

- Move network and security group into a shared top row; remove the availability-zone chooser and use the configured Nova default.
- Place keypair/GitHub SSH selection below those network controls.
- Encrypt user cloud-init history and named presets per user; record non-empty scripts after successful instance creation; provide save, load, and delete operations in the VM wizard.
