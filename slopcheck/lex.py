"""Split prose into numbered units and catch the tells a regex can catch.

The unit is a sentence. Jev is only ever allowed to point at a unit this module
produced, which is why it cannot fabricate a quoted line.
"""
import re
from dataclasses import dataclass, field

# Fenced code, inline code, and link targets are not prose. Blank them before
# splitting so a URL full of hyphens never reads as an em dash.
FENCE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
INLINE = re.compile(r"`[^`\n]+`")
LINK = re.compile(r"\]\([^)]*\)")
URL = re.compile(r"https?://\S+")

# Splitter guards. A unit ending in one of these did not really end.
ABBREV = re.compile(
    r"(?:\b[A-Z]|\bMr|\bMrs|\bMs|\bDr|\bProf|\bInc|\bLtd|\bJan|\bFeb|\bMar|\bApr"
    r"|\bJun|\bJul|\bAug|\bSep|\bSept|\bOct|\bNov|\bDec|\be\.g|\bi\.e|\betc|\bvs"
    r"|\bapprox|\bNo|\bfig|\bcf|\bp)\.$"
)
# Fixed-width lookbehind only. Python re cannot do variable-width.
SPLIT = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z\"'(\[])")


def sentences(body):
    """Split, then glue back the pieces an abbreviation or a decimal broke."""
    parts, out = SPLIT.split(body), []
    for part in parts:
        if out and (ABBREV.search(out[-1]) or re.search(r"\d\.$", out[-1])):
            out[-1] = out[-1] + " " + part
        else:
            out.append(part)
    return [p.strip() for p in out if p.strip()]


@dataclass
class Unit:
    """One numbered sentence. `n` is what Jev sees and points at."""
    n: int
    text: str          # masked: code and URLs blanked. This is what Jev reads.
    line: int          # 1-based source line the unit starts on
    kind: str          # prose | heading | bullet
    raw: str = ""      # the original source line, for quoting back to the user


@dataclass
class LexHit:
    tell: str
    name: str
    unit: int          # 0 when the hit is document-wide
    line: int
    quote: str
    detail: str
    fix: str
    layer: str = "lex"
    p: float = 1.0     # a regex match is certain
    unslop: object = None


@dataclass
class Lexed:
    units: list = field(default_factory=list)
    hits: list = field(default_factory=list)
    words: int = 0
    masked: str = ""


def _mask(text):
    """Blank out code and URLs, preserving offsets so line numbers stay true."""
    def blank(m):
        return re.sub(r"\S", " ", m.group(0))
    for pat in (FENCE, INLINE, LINK, URL):
        text = pat.sub(blank, text)
    return text


def split(text, source=None):
    """Numbered units, in document order. Headings and bullets are their own unit.

    `text` is masked and decides the boundaries. `source` supplies the original
    line for quoting, so a blanked URL never reaches the report.
    """
    src = (source or text).splitlines()
    units, n = [], 0
    for lineno, raw in enumerate(text.splitlines(), 1):
        orig = src[lineno - 1].strip() if lineno <= len(src) else raw.strip()
        s = raw.strip()
        if not s:
            continue
        if re.match(r"^#{1,6}\s+", s):
            n += 1
            units.append(Unit(n, s, lineno, "heading", orig))
            continue
        kind = "bullet" if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", s) else "prose"
        body = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", s)
        cursor = 0
        for part in sentences(body):
            n += 1
            # Masking preserved offsets, so the same slice of the raw line is the
            # original sentence. Fall back to the whole line if the slice misses.
            i = body.find(part, cursor)
            quote = orig
            if i >= 0:
                cursor = i + len(part)
                off = raw.find(body)
                if off >= 0 and off + i + len(part) <= len(src[lineno - 1]):
                    cand = src[lineno - 1][off + i: off + i + len(part)].strip()
                    if cand:
                        quote = cand
            units.append(Unit(n, part, lineno, kind, quote))
    return units


def _unit_at(units, lineno):
    for u in units:
        if u.line == lineno:
            return u
    return None


def run(text, cfg):
    """Split, then apply every lex tell. Returns units, hits and a prose word count.

    Tells dispatch on `kind`:
      pattern  per-line regex
      words    per-line, word-boundary matched
      phrases  per-line substring, case-insensitive
      density  document-level rate, matches per N words
      length   per-unit word count
    """
    masked = _mask(text)
    units = split(masked, text)
    lex, hits = cfg["lex"], []
    src = text.splitlines()
    words = len(re.findall(r"\b[\w'-]+\b", masked))

    def add(tid, name, unit, line, quote, detail, fix, unslop):
        hits.append(LexHit(tid, name, unit, line, quote, detail, fix, unslop=unslop))

    for lineno, raw in enumerate(masked.splitlines(), 1):
        if not raw.strip():
            continue
        u = _unit_at(units, lineno)
        src_line = src[lineno - 1].strip() if lineno <= len(src) else raw.strip()
        un, uq = (u.n, u.raw or src_line) if u else (0, src_line)
        low = raw.lower()

        for tid, t in lex.items():
            kind = t.get("kind", "pattern")
            if kind == "pattern":
                for m in re.finditer(t["pattern"], raw, re.M):
                    add(tid, t["name"], un, lineno, uq,
                        f"matched {m.group(0)[:40]!r}", t["fix"], t.get("unslop"))
            elif kind == "words":
                for w in t["words"]:
                    for m in re.finditer(rf"(?<![\w-]){re.escape(w)}(?![\w-])", low):
                        add(tid, f"{t['name']}: {w}", un, lineno, uq,
                            f"{w!r} at column {m.start() + 1}", t["fix"], t.get("unslop"))
            elif kind == "phrases":
                for ph in t["phrases"]:
                    i = low.find(ph)
                    while i >= 0:
                        add(tid, f"{t['name']}: {ph!r}", un, lineno, uq,
                            f"at column {i + 1}", t["fix"], t.get("unslop"))
                        i = low.find(ph, i + len(ph))

    for tid, t in lex.items():
        if t.get("kind") == "density" and words:
            n = len(re.findall(t["pattern"], masked))
            allowed = max(1, words // t["per_words"])
            if n > allowed:
                add(tid, t["name"], 0, 0, "",
                    f"{n} bold runs in {words} words, {allowed} is the ceiling at "
                    f"1 per {t['per_words']}", t["fix"], t.get("unslop"))
        elif t.get("kind") == "length":
            for un_ in units:
                n = len(re.findall(r"\b[\w'-]+\b", un_.text))
                if n > t["max_words"]:
                    add(tid, t["name"], un_.n, un_.line, un_.raw,
                        f"{n} words, over {t['max_words']}", t["fix"], t.get("unslop"))

    return Lexed(units=units, hits=hits, words=words, masked=masked)
