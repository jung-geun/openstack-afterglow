# Migration Ledger Completeness

## Why

Keep every committed SQL migration in the immutable manifest so schema work cannot become silently unapplied.

## Problem

`070_chat_message_local_timestamps.sql` exists but is absent from `manifest.txt`. The ledger loader only verifies manifest entries against files, so the orphaned migration is invisible to any manifest-driven workflow.

## What Changes

- Register the timestamp migration with its immutable checksum and logical identity.
- Fail closed when a SQL migration file has no manifest entry.
- Add regression coverage for manifest-to-filesystem completeness.

## Non-goals

- Add an automatic migration executor.
- Replay historical migrations against existing databases.
- Change unrelated schema migrations.
