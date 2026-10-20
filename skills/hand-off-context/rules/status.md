# status の手順

引き継ぎの状態を表示する。ファイルは何も変更しない。

## 1. 情報を集める

`.handoff/handoff.md` がなければ、引き継ぎがないことを伝え、`export` を案内して終える。

**スクリプトを使う場合**：`handoff_tool.py validate` の出力をそのまま使う。検証結果・要約・`metadata.json` の状態・履歴の件数がそろう。

**手作業の場合**：

1. `rules/import.md` の手順 2 と同じ検証を行う
2. frontmatter から `handoff_id`・`kind`・`source_agent`・`created_at`・`project`・`branch` を読む
3. `### In Progress` と `### Pending` の直下にある箇条書きの数を数える（`None` は数えない）
4. `.handoff/metadata.json` の `status` を読む。読めなければ `Unknown` とする
5. `.handoff/history/` にある `.md` ファイルの数を数える

## 2. 現在のブランチと比べる

Git リポジトリなら `git rev-parse --abbrev-ref HEAD` を実行し、引き継ぎの `branch` と異なれば警告に加える。status では、それ以上の照合（コミットの位置など）は行わない。詳しく知りたいと言われたら `diff` を案内する。

## ユーザーへの報告

```text
引き継ぎの状態: .handoff/handoff.md
- handoff_id: 20261018T030000Z-a1b2 ／ 種別: handoff ／ 状態: imported
- 引き継ぎ元: claude-code（2026-10-18T03:00:00Z）
- プロジェクト: example-project ／ ブランチ: feature/example
- 未完了: In Progress 1 件、Pending 2 件
- 検証: 問題なし
- 履歴: 3 件
```

検証の警告や、ブランチの不一致があれば最後に列挙する。
