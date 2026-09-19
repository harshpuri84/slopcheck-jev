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

VAULT = pathlib.Path.home() / "Documents/Harsh OS/05-Areas/Career/LinkedIn Engine/drafts"
OUT = pathlib.Path(__file__).parent / "local"

# provenance: draft = Claude wrote it, no hook pass. published = Harsh's own text.
SOURCES = [
    ("jev-copy",     "typesafe-jev/POST-COPY.md",                          "draft",     "section:Carousel copy"),
    ("stripe-copy",  "stripe-openrouter/POST-COPY.md",                     "draft",     "section:Recommended"),
    ("86-v1",        "2026-08-24 - The 86 fields I refused to grade.md",   "draft",     "quote"),
    ("86-t2",        "2026-08-25 - The 86 fields I refused to grade (T2).md", "draft",  "quote"),
    ("86-recipe",    "2026-08-25 - The 4-step field audit (recipe).md",    "draft",     "quote"),
    ("86-v4",        "2026-08-25 - The field audit with tool (v4).md",     "draft",     "quote"),
    ("jev-final",    "typesafe-jev/POST-FINAL.txt",                        "published", "all"),
    ("jev-post2",    "typesafe-jev/POST-2.txt",                            "published", "all"),
    ("jev-post3",    "typesafe-jev/POST-3.txt",                            "published", "all"),
]


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


def main():
    OUT.mkdir(exist_ok=True)
    cfg = yaml.safe_load((pathlib.Path(__file__).parent.parent
                          / "slopcheck/slopcheck/tells.yaml").read_text()
                         if False else
                         (pathlib.Path(__file__).parent.parent / "slopcheck/tells.yaml").read_text())
    passages, rows, sid = [], [], 0
    for pid, rel, prov, rule in SOURCES:
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
