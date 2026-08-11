# Afterglow public endpoint

## Goal

Configure an explicit Afterglow public frontend endpoint so browser-facing origin, frontend base URL, CORS, OAuth callback, and instance-health callback use the operator-selected domain.

## Scope

- Add `afterglow_public_endpoint_url` to the Kolla Afterglow role.
- Render it into every frontend-facing URL consumer.
- Set the DMSLab sample and deployed plugin globals to `https://cloud.dmslab.re.kr`.
- Add a repository contract test for the configuration path.

## Non-goals

- DNS, TLS, firewall, or public API ingress changes.
- Changing the existing internal API base URL.

## Verification

- Run the Kolla contract test and full required repository gates.
- Run Kolla syntax/reconfigure against the deployed plugin and verify the rendered frontend environment and health endpoint.
