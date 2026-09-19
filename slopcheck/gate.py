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


def assemble(lexed, probs, cfg):
    """Merge lex hits and Jev findings into one ordered report."""
    findings = [Finding(h.tell, h.name, "lex", h.line, h.unit, h.quote,
                        h.p, h.detail, h.fix, h.unslop) for h in lexed.hits]
    for tid in fired(probs, cfg)[0] if probs else []:
        t = cfg["jev"][tid]
        findings.append(Finding(
            tid, t["name"], "jev", 0, 0, "", probs[tid],
            f"p={probs[tid]:.2f}, threshold {t['threshold']}",
            t["fix"], t.get("unslop")))
    findings.sort(key=lambda f: (f.layer == "jev", f.line, -f.p))
    return findings


def assemble_blocks(lexed, blocks, doc_probs, cfg):
    """Paragraph mode. Block-scope tells per block, document-scope tells once."""
    findings = [Finding(h.tell, h.name, "lex", h.line, h.unit, h.quote,
                        h.p, h.detail, h.fix, h.unslop) for h in lexed.hits]
    for line, text, probs in blocks:
        for tid in fired(probs, cfg)[0]:
            t = cfg["jev"][tid]
            findings.append(Finding(
                tid, t["name"], "jev", line, 0, text[:110], probs[tid],
                f"p={probs[tid]:.2f}, threshold {t['threshold']}",
                t["fix"], t.get("unslop")))
    for tid in fired(doc_probs, cfg)[0] if doc_probs else []:
        t = cfg["jev"][tid]
        findings.append(Finding(
            tid, t["name"], "jev", 0, 0, "", doc_probs[tid],
            f"p={doc_probs[tid]:.2f}, whole document",
            t["fix"], t.get("unslop")))
    findings.sort(key=lambda f: (f.line, f.layer == "jev", -f.p))
    return findings
