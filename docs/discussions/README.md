# discussions

実装のアイディア、案の比較、未決の問い。**正ではない。** 誰が書いてもよい。

- ファイル名は `YYYY-MM-DD-短い名前.md`。`_template.md` を複製して使う
- 冒頭の `status` は `open`（未決）/ `adopted`（採用）/ `rejected`（却下）/ `superseded`（別の議論に置き換え）
- 採用したら `decisions.md` に1項目足し、`decision:` にその見出しを書き、design に反映する。check が見出しの実在を確かめる
- 却下した議論も消さない。同じ案が何度も出てくるのを防ぐ
- AI は `open` の議論を前提に実装しない。当たったら止めて聞く
