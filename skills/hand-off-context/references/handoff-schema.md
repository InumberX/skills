# Handoff File の形式（schema_version 1.0）

`.handoff/handoff.md` と `.handoff/metadata.json` の形式を定義する。雛形は `templates/handoff.md` にある。

## frontmatter

ファイルの先頭に `---` で囲んだ frontmatter を置く。**1 行 1 項目の `key: value` 形式に限定する**（ネスト・複数行の値・リスト・コメントは使わない）。YAML ライブラリがない環境でも、各行を最初の `:` で分けるだけで読めるようにするため。

- 文字列はダブルクォートで囲む
- 真偽値は `true` / `false`、値がないことは `null` と書く（どちらも引用符で囲まない）

```yaml
---
schema_version: "1.0"
handoff_id: "20261018T030000Z-a1b2"
previous_handoff_id: "20261017T091200Z-9f3e"
kind: "handoff"
source_agent: "claude-code"
created_at: "2026-10-18T03:00:00Z"
project: "example-project"
branch: "feature/example"
commit: "3f2a9c1e8b7d6a5f4e3d2c1b0a9f8e7d6c5b4a3f"
dirty: true
---
```

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `schema_version` | string | `"1.0"` |
| `handoff_id` | string | 引き継ぎの識別子（次節） |
| `previous_handoff_id` | string / null | 前回の `handoff_id`。初回、または前回の識別子が読めなかったときは `null` |
| `kind` | string | `"handoff"`（作業の引き継ぎ）または `"review"`（レビュー結果） |
| `source_agent` | string | 引き継ぎ元。`"claude-code"`、`"codex"`、またはケバブケースの任意の名前 |
| `created_at` | string | ISO 8601 のタイムゾーン付き日時。`Z`（UTC）でも `+09:00` でもよい |
| `project` | string | Git リポジトリのトップレベルのディレクトリ名。Git 管理外なら作業ディレクトリ名 |
| `branch` | string | ブランチ名。Git 管理外・detached HEAD なら `"Unknown"` |
| `commit` | string | `HEAD` のフル SHA（40 文字）。取得できなければ `"Unknown"` |
| `dirty` | boolean / string | 未コミットの変更（untracked を含む）があれば `true`。取得できなければ `"Unknown"` |

すべてのフィールドが必須である。

## handoff_id

`YYYYMMDDTHHMMSSZ-xxxx` の形式にする。前半は UTC の作成日時、後半は 4 桁の 16 進数（`0-9a-f`）で、エージェントが任意に選ぶ。

- 連番にしないのは、履歴を読まずに採番でき、別のエージェントが同時に作っても衝突しにくいため
- UTC にするのは、文字列として並べるとそのまま時系列順になるため
- `history/` のファイル名にそのまま使う

## 本文

見出しの名前と階層は変えない。import 側が見出しで各セクションを探すため。

| セクション | 必須 | 書くこと |
| --- | --- | --- |
| `# Handoff` | ○ | 本文の先頭に置く |
| `## Task` | ○ | 現在のタスクと目的。`kind: review` ならレビューの対象と範囲 |
| `## Context` | ○ | 背景・制約・前提。ユーザーから受けた指示のうち、引き継ぎ先も守るべきもの |
| `## Progress` | ○ | `### Completed`・`### In Progress`・`### Pending` の 3 つの小見出しを必ず置く |
| `## Decisions` | ○ | 判断ごとに `### Decision N` を置き、`Decision` / `Reason` / `Alternatives` を書く |
| `## Changed Files` | ○ | 表（次節） |
| `## Validation` | ○ | 表（次節） |
| `## Review Findings` | `kind: review` のとき ○ | 表（次節）。`kind: handoff` では省略してよい |
| `## Known Issues` | ○ | 既知の問題・未解決のエラー・マージの衝突など |
| `## Next Actions` | ○ | 番号付きリスト。次に行う作業と、ユーザーへの確認が必要な事項 |
| `## Notes` | 任意 | 上のどれにも入らない補足 |

必須セクションに書くことがなければ、見出しを残したうえで `None` と書く。見出しを消すと、書き忘れなのか該当なしなのかを区別できなくなるため。

### Changed Files

| 列 | 値 |
| --- | --- |
| File | プロジェクトルートからの相対パス。区切り文字は `/` |
| Status | `Added` / `Modified` / `Deleted` / `Renamed` / `Untracked` / `Conflicted` |
| Area | `Staged` / `Unstaged` / `Both` / `Untracked` |
| Description | 変更の内容。エージェントが書く |

File・Status・Area は `git status` の出力から機械的に決める（対応は `rules/export.md`）。手で書くと Git の実際の状態とずれ、import 時の照合が意味をなさなくなるため。

変更がなければ表を置かずに `None` と書く。Git 管理外なら `Unknown` と書く。

### Validation

| 列 | 値 |
| --- | --- |
| Command | 実行した（または実行すべき）検証コマンド |
| Result | `Passed` / `Failed` / `Not run` / `Unknown` |
| Note | 失敗の要点など。なければ空欄 |

### Review Findings

| 列 | 値 |
| --- | --- |
| Severity | `High` / `Medium` / `Low` |
| File | `path/to/file.ts:42` のように行番号まで書く。特定のファイルに属さなければ `-` |
| Finding | 指摘の内容 |
| Suggestion | 修正案 |

## metadata.json

```json
{
  "schema_version": "1.0",
  "handoff_id": "20261018T030000Z-a1b2",
  "status": "ready",
  "imported_by": null,
  "imported_at": null
}
```

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `schema_version` | string | `"1.0"` |
| `handoff_id` | string | 対応する `handoff.md` の `handoff_id` |
| `status` | string | `ready`（export 直後）/ `imported`（import 済み）/ `invalid`（import の検証で不正と判定） |
| `imported_by` | string / null | import したエージェント |
| `imported_at` | string / null | import した日時（ISO 8601） |

`metadata.json` は `handoff.md` のキャッシュである。`handoff_id` が一致しない・欠落している・JSON として読めない場合は、`handoff.md` を正として扱う。

## schema_version の扱い

- 対応しているのは `"1.0"` だけである
- それ以外の値なら import を中止し、ファイルを書き換えずに、対応しているバージョンをユーザーに伝える。形式の違うファイルを推測で読むと、項目を取り違えたまま作業が進むおそれがあるため
- 既存の Handoff File を読めなくなる変更をするときに `schema_version` を上げる。項目を足すだけで既存のファイルも読めるなら上げない
