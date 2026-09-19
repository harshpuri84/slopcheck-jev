"""Render findings for a terminal or as JSON."""
import json

RED, YEL, DIM, OFF = "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def as_json(findings, stats):
    return json.dumps({"findings": [f.dict() for f in findings], "stats": stats}, indent=2)


def as_text(findings, stats, color=True, path=""):
    r, y, d, o = (RED, YEL, DIM, OFF) if color else ("", "", "", "")
    if not findings:
        return f"{d}slopcheck: clean, {stats['words']} words, {stats['ms']:.0f} ms{o}"
    lines = [f"{r}slopcheck{o} {path}  {len(findings)} findings in {stats['words']} words"]
    for f in findings:
        tag = f"{r}jev{o}" if f.layer == "jev" else f"{y}lex{o}"
        ref = f"unslop {f.unslop}" if f.unslop else "no-ai-slop"
        loc = f"L{f.line}" if f.line else "doc"
        lines.append(f"  {loc:>5} {tag} {f.name}  {d}({ref}, {f.detail}){o}")
        if f.quote:
            lines.append(f"        {d}> {f.quote[:100]}{o}")
        lines.append(f"        {f.fix}")
    lines.append(f"{d}{stats['ms']:.0f} ms, {stats['calls']} Jev call(s), "
                 f"${stats['cost']:.6f}{o}")
    return "\n".join(lines)
