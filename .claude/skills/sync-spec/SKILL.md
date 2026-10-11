---
name: sync-spec
description: 出典（docs/design の節・mock のファイル）が変わった docs/spec を追従させ、出典のハッシュを記録し直す
---

`docs/spec/` は `docs/design/` と `mock/` から導くもの。出典が変わると `scripts/docs_check.py` が赤くなる。

## 手順
1. `python3 scripts/docs_check.py --stale` で、追従が要る spec と出典を一覧にする。
2. 出典ごとに、何が変わったかを読む（`git log -p -n 5 -- <出典のファイル>`、未コミットなら `git diff -- <出典のファイル>`）。
3. spec を直す。
   - 出典の変更で、規則・例・ID の何が変わるかを反映する。ID は使い回さない（消した規則の ID は欠番にする）
   - 出典から一意に決まらない変更は spec に書かず、`docs/discussions/` に status: open で出して止める
   - 理由は spec に書かない
4. `python3 scripts/docs_check.py --stamp <spec のファイル>` でハッシュを記録し直す。
   **spec の中身を直さずに stamp だけするのは禁止。** 出典の変更が spec に影響しないと判断したときは、そう判断した理由を PR に書く。
5. 変わった規則 ID を参照しているテストと Issue を `grep` で探し、直す必要があるものを列挙する。

## 報告
- 出典の変更（1行ずつ）と、それに対応する spec の変更
- stamp だけで済ませた出典があれば、その理由
- 影響を受けるテスト・Issue
