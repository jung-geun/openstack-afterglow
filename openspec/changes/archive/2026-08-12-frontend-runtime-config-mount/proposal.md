# Frontend runtime configuration mount

## Goal

Ensure the Kolla Afterglow frontend receives the rendered `afterglow.conf` so browser API resolution uses the configured public API origin even with an older published frontend image.

## Scope

- Mount the existing rendered read-only configuration into the frontend container.
- Add a Kolla contract test for the frontend mount and public API configuration.
- Reconfigure only the Afterglow frontend path on DMSLab and verify browser requests target `https://cloud.dmslab.re.kr/api/v1/...`.

## Constraints

- Keep the current public endpoint and API origin unchanged: `https://cloud.dmslab.re.kr`.
- Do not log secrets or change the pinned images.
- Do not alter stock Kolla configuration or HAProxy routes.
