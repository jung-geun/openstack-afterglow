# Afterglow Kolla Operator Environment

This directory defines the operator virtual environment for Afterglow Kolla-Ansible service deployment.

## Overview

The operator environment manages the dependencies required for running `kolla-ansible` and service role wheels (such as `drover-kolla` and `lumen-kolla`).

- **Kolla-Ansible**: pinned to git commit `34daacfbf2d5987f543787f57535b2bebe7dee19` (21.2.0).
- **Drover Kolla Role**: pinned to wheel release `drover_kolla-0.2.19-py3-none-any.whl` (v0.2.19).
- **Lumen Kolla Role**: pinned to wheel release `lumen_kolla-0.1.4-py3-none-any.whl` (v0.1.4).

## Installation

To sync the operator environment:

```bash
uv sync --frozen
```

This installs `kolla-ansible` and service roles into the virtual environment (e.g. `/etc/kolla/.venv`), putting `drover` and `lumen` role files directly under `$VIRTUAL_ENV/share/kolla-ansible/ansible/roles/{drover,lumen}`.
