# Chat Stream Whitespace Integrity

## Goal

Preserve every streamed text and reasoning delta and completed part exactly while preventing whitespace-only chunks from crashing durable chat runs.

## Problem

`PartDeltaPayload` inherits the global strict-model whitespace stripping. A provider delta such as `"\n"` is stripped to an empty string before its minimum-length validation and terminates the durable run. Non-empty deltas are also corrupted: trailing spaces, indentation, and line breaks vanish from streamed markdown and code. `TextPart` and `ReasoningPart` share that behavior, so whitespace-only completed content can likewise terminate finalization.

## Scope

- Disable whitespace stripping for model-output text, reasoning, and persisted `part.delta` payloads.
- Preserve the existing non-empty and maximum-length content contract.
- Add byte-identity regressions for newline and trailing-space deltas and completed parts.

## Non-goals

- Keep whitespace normalization for all non-content strict models, including IDs and names.
- Modify MCP OAuth callback validation; worker logs indicate an older image without the current development-loopback allowance.
