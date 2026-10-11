# spec

AI に読ませる仕様。`design/` と `mock/` から導く。**人間は直さない**（直したいなら design を直す）。

## 書き方
- 冒頭に `sources` を置き、どの出典（design の節・mock のファイル）から導いたかを書く。ハッシュは `python3 scripts/docs_check.py --stamp <file>` が記録する
- 実装と評価に要る規則だけを書く。理由は書かない（design と decisions にある）
- 規則は表にし、具体的な入出力の例を必ず添える。例がなく一意に決まらないものは書かず、`discussions/` に出す
- 規則には ID（`R-xx`）を付ける。テスト名・Issue の Done から ID で参照できる

## 出典が変わったら
check が `出典が変わった` で赤くなる。`/sync-spec` で spec を追従させる。
