#!/usr/bin/env bash
# Usage: bash check-errors.sh
# Runs svelte-check and summarizes errors and a11y warnings.

cd "$(dirname "$0")"

OUTPUT=$(npx svelte-check 2>&1)

echo "=== Summary ==="
SUMMARY=$(echo "$OUTPUT" | grep "COMPLETED" | tail -1)
if [ -n "$SUMMARY" ]; then
  # Extract: X ERRORS Y WARNINGS Z FILES_WITH_PROBLEMS
  echo "$SUMMARY" | sed 's/.*COMPLETED //'
else
  echo "(no summary found)"
fi

echo ""
echo "=== Errors by file ==="
ERROR_FILES=$(echo "$OUTPUT" | grep " ERROR " | sed 's/.*ERROR "\([^"]*\)".*/\1/' | sort | uniq -c | sort -rn 2>/dev/null || true)
if [ -n "$ERROR_FILES" ]; then
  echo "$ERROR_FILES"
else
  echo "No errors."
fi

echo ""
echo "=== a11y warnings ==="
A11Y_COUNT=$(echo "$OUTPUT" | grep -ic "a11y" || true)
A11Y_COUNT=${A11Y_COUNT:-0}
echo "Count: $A11Y_COUNT"
if [ "$A11Y_COUNT" -gt 0 ] 2>/dev/null; then
  echo "$OUTPUT" | grep -i "a11y" | head -20
fi
