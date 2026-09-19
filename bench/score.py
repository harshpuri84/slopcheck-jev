"""Score every arm against the adjudicated pool.

  python bench/score.py

Precision is exact. Recall is recall against the pool: a tell that every arm
missed is invisible here, and the README says so.
"""
import json
import pathlib
import sys

LOCAL = pathlib.Path(__file__).parent / "local"


def load_verdicts():
    p = LOCAL / "adjudicate.tsv"
    if not p.exists():
        sys.exit("no adjudicate.tsv. Run bench/pool.py first.")
    out, blank = {}, 0
    for line in p.read_text().splitlines()[1:]:
        c = line.split("\t")
        if len(c) < 6:
            continue
        v = c[0].strip().lower()
        key = (c[1], int(c[3]), c[4])
        if v in ("y", "yes", "1"):
            out[key] = True
        elif v in ("n", "no", "0"):
            out[key] = False
        else:
            blank += 1
    return out, blank


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def main():
    verdicts, blank = load_verdicts()
    if blank:
        print(f"warning: {blank} rows still unmarked, excluded from scoring\n")
    if not verdicts:
        sys.exit("nothing adjudicated yet.")
    pool = json.loads((LOCAL / "pool.json").read_text())
    truth = {k for k, v in verdicts.items() if v}

    print(f"adjudicated {len(verdicts)} rows, {len(truth)} confirmed tells\n")
    hdr = f"{'arm':<28} {'TP':>4} {'FP':>4} {'FN':>4} {'prec':>6} {'rec*':>6} {'F1':>6} {'ms/passage':>11} {'$/1k':>9}"
    print(hdr); print("-" * len(hdr))
    names = {"a": "A  lex only", "b": "B  lex + Jev", "c": "C  Claude + no-ai-slop"}
    for arm, keys in sorted(pool["by_arm"].items()):
        flagged = {tuple([k[0], k[1], k[2]]) for k in keys} & set(verdicts)
        tp = len(flagged & truth)
        fp = len(flagged - truth)
        fn = len(truth - flagged)
        p, r, f = prf(tp, fp, fn)
        d = json.loads((LOCAL / f"arm_{arm}.json").read_text())
        n = len(d["results"])
        ms = sum(x["ms"] for x in d["results"]) / n
        costs = [x["cost"] for x in d["results"] if x["cost"] is not None]
        cost = f"${sum(costs)/n*1000:.3f}" if costs else "n/a"
        print(f"{names.get(arm,arm):<28} {tp:>4} {fp:>4} {fn:>4} "
              f"{p:>6.2f} {r:>6.2f} {f:>6.2f} {ms:>11.0f} {cost:>9}")
    print("\nrec* is recall against the pool, not absolute recall.")
    print(f"pool = {len(verdicts)} adjudicated rows from {len(pool['by_arm'])} arm(s).")


if __name__ == "__main__":
    main()
