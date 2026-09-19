"""Arm C: Claude reading the no-ai-slop skill in detect mode.

  python bench/run_skill.py

Needs a working `claude -p`. If OAuth has expired, run `claude` once
interactively to refresh it, then re-run this.

This is not a like-for-like comparison with arm B and the README says so. Arm C
sends the whole 31-tell skill on every call and thinks in text. It is here to
answer "do the two agree on the same lines", not "which is faster".
"""
import json
import pathlib
import re
import subprocess
import sys
import time

LOCAL = pathlib.Path(__file__).parent / "local"
SKILL = pathlib.Path.home() / ".claude/skills/no-ai-slop/SKILL.md"

PROMPT = """You are running the `no-ai-slop` skill in DETECT mode.

{skill}

---

Run DETECT on the numbered passage below. For every pattern from the skill that
appears, output one line, and nothing else:

LINE <n> | <pattern name> | <the quoted text>

Use only the line numbers given. Do not rewrite the draft. Do not score it. Do
not guess whether AI wrote it. If you find nothing, output exactly: NONE

PASSAGE:
{passage}
"""


def numbered(text, units):
    return "\n".join(f"{u['n']}. {u['raw']}" for u in units)


def parse(out):
    hits = []
    for ln in out.splitlines():
        m = re.match(r"\s*LINE\s+(\d+)\s*\|\s*([^|]+?)\s*\|\s*(.*)", ln, re.I)
        if m:
            hits.append({"unit": int(m.group(1)), "name": m.group(2).strip(),
                         "quote": m.group(3).strip(), "layer": "skill", "p": 1.0,
                         "tell": m.group(2).strip().lower().replace(" ", "_")})
    return hits


def main():
    if not SKILL.exists():
        sys.exit(f"missing {SKILL}")
    skill = SKILL.read_text()
    sheet = [l.split("\t") for l in (LOCAL / "sheet.tsv").read_text().splitlines()[1:]]
    by_passage = {}
    for sid, pid, prov, n, tells, sent in sheet:
        by_passage.setdefault(pid, []).append({"n": int(n), "raw": sent})

    passages = json.loads((LOCAL / "passages.json").read_text())
    results, t0 = [], time.perf_counter()
    for p in passages:
        units = by_passage.get(p["id"], [])
        prompt = PROMPT.format(skill=skill, passage=numbered(p["text"], units))
        t1 = time.perf_counter()
        try:
            r = subprocess.run(["claude", "-p", prompt], capture_output=True,
                               text=True, timeout=300)
        except subprocess.TimeoutExpired:
            sys.exit(f"timeout on {p['id']}")
        ms = (time.perf_counter() - t1) * 1000
        if r.returncode != 0 or "Failed to authenticate" in (r.stdout + r.stderr):
            sys.exit(f"claude -p failed on {p['id']}: "
                     f"{(r.stderr or r.stdout)[:200]}\n"
                     f"Run `claude` once interactively to refresh OAuth, then retry.")
        hits = parse(r.stdout)
        results.append({"passage": p["id"], "provenance": p["provenance"],
                        "ms": ms, "cost": None, "calls": 1, "findings": hits})
        print(f"  {p['id']:12} {p['provenance']:9} {len(hits):3} findings  {ms:7.0f} ms")
    total = (time.perf_counter() - t0) * 1000
    (LOCAL / "arm_c.json").write_text(json.dumps(
        {"arm": "c", "total_ms": total, "results": results}, indent=2))
    print(f"\narm C: {sum(len(r['findings']) for r in results)} findings, {total:.0f} ms total")


if __name__ == "__main__":
    main()
