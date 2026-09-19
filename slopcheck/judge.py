"""Ask Jev which tells a passage contains, then which line each one is on.

One call. One noul per semantic tell, over the whole passage, every time.

There was a second call that pinned each tell to a line. It is gone. Jev returns
typed answers, not text, so the only way to get a quoted sentence was to ask a
second round of questions about lines. That bought one sentence and cost 774ms,
4.6x the tokens, and every defect in the detector: a cap that could only ever
report one instance per tell, a per-line question that fired on 25 of 47 lines,
batching, and two thread pools. The report names the tell and its probability.

Jev is never asked whether a human should care. That is policy, and policy lives
in gate.py.
"""
import concurrent.futures as cf
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

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


def detect(text, cfg, key=None, timeout=20, scope=None):
    """One noul per semantic tell. Returns {tell_id: p_yes}, ms, tokens.

    `scope` filters which tells are asked. A tell marked `scope: document` asks
    about the whole piece (is the LAST line an aphorism, does it OPEN with a
    stock preamble) and is meaningless per paragraph, because every paragraph
    has a first line and a last line.
    """
    meta, jev = cfg["meta"], cfg["jev"]
    if scope == "block":
        jev = {k: v for k, v in jev.items() if v.get("scope") != "document"}
    elif scope == "document":
        jev = {k: v for k, v in jev.items() if v.get("scope") == "document"}
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


def cost_usd(*usages):
    tok = sum((u or {}).get("input_tokens") or 0 for u in usages)
    return tok * PRICE_PER_MTOK / 1e6


def detect_blocks(blocks, cfg, key=None, timeout=20, max_workers=8):
    """One detect call per block, all in flight at once.

    Asking per paragraph gives a line number back, because the answer is about a
    block whose position code already knows. Doing it sequentially costs a round
    trip per paragraph; doing it concurrently costs roughly one.

    `blocks` is [(line_number, text)]. Returns [(line, text, probs)].
    """
    if not blocks:
        return [], 0.0, {}
    key = api_key(key)
    t0 = time.perf_counter()

    def one(b):
        return detect(b[1], cfg, key, timeout, scope="block")

    out, tok = [], 0
    with cf.ThreadPoolExecutor(max_workers=min(max_workers, len(blocks))) as ex:
        for (line, text), (probs, _, usage) in zip(blocks, ex.map(one, blocks)):
            out.append((line, text, probs))
            tok += (usage or {}).get("input_tokens") or 0
    return out, (time.perf_counter() - t0) * 1000, {"input_tokens": tok,
                                                    "calls": len(blocks)}
