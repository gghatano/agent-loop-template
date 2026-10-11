# agent-loop-template

AI に仕事を渡せる形へ、開発プロセスそのものを設計するためのリポジトリテンプレート。

人間が持つのは **Goal・評価・エスカレーション基準** の3つだけ。
**実装・観察・修正** は AI がループで回す。

```
Goal (Issue) ─▶ Action ─▶ Observation ─▶ Evaluation (scripts/check.sh) ─▶ Correction ─┐
                  ▲                                                                   │
                  └───────────────────────────────────────────────────────────────────┘
```

## 使い始める（最初の30分）

1. `AGENTS.md` の `TODO` を埋める。**このプロジェクト固有の事情だけ**。一般知識は書かない。
2. `scripts/check.sh` の `TODO` を埋め、`./scripts/check.sh` が通る状態にする。これが唯一の評価関数になる。
3. 最初のタスクを Issue（テンプレート「Agent task」）で書く。Done は機械判定できる形で。
4. 細かい手順を書かずに、まず一度丸投げする: `/goal #<issue番号>`
5. 失敗したら `/postmortem` で原因を4分類して `docs/knowledge/failures.md` に記録する。

docs/ の中身は空のままでいい。AI が実際に失敗した箇所だけが、知識として昇格していく。docs の構成は [`docs/README.md`](docs/README.md)。

## 何がどこにあるか

| ファイル | 持ち主 | 役割 |
|---|---|---|
| `AGENTS.md` | 人間 | 固有の制約・完了条件・エスカレーション基準。短く保つ |
| `scripts/check.sh` | 人間 | 評価関数。AI・Stop hook・CI がすべてこれを呼ぶ |
| `.github/ISSUE_TEMPLATE/` | 人間 | AI の仕事単位（Goal / Done / Constraints） |
| `tasks/current.md` | AI | 今のループの作業メモ。Issue が正、こちらは使い捨て |
| `docs/design/` | 人間 | 人間向けの設計書。正 |
| `docs/spec/` | AI | design と mock から導いた、AI 向けの仕様。出典とハッシュを持ち、出典が変わると check が赤くなる |
| `docs/discussions/` | 両方 | 実装のアイディア・議論。status を持つ |
| `docs/decisions.md` | 人間 | 議論から採用した判断。design への橋 |
| `docs/knowledge/` | AI→人間 | 開発の知識。失敗の4分類ログ（`failures.md`）もここ |
| `scripts/docs_check.py` | — | docs の整合（spec の追従、議論の状態、リンク）を検査する |
| `.claude/hooks/stop-gate.sh` | — | 変更があるのに check が赤いまま止まろうとしたら差し戻す |
| `scripts/loop.sh` | — | ヘッドレスで回す Ralph Loop。check 緑・`.agent/BLOCKED`・無変化・上限回数で止まる |
| `scripts/mutate.py` | — | 誤実装を1つずつ当てて check を回し、生き残りを数える（`/mutate` が使う） |

## スキル

- `/goal <#issue>` — Issue の Done を満たすまで実装→検証→修正を回し、PR を出す
- `/explore <観点>` — コードベースを調査し、見つかった問題を Umbrella Issue の下書きにまとめる
- `/postmortem` — 直前の失敗を Context / Permission / Evaluation / Model に分類して記録
- `/unlearn` — AGENTS.md・スキル・docs を棚卸しし、もう効いていないルールの削除を提案
- `/mutate` — 実装だけを書き換えた誤実装を作って check にぶつけ、評価関数の穴を探す。テストを書いた本人とは別の文脈で回す
- `/sync-spec` — 出典（design・mock）が変わった spec を追従させ、ハッシュを記録し直す

## 失敗の4分類と打ち手

| 分類 | 症状 | 打ち手 |
|---|---|---|
| Context | 固有の制約を知らなかった | `AGENTS.md`・`docs/design/`・`docs/knowledge/` のどれかに**1行**昇格 |
| Permission | 必要なコマンド・権限・秘密情報がなかった | `.claude/settings.json` / CI / 環境を直す |
| Evaluation | 間違っていたのに check が緑だった | `scripts/check.sh` にテスト・検査を足し、`/mutate` で落ちることを確かめる |
| Model | 上3つを満たしても解けない | タスクを割る。人間が持つ。半年後に再挑戦 |

プロンプト改善が効くのは Context だけ。残り3つにプロンプトで対処しない。

## ヘッドレス実行の注意

[利用例](https://github.com/gghatano/agent-loop-example/blob/main/docs/walkthrough.md)で実際に踏んだもの。

- 未信頼のワークスペースでは、`claude -p` は `.claude/settings.json` の allow を無視する。一方で Stop hook は動く。`loop.sh` は許可を `--allowedTools` で明示している
- 許可はコマンドの前方一致で判定される。AI は `git -C . add` のような書き方もするので、コマンド単位で列挙すると正しい作業まで止まる。道具単位で許可し、破壊的な操作だけを `--disallowedTools` で塞ぐ
- 前方一致は、コマンドの語の単位で効く。`Bash(python3 scripts/:*)` は `python3 scripts/phase.py` にも一致しない。`Bash(python3:*)` のように、先頭のコマンド名で書く
- Issue の本文は `loop.sh` が人間側の `gh` で取得し、`tasks/issue-N.md` で渡す。AI に GitHub の認証を持たせない

## 評価関数を疑う

[利用例](https://github.com/gghatano/agent-loop-example/blob/main/docs/walkthrough.md)では、AI のエージェントは値を直書きしなかった。
穴があったのは、人間（の役）が書いたテストのほうだった。誤実装24個のうち17個が check を通った。

- **一部の項目だけを assert するテストは、見ていない項目の直書きや取り違えを通す。** 出力のすべての項目を、期待値の表と完全一致で比べる
- **期待値を実装と同じ関数で作らない。** 実装の誤りがそのまま期待値に写る
- **データが素直だと、エスケープ漏れや境界の誤りは見えない。** HTML を含む値、未知の列挙値、重複、0、同じ日、をテスト用のデータに入れる
- **データの取得口を差し替えられるようにする。** フィクスチャと別のデータで描画して、フィクスチャの値が出てこないことを確かめれば、直書きを機械で検出できる

テストを書いた本人の「これで十分」は当てにならない。評価関数を変えたら、別の文脈で `/mutate` を回す。
