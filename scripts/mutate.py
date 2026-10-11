#!/usr/bin/env python3
"""誤実装（ミュータント）を1つずつ当てて scripts/check.sh を回し、評価関数がそれを落とせるかを測る。

  python3 scripts/mutate.py .agent/mutants.json

ミュータントの書式（JSON の配列）。edits は「ファイル, 置換前, 置換後」の組で、置換前はファイル中に1回だけ現れること。
  [{"id": "M01_desc_hardcoded", "why": "説明文をモックの文言で直書き",
    "edits": [["app/templates/detail.html", "{{ project.description }}", "受発注…"]]}]

作業ツリーには触らない。HEAD を別の git worktree（.agent/mutwt）に展開し、そこで当てては元の内容を書き戻す。
依存の準備が要るなら MUTATE_SETUP に書く（例: MUTATE_SETUP="uv sync -q"）。
結果は標準出力の表と .agent/mutate-result.json。各ミュータントの check のログは .agent/mutate-logs/<id>.log に残る。
生き残りが1つでもあれば exit 1。
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WT = ROOT / ".agent" / "mutwt"
LOGS = ROOT / ".agent" / "mutate-logs"


def sh(cmd: list[str], cwd: Path, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False, **kw)


def eval_tree() -> str:
    """評価関数（tests/ と scripts/check.sh）の、HEAD での中身を表すハッシュ。"""
    r = sh(["git", "ls-tree", "-r", "HEAD", "--", "tests", "scripts/check.sh"], ROOT)
    return hashlib.sha256(r.stdout.encode()).hexdigest()[:12]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    mutants = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    LOGS.mkdir(parents=True, exist_ok=True)

    if WT.exists():
        sh(["git", "worktree", "remove", "--force", str(WT)], ROOT)
    r = sh(["git", "worktree", "add", "--detach", str(WT), "HEAD"], ROOT)
    if r.returncode:
        print(r.stderr)
        return 2
    try:
        if setup := os.environ.get("MUTATE_SETUP"):
            subprocess.run(setup, shell=True, cwd=WT, check=True)
        base = sh(["./scripts/check.sh"], WT)
        if base.returncode:
            print("check.sh が HEAD の時点で赤い。先に緑にすること。\n" + base.stdout)
            return 2

        results = []
        for n, m in enumerate(mutants, 1):
            originals: dict[str, str] = {}
            status = "KILLED"
            for path, old, new in m["edits"]:
                p = WT / path
                text = p.read_text(encoding="utf-8")
                originals.setdefault(path, text)
                if text.count(old) != 1:
                    status = "PATCH-FAIL"
                    break
                p.write_text(text.replace(old, new, 1), encoding="utf-8")
            summary = ""
            if status != "PATCH-FAIL":
                run = sh(["./scripts/check.sh"], WT)
                summary = run.stdout.splitlines()[0] if run.stdout else ""
                status = "KILLED" if run.returncode else "SURVIVED"
                log = WT / ".agent" / "check.log"
                if log.exists():
                    (LOGS / f"{n:02d}_{m['id']}.log").write_text(log.read_text(encoding="utf-8"), encoding="utf-8")
            for path, text in originals.items():
                (WT / path).write_text(text, encoding="utf-8")
            results.append({"id": m["id"], "why": m.get("why", ""), "status": status, "check": summary})
            print(f"{status:10s} {m['id']:40s} {summary}", flush=True)
    finally:
        sh(["git", "worktree", "remove", "--force", str(WT)], ROOT)

    out = ROOT / ".agent" / "mutate-result.json"
    summary = {"eval_tree": eval_tree(), "killed": sum(r["status"] == "KILLED" for r in results),
               "survived": sum(r["status"] == "SURVIVED" for r in results), "mutants": results}
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    killed = sum(r["status"] == "KILLED" for r in results)
    survived = [r for r in results if r["status"] == "SURVIVED"]
    print(f"\n{killed}/{len(results)} killed, {len(survived)} survived -> {out.relative_to(ROOT)}")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
