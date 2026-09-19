"""Pull prose out of the vault drafts and emit a sheet for Harsh to label.

Local only. Nothing this touches ever ships in the repo; the published corpus is
synthetic. Run from the repo root.

  python bench/extract.py            # writes bench/local/sheet.tsv + passages.json
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import yaml
from slopcheck import lex

OUT = pathlib.Path(__file__).parent / "local"
# Your corpus map. Gitignored, because the file names alone say what you write
# about. Copy sources.example.json to bench/local/sources.json and edit it.
MAP = OUT / "sources.json"


def carve(text, rule):
    """Pull the post body out of a working file full of notes and metadata."""
    if rule == "all":
        return text
    if rule == "quote":
        out = [re.sub(r"^>\s?", "", ln) for ln in text.splitlines() if ln.startswith(">")]
        return "\n".join(out)
    if rule.startswith("section:"):
        want = rule.split(":", 1)[1]
        lines, keep, body = text.splitlines(), False, []
        for ln in lines:
            if ln.startswith("## "):
                keep = want.lower() in ln.lower()
                continue
            if ln.startswith("---") and keep:
                break
            if keep:
                body.append(ln)
        return "\n".join(body)
    raise ValueError(rule)


def load_sources():
    if not MAP.exists():
        sys.exit(f"no {MAP}. Copy bench/sources.example.json there and edit it.")
    m = json.loads(MAP.read_text())
    return pathlib.Path(m["root"]).expanduser(), m["sources"]


def main():
    OUT.mkdir(exist_ok=True)
    VAULT, SOURCES = load_sources()
    cfg = yaml.safe_load((pathlib.Path(__file__).parent.parent
                          / "slopcheck/slopcheck/tells.yaml").read_text()
                         if False else
                         (pathlib.Path(__file__).parent.parent / "slopcheck/tells.yaml").read_text())
    passages, rows, sid = [], [], 0
    for s_ in SOURCES:
        pid, rel, prov, rule = s_["id"], s_["path"], s_["provenance"], s_["carve"]
        p = VAULT / rel
        if not p.exists():
            print(f"MISSING {p}", file=sys.stderr)
            continue
        body = carve(p.read_text(), rule).strip()
        if not body:
            print(f"EMPTY after carve: {rel}", file=sys.stderr)
            continue
        units = lex.run(body, cfg).units
        passages.append({"id": pid, "provenance": prov, "file": rel,
                         "text": body, "units": len(units)})
        for u in units:
            if u.kind == "heading" or len(u.raw.split()) < 4:
                continue
            sid += 1
            rows.append((sid, pid, prov, u.n, u.raw.replace("\t", " ")))
    (OUT / "passages.json").write_text(json.dumps(passages, indent=2))
    with (OUT / "sheet.tsv").open("w") as f:
        f.write("id\tpassage\tprovenance\tunit\ttells\tsentence\n")
        for sid_, pid, prov, n, txt in rows:
            f.write(f"{sid_}\t{pid}\t{prov}\t{n}\t\t{txt}\n")
    d = sum(1 for p in passages if p["provenance"] == "draft")
    print(f"passages: {len(passages)} ({d} draft, {len(passages)-d} published)")
    print(f"sentences to label: {len(rows)}")
    print(f"wrote {OUT/'sheet.tsv'} and {OUT/'passages.json'}")


if __name__ == "__main__":
    main()
