# Running slopcheck after every Claude Code turn

The hook reads the last assistant message from the session transcript, scores the prose in
it, and prints any tells it finds. It warns. It never blocks.

## Install

```bash
pip install -e /path/to/slopcheck
```

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/ABSOLUTE/PATH/TO/slopcheck/hooks/stop-hook.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Use the absolute path. If a `Stop` array already exists, add this object to it rather than
replacing it.

Check it runs:

```bash
printf '{"stop_hook_active":false,"transcript_path":"%s"}' \
  "$(ls -t ~/.claude/projects/*/*.jsonl | head -1)" \
  | SLOPCHECK_MIN_WORDS=10 ./hooks/stop-hook.sh
```

## What it costs you

| Case | Time |
|---|---|
| Turn under 40 prose words. Most turns | 0.10 s, no network, no Python |
| Clean prose | ~0.75 s, one Jev call |
| Prose with tells | ~1.35 s, two Jev calls |

A shell wrapper does the gate because `python3` costs about 0.42 s just to start on a pyenv
install, and that would land on every turn. Python only starts when there is prose worth
checking.

## Settings

| Variable | Default | Effect |
|---|---|---|
| `SLOPCHECK_MIN_WORDS` | 40 | Prose words below which the hook does nothing |
| `SLOPCHECK_TIMEOUT` | 6 | Seconds allowed for the Jev calls |
| `SLOPCHECK_NO_JEV` | unset | Set to `1` for regex only, no network |
| `SLOPCHECK_LOG` | unset | Also append every report to this file |

## It cannot break your session

Every path exits 0: no key, no network, DNS failure, timeout, malformed transcript,
unparseable JSON, `jq` missing. A detector that can break a session is worse than no
detector.

Verified failure paths:

```
bad API key          exit 0, no output
1 ms timeout         exit 0, no output
proxy blackhole      exit 0, no output
garbage on stdin     exit 0, no output
missing transcript   exit 0, no output
stop_hook_active     exit 0, no output
```

## What it does not do

It does not block, rewrite, or edit. `--strict` makes the CLI exit 1 when findings exist,
but the hook never passes it. Blocking on a false positive traps you in a rewrite loop, and
this detector has false positives.
