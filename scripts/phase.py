#!/usr/bin/env python3
"""開発の手順のうち、いまどこにいるかをリポジトリの状態だけから判定する。

  python3 scripts/phase.py           # 段階の一覧と、次にやること
  python3 scripts/phase.py --json    # /dev が読む
  python3 scripts/phase.py --done    # 全段階が済んでいれば exit 0

段階は上から順に判定し、最初に済んでいない段階を「今ここ」とする。
前の段階の条件が崩れれば（例: モックが変わって spec が古くなった）、自動でそこへ戻る。

人間の判断が要る段階では、AI は docs/discussions/ に議論を書いて止まる。
人間が「## 結論」を書いたら、AI が decisions.md・design・設定に清書する。
"""

import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
RULE_ID = re.compile(r"\bR-\d+\b")


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return {}
    end = lines.index("---", 1)
    return {m[1]: m[2].strip() for line in lines[1:end] if (m := re.match(r"^(\w+):\s*(.*)$", line))}


def conclusion(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^## 結論\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    body = m[1] if m else ""
    body = re.sub(r"（adopted / rejected にしたら書く）|<!--.*?-->", "", body, flags=re.S)
    return body.strip()


def discussions() -> list[Path]:
    return [p for p in sorted((DOCS / "discussions").glob("*.md")) if p.name != "README.md" and not p.name.startswith("_")]


def specs() -> list[Path]:
    """TODO が残っていない spec だけを、spec として数える。"""
    out = []
    for p in sorted((DOCS / "spec").glob("**/*.md")):
        if p.name == "README.md" or p.name.startswith("_"):
            continue
        if "TODO" not in p.read_text(encoding="utf-8"):
            out.append(p)
    return out


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def phases() -> list[dict]:
    has_mock = (ROOT / "mock").is_dir() and any((ROOT / "mock").glob("*.html"))
    today = date.today().isoformat()
    result = []

    def add(n, name, done, owner="", action="", na=False):
        result.append({"n": n, "name": name, "done": done or na, "na": na, "owner": owner, "action": action})

    add(1, "リポジトリ", True)

    # 2. パック
    if not has_mock:
        add(2, "パック（mock-replica）", True, na=True)
    else:
        pending = (ROOT / "packs" / "mock-replica").exists() or (ROOT / "AGENTS.mock-replica.md").exists()
        installed = (ROOT / "scripts" / "vrt.py").exists()
        add(2, "パック（mock-replica）", installed and not pending, "AI",
            "packs/mock-replica/README.md の「入れ方」に従って取り込む。AGENTS.mock-replica.md の3行を AGENTS.md に移してから消し、packs/ を消す")

    # 3. 評価のステップ
    steps = [s for s in run(["./scripts/check.sh", "--list"]).stdout.splitlines() if s.strip()]
    add(3, "評価のステップ", bool(steps), "人間が結論 → AI が清書",
        f"技術と check.sh の STEPS の案を docs/discussions/{today}-evaluation.md に書いて止まる。"
        "結論が書かれたら、check.sh・依存・CI を清書する")

    # 4. 仕様
    stale = run(["python3", "scripts/docs_check.py", "--stale"]).stdout.strip()
    is_stale = bool(stale) and stale != "stale なし"
    spec_list = specs()
    need = (DOCS / "spec" / "mock.md") if has_mock else None
    spec_ok = (need.exists() if need else bool(spec_list)) and not is_stale
    add(4, "仕様（docs/spec）", spec_ok, "AI",
        ("出典が変わった spec を /sync-spec で追従させる" if is_stale else
         "/mock-spec でモックから docs/spec/mock.md・fixtures・vrt.json・未定義の議論を作る" if has_mock else
         "docs/design から docs/spec を導き、--stamp で出典を記録する（design が TODO なら、議論を書いて止まる）"))

    # 5. 未定義（open の議論）
    open_ = [p for p in discussions() if frontmatter(p).get("status") == "open"]
    waiting = [p for p in open_ if not conclusion(p)]
    ready = [p for p in open_ if conclusion(p)]
    if waiting:
        add(5, "未定義（open の議論）", False, "人間",
            "結論を書く: " + ", ".join(rel(p) for p in waiting))
    else:
        add(5, "未定義（open の議論）", not ready, "AI（清書）",
            "結論が書かれた議論を清書する: " + ", ".join(rel(p) for p in ready) +
            "。decisions.md に1項目、design に反映、status を adopted にして decision を書き、/sync-spec")

    # 6. 評価関数（spec の全規則がテストから参照されている）
    ids = sorted({i for p in spec_list for i in RULE_ID.findall(p.read_text(encoding="utf-8"))},
                 key=lambda s: int(s[2:]))
    tests_text = "\n".join(p.read_text(encoding="utf-8", errors="ignore")
                           for p in (ROOT / "tests").glob("**/*") if p.is_file())
    missing = [i for i in ids if not re.search(rf"\b{i}\b", tests_text)]
    add(6, "評価関数（テスト）", bool(ids) and not missing, "AI",
        ("/mock-tests" if has_mock else "spec の規則ごとにテストを書く") +
        ("。テストから参照されていない規則: " + ", ".join(missing) if missing else "") +
        "。テスト名か docstring に規則 ID を書く。実装がない状態で check が赤くなることを確かめる")

    # 7. 実装
    green = run(["./scripts/check.sh"]).returncode == 0 if all(p["done"] for p in result) else False
    add(7, "実装", green, "AI",
        "check が緑になるまで実装する（画面ごとなら python3 scripts/vrt.py --only <name> を Done にする）")

    # 8. 評価を疑う
    res = ROOT / ".agent" / "mutate-result.json"
    ok8, why = False, "まだ /mutate を回していない"
    if res.exists():
        data = json.loads(res.read_text(encoding="utf-8"))
        tree = run(["git", "ls-tree", "-r", "HEAD", "--", "tests", "scripts/check.sh"]).stdout
        current = hashlib.sha256(tree.encode()).hexdigest()[:12]
        if data.get("eval_tree") != current:
            why = "評価関数（tests/・check.sh）が変わったあとの /mutate の結果がない（変更はコミットしてから回す）"
        elif data.get("survived", 1):
            why = f"生き残り {data['survived']} 個。落とすテストを足して回し直す"
        else:
            ok8 = True
    add(8, "評価を疑う（/mutate）", ok8, "AI（別の文脈）", why)
    return result


def main() -> int:
    ps = phases()
    current = next((p for p in ps if not p["done"]), None)
    if "--done" in sys.argv:
        return 0 if current is None else 1
    if "--json" in sys.argv:
        print(json.dumps({"current": current, "phases": ps}, ensure_ascii=False, indent=2))
        return 0
    for p in ps:
        mark = "–" if p["na"] else "✓" if p["done"] else "✗"
        here = "  ← 今ここ" if p is current else ""
        print(f"{p['n']} {mark} {p['name']}{here}")
    if current:
        print(f"\n次: [{current['owner']}] {current['action']}")
    else:
        print("\n全段階が済んでいる")
    return 0


if __name__ == "__main__":
    sys.exit(main())
