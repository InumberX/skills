# scripts/handoff_tool.py の使い方

手作業で間違えやすい処理（Git の状態の読み取り、`git status` から Changed Files への変換、Handoff File の検証、秘密情報の検出、ファイルの安全な置き換え）を決定的に行う補助スクリプト。**使わなくてもスキルの全機能は手作業で実行できる。** 使える環境では、手作業よりも結果がぶれないため優先して使う。

標準ライブラリだけで動くため、取り込み先のプロジェクトに追加でインストールするものはない。

## 使えるかを確かめる

Python 3.10 以上が必要である。次のどれかでバージョンを確かめ、最初に 3.10 以上が得られたコマンドを使う。

| 環境 | コマンド |
| --- | --- |
| macOS・Linux | `python3 --version` |
| Windows | `py -3 --version`、または `python --version` |

どれも使えなければ、スクリプトを使わずに手作業の手順で進める。インストールをユーザーに求めない。

## 呼び出し方

スクリプトは、このスキルのディレクトリ（`SKILL.md` があるディレクトリ）の `scripts/handoff_tool.py` にある。作業ディレクトリはプロジェクトの中にしておく。

```text
python3 <このスキルのディレクトリ>/scripts/handoff_tool.py <サブコマンド> [オプション]
```

プロジェクトのルートは、Git リポジトリならそのトップレベル、そうでなければ作業ディレクトリになる。別の場所を対象にするときは `--root <パス>` を付ける（`scan` 以外のサブコマンド）。

## サブコマンド

| サブコマンド | 内容 | 使う手順 |
| --- | --- | --- |
| `info` | `handoff_id`・`created_at`・`project`・`branch`・`commit`・`dirty` を frontmatter の形式で出力する | export 3・4 |
| `changed-files [--limit N]` | `git status` から Changed Files の表を出力する。Description 列は空 | export 3 |
| `scan FILE [--redact]` | 秘密情報を検出し、行番号・セクション・種類を出力する。値そのものは出力しない。`--redact` で該当箇所を `[REDACTED]` に置き換える | export 5 |
| `validate [FILE]` | Handoff File を検証し、要約を出力する。FILE を省くと `.handoff/handoff.md` と `metadata.json` を対象にする | import 2、status |
| `publish DRAFT` | DRAFT を検証し、現在の `handoff.md` を `history/` へ退避してから DRAFT に置き換え、`metadata.json` を `ready` にする。DRAFT が `.handoff/draft.md` なら最後に削除する。秘密情報らしいものがあれば WARNING を出す（拒否はしない） | export 6 |
| `mark --status imported --agent NAME` / `mark --status invalid` | `metadata.json` に import の結果を書く。`handoff.md` がなければ何も書かずに拒否する | import 4 |
| `clear [--history \| --keep N] [--yes]` | 削除対象を一覧にする。`--yes` を付けたときだけ削除する | clear |

## 終了コード

| コード | 意味 |
| --- | --- |
| 0 | 成功 |
| 1 | 問題が見つかった（検証エラー・秘密情報の検出）、または操作を拒否した。拒否したときはファイルを何も変更していない |
| 2 | 引数の誤り |

## publish が拒否する場合

| 出力 | 原因と対処 |
| --- | --- |
| `the draft is not a valid Handoff File` | 下書きの frontmatter が不正。続けて出る `ERROR` を直す |
| `the draft reuses the current handoff_id` | 下書きの `handoff_id` が現在の引き継ぎと同じ。`info` で新しい値を取り直す |
| `handoff_id ... is not YYYYMMDDTHHMMSSZ-xxxx` | 下書きの `handoff_id` の形式が違う。履歴のファイル名に使うため、`validate` と違って警告ではなく拒否する。`info` で新しい値を取り直す |
| `... already exists` | 退避先の履歴ファイルがすでにある。上書きせずユーザーに伝える（次節） |

## 退避先がすでにある場合

`publish` は、履歴への退避を終えた後で置き換えに失敗することがある（ディスクの空き不足など）。このとき `history/` には退避したファイルが残り、`handoff.md` は元のままなので、再実行すると `already exists` で拒否される。

その履歴ファイルの中身が現在の `handoff.md` と同じかを確かめ、同じなら、ユーザーの確認を得てから履歴ファイルを削除して再実行する。違う場合は、どちらを残すかをユーザーに尋ねる。

## 書き込みの安全性

`publish`・`mark`・`scan --redact` は、同じディレクトリの一時ファイルに書いてから置き換える。途中で失敗しても、元のファイルが半端な内容で残ることはない。置き換えるファイルの権限と改行コード（LF / CRLF）はそのまま保つ。先頭に BOM があるファイルも読める。
