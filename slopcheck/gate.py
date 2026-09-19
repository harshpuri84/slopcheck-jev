"""Policy. The only place a decision to report is made.

Jev returns probabilities. This file turns them into findings. Change a
threshold in tells.yaml and nothing re-runs.
"""
from dataclasses import dataclass, asdict


@dataclass
class Finding:
    tell: str
    name: str
    layer: str        # lex | jev
    line: int         # source line, 0 when unknown
    unit: int         # numbered unit, 0 when document-wide
    quote: str
    p: float
    detail: str
    fix: str
    unslop: object = None
    # True when call 1 fired but call 2 could not name a line. Two Jev judgments
    # disagreeing. Reported, but never as a confident finding.
    unlocated: bool = False
    # True when the line was pinned, but the distribution was spread enough that
    # the pin should be read as a suggestion.
    weak_pin: bool = False

    def dict(self):
        return asdict(self)


def fired(probs, cfg):
    """Tells at or above threshold. The undecided band is suppressed, not reported.

    A noul near 0.5 means the model is not answering. Treating that as a weak yes
    is the single easiest way to make a detector useless.
    """
    lo, hi = cfg["meta"]["undecided_band"]
    out, undecided = [], []
    for tid, p in probs.items():
        if tid not in cfg["jev"]:
            continue
        if lo <= p < hi:
            undecided.append((tid, p))
        elif p >= cfg["jev"][tid]["threshold"]:
            out.append(tid)
    return out, undecided


def assemble(lexed, probs, picked, cfg):
    """Merge lex hits and Jev findings into one ordered report."""
    findings = [Finding(h.tell, h.name, "lex", h.line, h.unit, h.quote,
                        h.p, h.detail, h.fix, h.unslop) for h in lexed.hits]
    by_n = {u.n: u for u in lexed.units}
    for tid in fired(probs, cfg)[0] if probs else []:
        t = cfg["jev"][tid]
        n, conf = picked.get(tid, (0, 0.0))
        u = by_n.get(n)
        # Choice confidence is a shape statistic over the distribution, not the
        # winning probability. A spread distribution can still have the right top
        # pick, so keep the line and label the pin weak rather than discarding it.
        weak = u is not None and conf < cfg["meta"].get("locate_min_confidence", 0.0)
        findings.append(Finding(
            tid, t["name"], "jev",
            u.line if u else 0, n,
            u.raw if u else "(whole passage)",
            probs[tid],
            f"p={probs[tid]:.2f}" + (
                (f", line pinned weakly, confidence {conf:.2f} below "
                 f"{cfg['meta']['locate_min_confidence']}" if weak else
                 f", line picked with confidence {conf:.2f}") if u else
                ", call 1 fired but call 2 named no line"),
            t["fix"], t.get("unslop"), unlocated=u is None, weak_pin=weak))
    # Unlocated findings sort last. A reader should see the pinned ones first.
    findings.sort(key=lambda f: (f.unlocated, f.weak_pin, f.line, -f.p))
    return findings
