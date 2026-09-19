"""slopcheck: report which AI tells a passage contains, with the line quoted.

  slopcheck draft.md
  cat draft.md | slopcheck -
  slopcheck draft.md --json
  slopcheck draft.md --no-jev     # regex only, no network, no key

It never answers "did AI write this". It answers "line 4 is a binary contrast".
Exit code is 0 unless --strict is passed.
"""
import argparse
import pathlib
import sys
import time

import yaml

from . import gate, judge, lex, report

CFG = pathlib.Path(__file__).with_name("tells.yaml")


def check(text, cfg, use_jev=True, key=None, timeout=20):
    t0 = time.perf_counter()
    lexed = lex.run(text, cfg)
    probs, calls, usages = {}, 0, []
    err = None
    if use_jev and lexed.words >= 1:
        try:
            probs, _, u1 = judge.detect(text, cfg, key, timeout)
            calls, usages = 1, [u1]
        except judge.JevError as e:
            err = str(e)
    findings = gate.assemble(lexed, probs, cfg)
    stats = {"words": lexed.words, "units": len(lexed.units),
             "ms": (time.perf_counter() - t0) * 1000, "calls": calls,
             "cost": judge.cost_usd(*usages), "error": err}
    return findings, stats


def main(argv=None):
    ap = argparse.ArgumentParser(prog="slopcheck")
    ap.add_argument("path", help="file to check, or - for stdin")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-jev", action="store_true", help="regex only, no network")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--min-words", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=20)
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when findings exist. Off by default on purpose")
    a = ap.parse_args(argv)

    text = sys.stdin.read() if a.path == "-" else pathlib.Path(a.path).read_text()
    cfg = yaml.safe_load(CFG.read_text())
    if a.min_words and len(text.split()) < a.min_words:
        return 0
    findings, stats = check(text, cfg, use_jev=not a.no_jev, timeout=a.timeout)
    if a.json:
        print(report.as_json(findings, stats))
    else:
        out = report.as_text(findings, stats,
                             color=not a.no_color and sys.stderr.isatty(),
                             path="" if a.path == "-" else a.path)
        print(out, file=sys.stderr)
        if stats["error"]:
            print(f"slopcheck: jev unavailable ({stats['error']}), lex only",
                  file=sys.stderr)
    return 1 if (a.strict and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
