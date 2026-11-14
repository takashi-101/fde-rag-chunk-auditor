# FDE RAG Chunk Auditor（RAGチャンク分割・文脈欠損監査ツール）

[![tests](https://github.com/takashi-101/fde-rag-chunk-auditor/actions/workflows/tests.yml/badge.svg)](https://github.com/takashi-101/fde-rag-chunk-auditor/actions/workflows/tests.yml)

RAG（検索した文書の断片をLLMに渡して回答させる方式）に使う規程やマニュアルを、決まった文字数のチャンク（分割した文書の断片）に分け、文の途中で終わっているチャンクの数を数えるツールです。分割の設定（最大文字数と、隣のチャンクと重ねる文字数）を変えて実行し、結果を比べられます。

## 30秒で読む要点
- **分割は文字数だけで行います**：`chunk_text` は、先頭から `max_chars` 文字ずつ、`max_chars − overlap` 文字ずつずらして切り出します。文や条文の区切りは見ません。
- **判定はチャンクの末尾だけで行います**：`audit_chunks` は、前後の空白を除いた末尾が `。` `）` `」` のどれでもなく、`第(数字)条` でも終わっていないチャンクを、文の途中で終わっているもの（`broken_clauses`）として数えます。
- **標準ライブラリだけで動きます**：外部との通信や有料APIは使いません。テスト30件（正常・境界・異常）を、CI（GitHub Actions による自動テスト）で Python 3.11 と 3.12 で実行しています。

## 見本を動かす
`examples/sample_policy.txt` は架空の情報取扱規程（第1条〜第10条、454文字）です。

```
python examples/run_example.py examples/sample_policy.txt
```
```json
{
  "total_chunks": 2,
  "broken_clauses": 1,
  "avg_chars": 247.0
}
```
既定値（`max_chars=300`、`overlap=40`）では2つに分かれます。1つ目が第6条の途中（「…点検し、そ」）で終わるため、1件と数えます。

```
python examples/run_example.py examples/sample_policy.txt --max-chars 100 --overlap 20
```
```json
{
  "total_chunks": 6,
  "broken_clauses": 4,
  "avg_chars": 92.3
}
```
チャンクを小さくすると6つに分かれ、そのうち4つが文の途中で終わります。`--max-chars` が `--overlap` 以下のときは、`max_chars must be greater than overlap` と表示して終了コード 2 で終わります。

## 出力の項目
| 項目 | 内容 |
|---|---|
| `total_chunks` | チャンクの数（空白だけのチャンクも含む） |
| `broken_clauses` | 文の途中で終わっていると判定したチャンクの数 |
| `avg_chars` | チャンクの平均文字数（小数第1位に丸める。チャンクが無いときは 0.0） |

## 関数
| 関数 | 内容 |
|---|---|
| `chunk_text(text, max_chars=300, overlap=40)` | 固定の文字数で分割したチャンクのリストを返します。空の文字列なら空のリストです。`max_chars` が `overlap` 以下のときは `ValueError` です。 |
| `audit_chunks(chunks)` | `ChunkAuditReport(total_chunks, broken_clauses, avg_chars)` を返します。 |

判定の例：
| チャンクの末尾 | `broken_clauses` に数えるか |
|---|---|
| `…定める。`、`…（例外あり）`、`…「承認」` | 数えない |
| `…第2条`、`…第12条`、`…第１条`（全角数字） | 数えない |
| 空、または空白だけ | 数えない（`total_chunks` と `avg_chars` には含める） |
| `…取扱いを`、`…ですか？`、`…注意！`、`…end.`、`…(注)`（半角括弧）、`…『題名』`、`…第一条`（漢数字） | 数える |

## テスト（30件）
```
python -m unittest discover -s tests -v
```
- 正常：固定長の分割と重なり、既定値での分割、重なりを除いてつなぐと元の文になること、文の終わり・閉じ括弧・条番号で終わるチャンク、件数と平均文字数、見本の実行結果（2通り）。
- 境界：空の文字列、`max_chars` より短い文、文字数がちょうど `max_chars`（重なりあり・なし）、`max_chars = overlap + 1`、負の `overlap`、空のリスト、平均文字数の丸め、空白だけのチャンク、末尾の空白と改行、`？` `！` `.` 半角括弧 `』` 漢数字の条番号。
- 異常：`max_chars` が `overlap` 以下・0、文字列でない入力（`TypeError`）、リストでない入力、文字列でないチャンク、`ChunkAuditReport` の書き換え、見本のスクリプトに不正な設定を渡したとき。

## 制約
- 末尾だけを見ます。文の途中から始まるチャンク（先頭の切断）は数えません。
- 判定の前に前後の空白と改行を取り除くため、改行で終わるチャンクも、改行の前の文字で判定します。
- `？` `！` `.` や半角の `)`、`』` で終わる文も、文の途中で終わっていると数えます。条番号は算用数字（全角を含む）だけを認識し、漢数字の「第一条」は認識しません。
- `overlap` に負の値を渡しても検査しません。その場合、チャンクの間の文字が抜けます。
- 文書の長さによっては、最後のチャンクが直前のチャンクの重なり部分だけになることがあります（例：10文字を `max_chars=10`、`overlap=3` で分けると `["0123456789", "789"]`）。
- 数えるだけのツールです。文の区切りで分割し直す機能はありません。

## ファイル構成
```
src/rag_auditor/
  auditor.py            chunk_text（分割）と audit_chunks（判定）
examples/
  run_example.py        テキストを分割し、判定の結果を JSON で表示
  sample_policy.txt     見本の規程（架空）
tests/                  ユニットテスト
.github/workflows/      CI（Python 3.11・3.12）
```

## ライセンス
MIT
