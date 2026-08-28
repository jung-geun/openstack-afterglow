# Afterglow Kolla public route

## Goal

Route `https://cloud.dmslab.re.kr` through Kolla-Ansible's existing TLS external HAProxy frontend, splitting frontend requests from `/api/v1` backend requests without changing stock Kolla files.

## Scope

- Add a plugin-owned HAProxy service fragment and external-frontend map entry.
- Send `/api/` to the existing Afterglow API backend and all other paths to the existing frontend backend.
- Add explicit enable, FQDN, and loopback-router port variables.
- Deploy the route to DMSLab and verify both paths directly through the Kolla external VIP.

## Non-goals

- Change Kolla's stock HAProxy templates, global configuration, certificates, DNS, or external VIP.
- Add a new TLS certificate.

## Verification

- Run the Kolla contract test and repository gates.
- Verify Kolla syntax and reconfigure.
- Use `--resolve cloud.dmslab.re.kr:443:172.30.0.254` to assert `/` and `/api/v1/health` return HTTP 200 through Kolla HAProxy.
