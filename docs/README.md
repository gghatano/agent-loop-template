# docs

読み手ごとにフォルダを分け、情報は一方向にだけ流す。整合は `scripts/docs_check.py` が check のたびに確かめる。

```
discussions/ ──採用──▶ decisions.md ──反映──▶ design/ ──導出──▶ spec/ ──▶ 実装・テスト
 （議論・案）          （採用した判断）       （人間向け・正）   （AI 向け）
                                                  mock/ ───導出──┘

knowledge/ … 開発のやり方の知識。上の流れとは別に、失敗から育てる
```

| フォルダ | 読み手 | 書き手 | 正か | 中身 |
|---|---|---|---|---|
| [`design/`](design/) | 人間 | 人間（AI は頼まれたときだけ） | **正** | 何を作るか・なぜそうするか。文章と図でよい |
| [`discussions/`](discussions/) | 人間・AI | 誰でも | 正ではない | 実装のアイディア、比較、未決の問い。状態を持つ |
| [`decisions.md`](decisions.md) | 人間・AI | 人間 | 正 | 議論から採用した判断。design に反映する前の橋 |
| [`spec/`](spec/) | AI | AI（`/sync-spec`） | design から導く | 実装と評価に要る規則だけを、表と例で。出典つき |
| [`knowledge/`](knowledge/) | AI・人間 | AI→人間が確認 | — | 開発のやり方、踏んだ罠、失敗ログ |

## ルール
- **事実は一か所にだけ書く。** spec に理由を書かない（理由は design と decisions にある）。design に実装の細部を書かない
- **spec を直したくなったら、design を直す。** spec は design と mock から導くもので、手で直した spec は次の `/sync-spec` で消える
- **議論の結論は、議論の資料に書いて終わりにしない。** 採用したら `decisions.md` に1項目足し、design に反映し、議論の status を `adopted` にする
- **未決（status: open）の議論を前提に実装しない。** AI は open の議論に当たったら止めて聞く
- **knowledge は失敗からしか増やさない。** 根拠は `knowledge/failures.md` の行

## 整合の検査（`scripts/docs_check.py`）
- spec の各ファイルは、冒頭の `sources` に出典（design の節、mock のファイル）とそのハッシュを持つ。出典の内容が変わるとハッシュが合わなくなり、check が赤くなる。`/sync-spec` で spec を追従させてから `--stamp` で記録し直す
- discussions の各ファイルは `status` を持つ。`adopted` なら、`decision` に書いた見出しが `decisions.md` に実在すること
- docs・AGENTS.md・README.md の相対リンクと `#見出し` が切れていないこと
