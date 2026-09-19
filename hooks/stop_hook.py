#!/usr/bin/env python3
"""slopcheck as a Claude Code Stop hook. Warns. Never blocks.

Registered in settings.json as a Stop hook. Reads the hook JSON on stdin, pulls
the last assistant message out of the transcript, and reports any AI tells in it.

Every failure path exits 0. A detector that can break a session is worse than no
detector, so: no key, no network, timeout, malformed transcript and unparseable
JSON all exit silently.

Env:
  SLOPCHECK_MIN_WORDS  prose words below which the hook does nothing (default 40)
  SLOPCHECK_TIMEOUT    seconds for the Jev calls (default 6)
  SLOPCHECK_NO_JEV     set to 1 for regex only, no network
  SLOPCHECK_LOG        append every report to this file as well
"""
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def prose_of(block):
    """Text a human reads. Code fences, tool calls and thinking are not prose."""
    if isinstance(block, str):
        return block
    if not isinstance(block, dict) or block.get("type") != "text":
        return ""
    return block.get("text", "")


def last_assistant_text(path):
    try:
        lines = pathlib.Path(path).read_text(errors="replace").splitlines()
    except Exception:
        return ""
    for line in reversed(lines):
        if '"type":"assistant"' not in line and '"type": "assistant"' not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        content = (rec.get("message") or {}).get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            t = "".join(prose_of(b) for b in content)
            if t.strip():
                return t
    return ""


def strip_code(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"^\s{4,}\S.*$", "", text, flags=re.M)
    return text


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("stop_hook_active"):
        return 0

    text = strip_code(last_assistant_text(payload.get("transcript_path") or ""))
    min_words = int(os.environ.get("SLOPCHECK_MIN_WORDS", "40"))
    if len(re.findall(r"\b[\w'-]+\b", text)) < min_words:
        return 0

    try:
        import yaml
        from slopcheck import cli, report
        cfg = yaml.safe_load((HERE.parent / "slopcheck/tells.yaml").read_text())
        findings, stats = cli.check(
            text, cfg,
            use_jev=os.environ.get("SLOPCHECK_NO_JEV") != "1",
            timeout=float(os.environ.get("SLOPCHECK_TIMEOUT", "6")))
    except Exception:
        return 0

    if not findings:
        return 0
    out = report.as_text(findings, stats, color=False, path="(this turn)")
    print(out, file=sys.stderr)
    log = os.environ.get("SLOPCHECK_LOG")
    if log:
        try:
            with open(log, "a") as f:
                f.write(out + "\n\n")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)          # last resort. The hook never fails the session.
