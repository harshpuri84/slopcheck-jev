"""Run arm A (lex only) and arm B (lex + Jev) over the extracted passages.

  python bench/run_arms.py           # both arms
  python bench/run_arms.py --arm a   # regex only, no network

Writes bench/local/arm_a.json and arm_b.json. Each records, per passage, which
sentence each tell was pinned to, so the pool can be adjudicated sentence by
sentence.
"""
import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import yaml
from slopcheck import cli

LOCAL = pathlib.Path(__file__).parent / "local"
CFG = yaml.safe_load((pathlib.Path(__file__).parent.parent / "slopcheck/tells.yaml").read_text())


def run(arm):
    passages = json.loads((LOCAL / "passages.json").read_text())
    out, t0 = [], time.perf_counter()
    for p in passages:
        findings, stats = cli.check(p["text"], CFG, use_jev=(arm == "b"))
        if stats["error"]:
            # Fail-open means a failed call looks like a clean passage with zero
            # calls. Never let that reach a results table unlabelled.
            sys.exit(f"jev error on {p['id']}: {stats['error']}")
        out.append({
            "passage": p["id"], "provenance": p["provenance"],
            "ms": stats["ms"], "cost": stats["cost"], "calls": stats["calls"],
            "findings": [{"tell": f.tell, "name": f.name, "layer": f.layer,
                          "unit": f.unit, "quote": f.quote, "p": f.p}
                         for f in findings]})
        n = len(out[-1]["findings"])
        print(f"  {p['id']:12} {p['provenance']:9} {n:3} findings  "
              f"{stats['ms']:6.0f} ms  ${stats['cost']:.6f}")
    path = LOCAL / f"arm_{arm}.json"
    total_ms = (time.perf_counter() - t0) * 1000
    path.write_text(json.dumps({"arm": arm, "total_ms": total_ms,
                                "results": out}, indent=2))
    tot = sum(len(r["findings"]) for r in out)
    cost = sum(r["cost"] for r in out)
    print(f"\narm {arm.upper()}: {tot} findings over {len(out)} passages, "
          f"{total_ms:.0f} ms total, ${cost:.6f}")
    print(f"wrote {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["a", "b", "both"], default="both")
    a = ap.parse_args()
    for arm in (["a", "b"] if a.arm == "both" else [a.arm]):
        print(f"\n=== arm {arm.upper()} ({'lex only' if arm == 'a' else 'lex + Jev'}) ===")
        run(arm)
