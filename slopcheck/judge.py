"""Ask Jev which tells a passage contains, then which line each one is on.

Call 1: one noul per semantic tell, over the whole passage. Always runs.
Call 2: one choice per fired tell, over the numbered units. Usually does not run.

Jev is never asked whether a human should care. That is policy and it lives in
gate.py. Jev is never asked to write a quote either; it selects a unit number
that lex.py produced.
"""
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

NONE = "__no_line__"
PRICE_PER_MTOK = 0.042  # USD per million input tokens, measured Sep 2026


class JevError(RuntimeError):
    pass


def api_key(explicit=None):
    if explicit:
        return explicit
    if os.environ.get("TYPESAFE_API_KEY"):
        return os.environ["TYPESAFE_API_KEY"]
    extra = os.environ.get("SLOPCHECK_ENV")
    for p in ([pathlib.Path(extra)] if extra else []) + [
            pathlib.Path.cwd() / ".env",
            pathlib.Path(__file__).resolve().parent.parent / ".env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith("TYPESAFE_API_KEY="):
                    v = line.split("=", 1)[1].strip()
                    if v:
                        return v
    raise JevError("no TYPESAFE_API_KEY in env or .env")


def _post(url, body, key, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.load(r)
    except urllib.error.HTTPError as e:
        raise JevError(f"HTTP {e.code}: {e.read().decode()[:200]}") from None
    except Exception as e:
        raise JevError(f"{type(e).__name__}: {e}") from None
    return out, (time.perf_counter() - t0) * 1000


def detect(text, cfg, key=None, timeout=20):
    """Call 1. One noul per semantic tell. Returns {tell_id: p_yes}, ms, tokens."""
    meta, jev = cfg["meta"], cfg["jev"]
    questions = {
        tid: {"type": "noul",
              "instructions": t["instructions"].strip(),
              "criteria": {k: str(v).strip() for k, v in t["criteria"].items()}}
        for tid, t in jev.items()}
    out, ms = _post(meta["url"],
                    {"state": {"passage": text}, "model": meta["model"], "questions": questions},
                    api_key(key), timeout)
    probs = {tid: a.get("noul", 0.0) for tid, a in out["answers"].items()}
    return probs, ms, out.get("usage", {})


def locate(units, tell_ids, cfg, key=None, timeout=20):
    """Call 2. One choice per fired tell, over the numbered units.

    The options are exactly the units lex.py produced, so a returned line is
    always a line that exists in the source.
    """
    if not tell_ids or not units:
        return {}, 0.0, {}
    meta, jev = cfg["meta"], cfg["jev"]
    options = {str(u.n): u.text for u in units}
    options[NONE] = "No line in the list matches the description"
    numbered = "\n".join(f"{u.n}. {u.text}" for u in units)
    questions = {
        tid: {"type": "choice",
              "instructions": jev[tid]["locate"].strip(),
              "criteria": options}
        for tid in tell_ids}
    out, ms = _post(meta["url"],
                    {"state": {"passage": numbered}, "model": meta["model"],
                     "questions": questions},
                    api_key(key), timeout)
    picked = {}
    for tid, a in out["answers"].items():
        c = a.get("choice")
        if c and c != NONE and c.isdigit():
            picked[tid] = (int(c), a.get("confidence", 0.0))
    return picked, ms, out.get("usage", {})


def cost_usd(*usages):
    tok = sum((u or {}).get("input_tokens") or 0 for u in usages)
    return tok * PRICE_PER_MTOK / 1e6
