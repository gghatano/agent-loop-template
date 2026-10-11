# Pack: mock-replica

モック（HTML/CSS）を正として、実装を見た目で一致させるプロジェクト用の差し込みパック。

## 入れ方
```sh
cp -rn packs/mock-replica/. .          # 既存ファイルは上書きしない（GNU cp の新しい版では --update=none）
cat AGENTS.mock-replica.md             # 中の3行を AGENTS.md の Project rules に足し、ファイルは消す
cp vrt.json.example vrt.json           # 画面とルートを書く（/mock-spec が作ってもよい）
rm -rf packs                           # パックの元ファイルはもう要らない
```
`scripts/check.sh` の STEPS に次を足す。
```
"mock-unchanged|git diff --exit-code --stat $(git rev-parse -q --verify origin/main || git rev-parse HEAD) -- mock/ fixtures/"
"vrt|uv run python scripts/vrt.py"
```
開発依存に `playwright` と `pillow` を足し、Chromium を用意する。

## 流れ
1. `mock/` にモックを置く
2. `/mock-spec` で仕様の下書き（`docs/mock-spec.md`）・fixtures・`vrt.json`・画面ごとの Issue 案を作る。**未定義の項目を人間が決める**
3. `/mock-tests` で評価関数を組む。実装がない状態で check が赤いことを確かめる
4. 画面ごとの Issue を `/goal` か `scripts/loop.sh` に渡す
5. `/mutate` で評価関数の強さを確かめる

## 中身
| ファイル | 役割 |
|---|---|
| `docs/mock-replica.md` | モック再現の知識。VRT が見ているもの・見ていないもの、実際に踏んだ差 |
| `scripts/vrt.py` | モックと実装を同じ Chromium で撮ってピクセル差分を数える。`vrt.json` で設定 |
| `.claude/skills/mock-spec` | モックから仕様・fixtures・vrt.json・Issue 案を作る |
| `.claude/skills/mock-tests` | 仕様から、単体・結合（全項目の完全一致）・E2E のテストを作る |
| `.github/ISSUE_TEMPLATE/mock-screen.yml` | 画面ごとの Issue。Done を最初から機械判定の形にしてある |

## 試した結果
[agent-loop-example](https://github.com/gghatano/agent-loop-example) のモック3画面に、`/mock-spec` を細かい指示なしで一度だけ実行した。
- 表示ルール（¥ とカンマ、`YYYY/MM/DD`、en dash の期間、両端を含む日数、状態ラベル、タイトル）は、利用例で人間が確かめたものとすべて一致した
- 「未定義」には20項目が挙がった。その中に、利用例で誤実装がテストをすり抜けた箇所（役割の決め方、同名、未知の状態、メンバー0名）が含まれていた。テストを書く前に、穴になる場所を人間に返せる
- 役割は、名前から推測せずデータに `role` を持たせる設計を選んだ（未定義 U4 として人間に返した）。利用例とは別の、正当な選択肢である
