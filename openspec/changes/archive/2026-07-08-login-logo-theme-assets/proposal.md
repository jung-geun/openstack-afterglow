## Summary

Fix the login branding logo on the home/login page so the initial SSR render does not trigger both theme-specific logo asset requests, and correct the built-in default `logo_light`/`logo_dark` asset path assignments without changing the existing slot semantics. This change preserves the current branding contract, gates the login logo until the client theme is known after mount, updates backend/frontend/K8s/example defaults in sync, and adds regression coverage for mounted and SSR behavior.
