"""Local demo server. Shows what Jev returns, not just what slopcheck concludes.

  python -m slopcheck.serve          # http://localhost:8765
  python -m slopcheck.serve --port 9000

The API key stays in this process. The browser never sees it.

Two endpoints, matching the two calls, so the architecture is visible in the UI
rather than hidden behind one spinner:

  POST /api/detect   15 nouls over the passage, in ONE Jev call. Returns every
                     probability, not just the ones over threshold.
  POST /api/locate   one choice per fired tell, over the numbered units.
"""
import argparse
import json
import pathlib
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml

from . import gate, judge, lex

HERE = pathlib.Path(__file__).parent
CFG = yaml.safe_load((HERE / "tells.yaml").read_text())
WEB = HERE / "web"
SAMPLES = pathlib.Path(__file__).parent.parent / "bench/corpus"


def samples():
    out = []
    for p in sorted(SAMPLES.glob("*.md")):
        out.append({"id": p.stem, "dirty": p.stem.startswith("dirty"),
                    "text": p.read_text().strip()})
    return out


def tell_meta():
    """Everything the UI needs to draw a bar: label, threshold, source rule."""
    return [{"id": tid, "name": t["name"], "threshold": t["threshold"],
             "unslop": t.get("unslop"), "fix": t["fix"]}
            for tid, t in CFG["jev"].items()]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/boot":
            return self._send(200, {"tells": tell_meta(),
                                    "band": CFG["meta"]["undecided_band"],
                                    "model": CFG["meta"]["model"],
                                    "samples": samples()})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            b = self._body()
            text = (b.get("text") or "").strip()
            if not text:
                return self._send(400, {"error": "no text"})

            if self.path == "/api/detect":
                lexed = lex.run(text, CFG)
                t0 = time.perf_counter()
                probs, ms, usage = judge.detect(text, CFG)
                fired, undecided = gate.fired(probs, CFG)
                return self._send(200, {
                    "probs": probs, "fired": fired,
                    "undecided": [t for t, _ in undecided],
                    "ms": round(ms), "wall_ms": round((time.perf_counter() - t0) * 1000),
                    "tokens": usage.get("input_tokens"),
                    "cost": judge.cost_usd(usage),
                    "questions": len(CFG["jev"]),
                    "units": [{"n": u.n, "text": u.text, "raw": u.raw, "line": u.line}
                              for u in lexed.units],
                    "lex": [{"tell": h.tell, "name": h.name, "line": h.line,
                             "quote": h.quote, "detail": h.detail, "fix": h.fix,
                             "unslop": h.unslop} for h in lexed.hits],
                    "words": lexed.words})

            if self.path == "/api/locate":
                lexed = lex.run(text, CFG)
                ids = b.get("fired") or []
                picked, ms, usage = judge.locate(lexed.units, ids, CFG)
                return self._send(200, {
                    "picked": {k: {"unit": v[0], "confidence": v[1]}
                               for k, v in picked.items()},
                    "ms": round(ms), "tokens": usage.get("input_tokens"),
                    "cost": judge.cost_usd(usage)})

            self._send(404, {"error": "not found"})
        except judge.JevError as e:
            self._send(502, {"error": str(e)})
        except Exception as e:
            self._send(500, {"error": f"{type(e).__name__}: {e}"})


def main():
    ap = argparse.ArgumentParser(prog="slopcheck.serve")
    ap.add_argument("--port", type=int, default=8781)
    a = ap.parse_args()
    try:
        judge.api_key()
    except judge.JevError as e:
        sys.exit(f"{e}\nPut it in .env as TYPESAFE_API_KEY=... and try again.")
    print(f"slopcheck demo on http://localhost:{a.port}")
    print(f"model {CFG['meta']['model']}, {len(CFG['jev'])} questions per call")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
