## Why

The Linux x64 build capacity on `pieroot-server` is intended to be shared by repositories in the `openstack-afterglow` organization. Registering the five containers directly to one repository fixed an immediate queue but defeated that design. The prior organization registration failed because the Default runner group allowed all private repositories while `allows_public_repositories` was false; all six organization repositories are public. Simply enabling public access would also let the current pull-request image job execute untrusted fork code on a runner that mounts the host Docker socket.

## What Changes

- Keep the five Afterglow build containers registered at organization scope so eligible organization repositories share one queue and capacity pool.
- Allow public organization repositories to use the Default runner group.
- Prevent `pull_request` events from reaching the self-hosted image-build matrix; pull requests retain deterministic hosted tests, while trusted push, tag, and manual-dispatch events retain native image builds.
- Verify organization group visibility, runner registration, labels, and assignment using a trusted workflow run.

## Capabilities

### New Capabilities

- Organization repositories can share the Linux x64 runner pool instead of maintaining repository-specific registrations.

### Modified Capabilities

- Public pull requests no longer execute Docker image builds on the self-hosted host; trusted repository events continue publishing images.

## Impact

- Repository: `.github/workflows/docker-build.yml` and its orchestration contract tests.
- Runner host: `/app/actions-runner/.env` and the five `afterglow-runner` containers.
- GitHub organization: Default runner-group public-repository access.
- No application runtime behavior changes.
