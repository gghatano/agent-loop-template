#!/usr/bin/env python3
"""docs/ の整合を機械で確かめる。check.sh から毎回呼ばれる。

  python3 scripts/docs_check.py                 # 検査だけ。問題があれば exit 1
  python3 scripts/docs_check.py --stale         # 出典が変わった spec の一覧（/sync-spec が使う）
  python3 scripts/docs_check.py --stamp FILE    # spec の出典ハッシュを今の内容で更新する

検査すること:
  1. spec/: 冒頭の sources に書いた出典（design の節、mock のファイルなど）が存在し、
     記録したハッシュが今の内容と一致する。一致しなければ、出典が変わったのに spec が追従していない
  2. discussions/: status が open / adopted / rejected / superseded のどれか。
     adopted なら decision に docs/decisions.md の見出しを書き、その見出しが実在する
  3. docs/・AGENTS.md・README.md の相対リンク（#見出し を含む）が切れていない

spec の冒頭の書式:
  ---
  sources:
    - docs/design/overview.md#画面 sha256:1a2b3c4d5e6f
    - mock/list.html sha256:0f9e8d7c6b5a
  ---
"""

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
STATUSES = {"open", "adopted", "rejected", "superseded"}
SOURCE_RE = re.compile(r"^\s*-\s+(\S+?)(?:\s+sha256:([0-9a-f]+))?\s*$")
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def slug(text: str) -> str:
    """GitHub と同じ規則で見出しのアンカーを作る（日本語はそのまま残る）。"""
    text = re.sub(r"[`*_~]|<[^>]+>", "", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def strip_code(text: str) -> str:
    return re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)


def headings(text: str) -> dict[str, tuple[int, int]]:
    """アンカー → (見出しの行番号, レベル)。"""
    found, seen = {}, {}
    in_code = False
    for i, line in enumerate(text.splitlines()):
        if line.startswith("```"):
            in_code = not in_code
            continue
        m = None if in_code else HEADING_RE.match(line)
        if m:
            s = slug(m[2])
            n = seen.get(s, 0)
            seen[s] = n + 1
            found[s if n == 0 else f"{s}-{n}"] = (i, len(m[1]))
    return found


def section(path: Path, anchor: str | None) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not anchor:
        return text
    hs = headings(text)
    if anchor not in hs:
        return None
    start, level = hs[anchor]
    lines = text.splitlines()
    end = len(lines)
    for _, (i, lv) in sorted(hs.items(), key=lambda kv: kv[1][0]):
        if i > start and lv <= level:
            end = i
            break
    return "\n".join(line.rstrip() for line in lines[start:end]).strip()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return {}, []
    end = lines.index("---", 1)
    fields, sources, key = {}, [], None
    for line in lines[1:end]:
        if m := re.match(r"^(\w+):\s*(.*)$", line):
            key = m[1]
            fields[key] = m[2].strip()
        elif key == "sources" and line.strip().startswith("- "):
            sources.append(line)
    return fields, sources


def spec_files() -> list[Path]:
    return [p for p in sorted((DOCS / "spec").glob("**/*.md")) if p.name != "README.md" and not p.name.startswith("_")]


def check_spec(path: Path) -> tuple[list[str], list[str]]:
    errors, stale = [], []
    fields, sources = frontmatter(path)
    rel = path.relative_to(ROOT)
    if "sources" not in fields:
        return [f"{rel}: 冒頭に sources がない（どの設計・モックから導いたかを書く）"], []
    for line in sources:
        m = SOURCE_RE.match(line)
        if not m:
            errors.append(f"{rel}: sources の書式が読めない: {line.strip()}")
            continue
        target, recorded = m[1], m[2]
        file, _, anchor = target.partition("#")
        src = ROOT / file
        if not src.exists():
            errors.append(f"{rel}: 出典がない: {file}")
            continue
        body = section(src, anchor or None)
        if body is None:
            errors.append(f"{rel}: 出典の見出しがない: {target}")
        elif recorded is None:
            stale.append(f"{rel}: 出典のハッシュが未記録: {target}（--stamp で記録する）")
        elif digest(body) != recorded:
            stale.append(f"{rel}: 出典が変わった: {target}（/sync-spec で追従してから --stamp）")
    return errors, stale


def check_discussions() -> list[str]:
    errors = []
    decisions = DOCS / "decisions.md"
    known = headings(decisions.read_text(encoding="utf-8")) if decisions.exists() else {}
    for path in sorted((DOCS / "discussions").glob("*.md")):
        if path.name == "README.md" or path.name.startswith("_"):
            continue
        rel = path.relative_to(ROOT)
        fields, _ = frontmatter(path)
        status = fields.get("status")
        if status not in STATUSES:
            errors.append(f"{rel}: status は {'/'.join(sorted(STATUSES))} のどれか（今: {status!r}）")
        elif status == "adopted":
            decision = fields.get("decision", "")
            if not decision:
                errors.append(f"{rel}: adopted なのに decision がない（docs/decisions.md の見出しを書く）")
            elif slug(decision) not in known:
                errors.append(f"{rel}: decision の見出しが docs/decisions.md にない: {decision}")
    return errors


def check_links() -> list[str]:
    errors = []
    files = [p for p in DOCS.glob("**/*.md")] + [ROOT / "AGENTS.md", ROOT / "README.md"]
    for path in files:
        if not path.exists():
            continue
        for target in LINK_RE.findall(strip_code(path.read_text(encoding="utf-8"))):
            if re.match(r"^[a-z]+:", target) or target.startswith("#") and not target[1:]:
                continue
            file, _, anchor = target.partition("#")
            dest = (path.parent / file).resolve() if file else path
            rel = path.relative_to(ROOT)
            if not dest.exists():
                errors.append(f"{rel}: リンク切れ: {target}")
            elif anchor and dest.suffix == ".md" and anchor not in headings(dest.read_text(encoding="utf-8")):
                errors.append(f"{rel}: 見出しがない: {target}")
    return errors


def stamp(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    out = []
    for line in text.splitlines():
        m = SOURCE_RE.match(line)
        if m and line.startswith("  "):
            file, _, anchor = m[1].partition("#")
            body = section(ROOT / file, anchor or None)
            if body is None:
                raise SystemExit(f"出典が見つからない: {m[1]}")
            line = f"  - {m[1]} sha256:{digest(body)}"
        out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"stamped {path.relative_to(ROOT)}")


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--stamp"]:
        for f in args[1:]:
            stamp(ROOT / f)
        return 0

    errors, stale = [], []
    for p in spec_files():
        e, s = check_spec(p)
        errors += e
        stale += s
    if args[:1] == ["--stale"]:
        print("\n".join(stale) or "stale なし")
        return 0
    errors += check_discussions() + check_links()
    for line in errors + stale:
        print(line)
    if errors or stale:
        print(f"docs: {len(errors)} errors, {len(stale)} stale")
        return 1
    print("docs: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
