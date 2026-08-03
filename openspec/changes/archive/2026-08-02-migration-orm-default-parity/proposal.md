# Migration ORM Default Parity

## Why

A fresh database initialized with SQLAlchemy `create_all` omitted the database-level `on_demand` default required by migration 071 for chat MCP servers and custom tools. The Python-only default cannot protect direct SQL writes or schema consumers.

## What Changes

- Define the `load_policy` default at the ORM server level.
- Add a MySQL DDL regression test for both affected tables.
- Keep historical Python-only defaults outside this targeted parity repair; they require a migration-by-migration design rather than an unverified bulk conversion.

## Non-goals

- Replay unrelated historical migrations.
- Sweep unrelated historical migration defaults into ORM server defaults.
- Change the `load_policy` value or API behavior.
