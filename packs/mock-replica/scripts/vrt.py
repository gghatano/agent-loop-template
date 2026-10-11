"""モックと実装の画面を同じブラウザで撮り、ピクセル差分と console error を数える。

  python scripts/vrt.py              # vrt.json を読む。差分か console error がある画面があれば exit 1
  python scripts/vrt.py --only list  # 1画面だけ

必要なもの: playwright, pillow（Python の開発依存）と Chromium。
差分画像は .agent/vrt/<name>.diff.png（赤 = 不一致の画素）。結果は .agent/vrt/result.json。

vrt.json の例:
  {
    "server": "uv run uvicorn app.main:app --port {port} --log-level warning",
    "viewport": {"width": 1280, "height": 800},
    "screens": [
      {"name": "list", "mock": "mock/list.html", "path": "/projects"},
      {"name": "detail", "mock": "mock/detail.html", "path": "/projects/101"}
    ]
  }
"""

import json
import os
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".agent" / "vrt"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(cmd: str, port: int) -> subprocess.Popen:
    server = subprocess.Popen(shlex.split(cmd.format(port=port)), cwd=ROOT)
    for _ in range(150):
        if server.poll() is not None:
            raise SystemExit(f"FAIL server exited with code {server.returncode}: {cmd}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return server
        except OSError:
            time.sleep(0.1)
    server.kill()
    raise SystemExit(f"FAIL server did not start within 15s: {cmd}")


def launch(p):
    exe = os.environ.get("PW_CHROMIUM") or next(
        (c for c in ["/opt/pw-browsers/chromium"] if Path(c).exists()), None
    )
    return p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()


def shoot(page, url: str, path: Path) -> list[str]:
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url, wait_until="networkidle")
    page.screenshot(path=path, full_page=True)
    return errors


def diff(a: Path, b: Path, out: Path) -> tuple[int, int]:
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    w, h = max(ia.width, ib.width), max(ia.height, ib.height)
    pa, pb = Image.new("RGB", (w, h), "white"), Image.new("RGB", (w, h), "white")
    pa.paste(ia)
    pb.paste(ib)
    mask = ImageChops.difference(pa, pb).convert("L").point(lambda v: 255 if v else 0)
    bad = mask.histogram()[255]
    overlay = pb.copy()
    overlay.paste(Image.new("RGB", (w, h), (255, 0, 0)), mask=mask)
    Image.blend(pb, overlay, 0.6).save(out)
    return bad, w * h


def main() -> int:
    conf = json.loads((ROOT / "vrt.json").read_text(encoding="utf-8"))
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    screens = [s for s in conf["screens"] if only in (None, s["name"])]
    viewport = conf.get("viewport", {"width": 1280, "height": 800})
    OUT.mkdir(parents=True, exist_ok=True)

    port = free_port()
    server = start_server(conf["server"], port)
    results = []
    try:
        with sync_playwright() as p:
            browser = launch(p)
            for s in screens:
                ctx = browser.new_context(viewport=viewport)
                mock_png, app_png = OUT / f"{s['name']}.mock.png", OUT / f"{s['name']}.app.png"
                mock_errors = shoot(ctx.new_page(), (ROOT / s["mock"]).as_uri(), mock_png)
                errors = shoot(ctx.new_page(), f"http://127.0.0.1:{port}{s['path']}", app_png)
                bad, total = diff(mock_png, app_png, OUT / f"{s['name']}.diff.png")
                ok = bad == 0 and not errors
                results.append({**s, "ok": ok, "diff_px": bad, "diff_ratio": bad / total,
                                "console_errors": errors, "mock_console_errors": mock_errors})
                print(f"{'ok  ' if ok else 'FAIL'} {s['name']:12s} diff={bad}px ({bad / total:.4%}) "
                      f"console_errors={len(errors)}")
                for e in errors:
                    print(f"       console: {e}")
                ctx.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)

    (OUT / "result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all(r["ok"] for r in results):
        print(f"差分画像: {OUT.relative_to(ROOT)}/<name>.diff.png（赤 = 不一致）")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
