#!/usr/bin/env bash
# Reads Claude Code PreToolUse JSON from stdin.
# If the tool call is a git push, checks the branch diff size and warns
# if it exceeds the threshold. Exits 0 (non-blocking) in all cases.

THRESHOLD=8

# Parse the command out of the JSON input
INPUT=$(cat)

if command -v jq &>/dev/null; then
  COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)
else
  COMMAND=$(echo "$INPUT" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" \
    2>/dev/null)
fi

# Only act on git push commands
if ! echo "$COMMAND" | grep -qE "^git push"; then
  exit 0
fi

# Resolve base branch
BASE=""
for candidate in main master develop; do
  if git rev-parse --verify "$candidate" &>/dev/null; then
    BASE="$candidate"
    break
  fi
done

[ -z "$BASE" ] && exit 0

FILE_COUNT=$(git diff "${BASE}...HEAD" --name-only 2>/dev/null | wc -l | tr -d ' ')

if [ "$FILE_COUNT" -gt "$THRESHOLD" ]; then
  echo ""
  echo "Large branch: ${FILE_COUNT} files changed against '${BASE}' (threshold: ${THRESHOLD})."
  echo "Before pushing, consider splitting this into smaller PRs:"
  echo "  /pr-split:plan"
  echo ""
fi

exit 0
