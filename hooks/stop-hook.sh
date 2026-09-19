#!/bin/sh
# slopcheck Stop hook. Warns about AI tells in Claude's own output. Never blocks.
#
# Register in ~/.claude/settings.json:
#   "Stop": [{"hooks":[{"type":"command",
#             "command":"/ABS/PATH/TO/slopcheck/hooks/stop-hook.sh","timeout":10}]}]
#
# Why the shell wrapper: python3 costs ~420 ms just to start on a pyenv install,
# and that would land on every turn. jq does the gate in ~15 ms, so python only
# starts on turns that actually have prose worth checking.
#
# Env:
#   SLOPCHECK_MIN_WORDS  prose words below which nothing happens (default 40)
#   SLOPCHECK_TIMEOUT    seconds for the Jev calls (default 6)
#   SLOPCHECK_NO_JEV=1   regex only, no network
#   SLOPCHECK_LOG        also append every report to this file
#
# Exits 0 on every path, including every failure. A detector that can break a
# session is worse than no detector.

set +e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MIN=${SLOPCHECK_MIN_WORDS:-40}

INPUT=$(cat 2>/dev/null)
[ -z "$INPUT" ] && exit 0

# No jq: hand the whole job to the python fallback, which parses it itself.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s' "$INPUT" | python3 "$DIR/hooks/stop_hook.py" 2>&1 >&2
  exit 0
fi

ACTIVE=$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)
[ "$ACTIVE" = "true" ] && exit 0

T=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[ -z "$T" ] || [ ! -f "$T" ] && exit 0

# Last assistant turn, text blocks only. tool_use and thinking are not prose.
TEXT=$(tail -n 600 "$T" 2>/dev/null \
  | grep '"type":"assistant"' 2>/dev/null \
  | tail -n 1 \
  | jq -r '(.message.content // empty)
           | if type=="array" then (map(select(.type=="text") | .text) | join("\n"))
             else (.//"") end' 2>/dev/null)
[ -z "$TEXT" ] && exit 0

# Fenced code is not prose. Drop it before counting and before scoring.
TEXT=$(printf '%s\n' "$TEXT" | awk '/^[[:space:]]*```/{f=!f;next} !f')
WORDS=$(printf '%s' "$TEXT" | wc -w | tr -d ' ')
[ "$WORDS" -lt "$MIN" ] && exit 0

printf '%s\n' "$TEXT" | python3 -m slopcheck - \
  --no-color \
  --timeout "${SLOPCHECK_TIMEOUT:-6}" \
  ${SLOPCHECK_NO_JEV:+--no-jev} \
  2>&1 >/dev/null \
  | { if [ -n "$SLOPCHECK_LOG" ]; then tee -a "$SLOPCHECK_LOG"; else cat; fi; } >&2

exit 0
