"""Build the adjudication sheet: the union of what every arm flagged.

  python bench/pool.py

Harsh marks each row y or n in the `verdict` column. Rows no arm flagged are
assumed negative, which is the standard pooled-adjudication assumption and the
reason recall here is recall against the pool, not absolute recall.

The sheet deliberately does NOT say which arm flagged a row. Showing that would
let the judge anchor on the arm they expect to win.
"""
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from normalise import canon

LOCAL = pathlib.Path(__file__).parent / "local"
ARMS = ["a", "b", "c"]


def main():
    sheet = [l.split("\t") for l in (LOCAL / "sheet.tsv").read_text().splitlines()[1:]]
    text = {(pid, int(n)): sent for _, pid, _, n, _, sent in sheet}
    prov = {pid: p for _, pid, p, _, _, _ in sheet}

    pool, by_arm = {}, {}
    for arm in ARMS:
        f = LOCAL / f"arm_{arm}.json"
        if not f.exists():
            print(f"  arm {arm.upper()}: not run, skipping")
            continue
        by_arm[arm] = set()
        for r in json.loads(f.read_text())["results"]:
            for fi in r["findings"]:
                # unit 0 means the tell fired but no line was named. Still a claim,
                # so it is adjudicated at passage level rather than dropped.
                key = (r["passage"], fi["unit"], canon(fi["name"]))
                pool.setdefault(key, set()).add(arm)
                by_arm[arm].add(key)

    rows = sorted(pool.keys())
    random.Random(19).shuffle(rows)      # order must not hint at the arm
    with (LOCAL / "adjudicate.tsv").open("w") as f:
        f.write("verdict\tpassage\tprovenance\tunit\ttell\tsentence\n")
        for pid, unit, name in rows:
            sent = text.get((pid, unit), "(whole passage: no line named)")
            f.write(f"\t{pid}\t{prov.get(pid,'?')}\t{unit}\t{name}\t{sent}\n")
    (LOCAL / "pool.json").write_text(json.dumps(
        {"rows": [list(k) for k in rows],
         "by_arm": {a: [list(k) for k in v] for a, v in by_arm.items()}}, indent=2))

    print(f"\npool: {len(rows)} rows to adjudicate, from arms {sorted(by_arm)}")
    for a, v in sorted(by_arm.items()):
        print(f"  arm {a.upper()} contributed {len(v)}")
    if len(by_arm) > 1:
        sets = list(by_arm.values())
        shared = set.intersection(*sets)
        print(f"  all arms agree on {len(shared)} of {len(rows)}")
        for a, v in sorted(by_arm.items()):
            only = v - set.union(*[x for k, x in by_arm.items() if k != a])
            print(f"  only arm {a.upper()}: {len(only)}")
    print(f"\nMark each row y or n in the first column of:\n  {LOCAL/'adjudicate.tsv'}")
    print("  y = the tell really is present on that sentence")
    print("  n = false positive")


if __name__ == "__main__":
    main()
