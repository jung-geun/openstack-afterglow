# layer-pip-index-options

## Goal

Allow admin pip package layer builds to use structured pip source options such as `--index-url https://download.pytorch.org/whl/cpu` without accepting free-form shell text.

## Scope

- Backend API accepts allowlisted structured fields for pip package layer source configuration.
- Backend validates URLs and rejects shell/control characters before build allocation.
- Build scripts render pip options with `shlex.quote()`.
- Admin layer UI exposes optional index URL inputs for package layers.
- Regression tests cover PyTorch CPU index URL and injection rejection.

## Non-goals

- No free-form pip command-line string.
- No support for environment markers, direct URL package specs, credentials in URLs, or arbitrary pip flags.
- No database migration; options affect the build command only.
