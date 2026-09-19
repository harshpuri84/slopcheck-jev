"""Record adjudication verdicts by row number.

  python bench/mark.py 1y 2y 3y 4n 5y

Row numbers come from bench/local/numbering.json, which pool.py writes. Writes
the verdict into the first column of adjudicate.tsv.
"""
import json
import pathlib
import sys

LOCAL = pathlib.Path(__file__).parent / "local"


def main(args):
    num = json.loads((LOCAL / "numbering.json").read_text())
    verdicts = {}
    for a in args:
        a = a.strip().lower().rstrip(",")
        if not a:
            continue
        n, v = a[:-1], a[-1]
        if v not in "yn" or not n.isdigit() or n not in num:
            sys.exit(f"bad token {a!r}. Use forms like 4n or 12y, row 1-{len(num)}.")
        verdicts[tuple(num[n])] = v

    p = LOCAL / "adjudicate.tsv"
    lines = p.read_text().splitlines()
    out, hit = [lines[0]], 0
    for line in lines[1:]:
        c = line.split("\t")
        if len(c) >= 6:
            key = (c[1], int(c[3]), c[4])
            if key in verdicts:
                c[0] = verdicts[key]
                hit += 1
        out.append("\t".join(c))
    p.write_text("\n".join(out) + "\n")

    done = sum(1 for l in out[1:] if l.split("\t")[0].strip())
    print(f"recorded {hit} of {len(verdicts)} | adjudicated {done}/{len(lines)-1}, "
          f"{len(lines)-1-done} left")


if __name__ == "__main__":
    main(sys.argv[1:])
