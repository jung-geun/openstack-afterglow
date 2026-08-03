## 1. Foundation

- [x] 1.1 Add manifest-backed migration and ORM persistence for runtime settings and immutable resource snapshots.
- [x] 1.2 Complete the policy registry, scoped catalogs, exact-ID validation, and no-mutation database stores.
- [x] 1.3 Update the admin resource-policy API and add runtime-setting endpoints with authorization and failure semantics.

## 2. Consumer cutover

- [x] 2.1 Migrate Nova/Cinder/Manila selection and precedence to policy-backed resolution.
- [x] 2.2 Resolve and snapshot K3s resources and version before provisioning side effects.
- [x] 2.3 Require Builder images, snapshot Builder/Union selections, and remove shared SSH material while preserving Palimpsest ephemeral access.
- [x] 2.4 Resolve and snapshot Waygate provisioning selections without settings/name/keypair fallbacks.
- [x] 2.5 Gate all Notion sync paths through the global runtime setting.

## 3. Migration and interface

- [x] 3.1 Add the idempotent legacy configuration importer and snapshot backfill behavior.
- [x] 3.2 Update admin settings and Notion user interfaces with grouped scoped controls and stale-request guards.
- [x] 3.3 Remove migrated/dead deployment configuration, generators/templates, and obsolete documentation.

## 4. Verification and completion

- [x] 4.1 Add or update focused backend/frontend contracts for every affected domain.
- [ ] 4.2 Perform representative smoke and browser verification after focused contracts pass.
- [ ] 4.3 Run full repository test/lint gates and archive the completed OpenSpec change.
