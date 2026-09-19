"""Drive the running demo and save frames, so ffmpeg can build a real video.

  python demo/record.py          # needs the server up on 8781

Frames are PNGs of the actual app in a real browser. Nothing is reconstructed.
The bar animation is 450ms, so the run is sampled at 100ms around it.
"""
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).parent / "frames"
URL = "http://localhost:8781"
_p = pathlib.Path(__file__).parent / "post.txt"
POST = _p.read_text() if _p.exists() else (
    pathlib.Path(__file__).parent.parent / "bench/corpus/clean-01.md").read_text()

n = 0
def shot(page, hold=1):
    """hold = how many identical frames to emit, so a beat lands on screen."""
    global n
    for _ in range(hold):
        n += 1
        page.screenshot(path=str(OUT / f"f{n:04d}.png"))

def run():
    OUT.mkdir(exist_ok=True)
    for f in OUT.glob("*.png"):
        f.unlink()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 820},
                        device_scale_factor=2)
        pg.goto(URL, wait_until="networkidle")

        # 1. a dirty passage
        pg.click("text=dirty-02")
        shot(pg, 8)
        pg.click("#go")
        # call 1 is ~600ms. Sample every 100ms so the bars filling is real footage.
        for _ in range(22):
            shot(pg); time.sleep(0.1)
        pg.wait_for_function("document.querySelector('#s-ms').textContent.includes('ms')",
                             timeout=20000)
        shot(pg, 10)

        # 2. the findings
        pg.mouse.wheel(0, 700); time.sleep(0.25); shot(pg, 8)
        pg.mouse.wheel(0, 700); time.sleep(0.25); shot(pg, 8)
        pg.mouse.wheel(0, -1400); time.sleep(0.25); shot(pg, 4)

        # 3. the post about the detector, through the detector
        pg.fill("#t", POST)
        shot(pg, 8)
        pg.click("#go")
        for _ in range(22):
            shot(pg); time.sleep(0.1)
        pg.wait_for_function("document.querySelector('#s-ms').textContent.includes('ms')",
                             timeout=20000)
        shot(pg, 6)
        pg.mouse.wheel(0, 500); time.sleep(0.25); shot(pg, 14)
        b.close()
    print(f"{n} frames in {OUT}")

if __name__ == "__main__":
    run()
