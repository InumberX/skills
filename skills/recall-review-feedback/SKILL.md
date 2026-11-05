---
name: recall-review-feedback
description: "Collect the review feedback the user received on their own past pull requests in a repository before starting new work there — list their PRs, fetch all three kinds of comments (review bodies, inline review comments, conversation comments), drop approvals and their own replies, check how each remaining point was resolved, and restate each as a rule to apply in the upcoming work. Use when the user asks to check, recall, or list what reviewers pointed out before, says something like 'what did I get flagged for last time in this repo', or is about to start work in a repository they rarely touch and wants to avoid repeating past mistakes."
---

# recall-review-feedback

あるリポジトリで作業を始める前に、ユーザー自身の過去の PR に付いたレビューの指摘を集め、これからの作業で守る形に整理するスキル。対象は GitHub の PR に付いたコメントで、コードは変更しない。

普段触らないリポジトリでは、レビュアーが以前に指摘したことを忘れたまま、同じ書き方を繰り返しやすい。指摘は PR ごとに散らばっていて、承認のコメントに埋もれているため、まとめて読み直さないと拾えない。

## いつ発動するか

次のいずれかに該当する場合に使う:

- 「以前の指摘を確認して」「前回のレビューで何を言われたか洗い出して」と依頼された
- 普段触らないリポジトリで作業を始める前に、過去の指摘を踏まえたいと言われた
- 複数のリポジトリにまたがる作業の前に、それぞれのリポジトリでの指摘を確かめたいと言われた

指摘を規約として残す作業（`CLAUDE.md` やスキルへの追記）は本スキルでは行わず、`record-lesson` に引き継ぐ。

## 手順

### 1. 対象を決める

対象のリポジトリと、誰の PR を見るかを決める。指定が無ければ、作業するリポジトリでの、ユーザー自身が作成した PR を対象にする。関連するリポジトリ（API とスキーマ定義のように、一緒に変更することが多いもの）があれば、それも対象に含めるかをユーザーに確かめる。

```bash
gh api user --jq .login   # ユーザーのログイン名
```

### 2. PR を一覧にする

```bash
gh pr list --repo OWNER/REPO --author LOGIN --state all --limit 50 \
  --json number,title,state,createdAt,url
```

件数が多い場合は、新しいものから読む。古い指摘は、その後の規約の変更で意味を失っていることがある。

### 3. 3 種類のコメントをすべて取得する

PR のコメントは 3 か所に分かれている。`gh pr view --comments` は行に付いたコメントを含まないので、API で 3 種類とも取る。

```bash
gh api repos/OWNER/REPO/pulls/NUMBER/reviews \
  --jq '.[] | select(.body != "") | "[review \(.state) by \(.user.login)]\n\(.body)\n"'
gh api repos/OWNER/REPO/pulls/NUMBER/comments \
  --jq '.[] | "[inline by \(.user.login) \(.path):\(.line // .original_line)]\n\(.body)\n"'
gh api repos/OWNER/REPO/issues/NUMBER/comments \
  --jq '.[] | "[comment by \(.user.login)]\n\(.body)\n"'
```

| 種類 | 取得先 | 含まれるもの |
| --- | --- | --- |
| レビュー本文 | `pulls/NUMBER/reviews` | 承認・変更要求に添えた総評 |
| 行のコメント | `pulls/NUMBER/comments` | 特定の行への指摘、修正案（`suggestion`） |
| 会話のコメント | `issues/NUMBER/comments` | PR 全体への質問・懸念、フォローアップの提案 |

### 4. 指摘だけを残す

次のものは除く。

- 承認だけのコメント（「LGTM」「ありがとうございます」など、内容の無いもの）
- ユーザー自身のコメント（レビュー依頼や返信）。ただし返信は、次の手順で対応を確かめるのに使う
- 自動化されたボットの定型通知（デプロイ完了など）。ボットのレビューでも、具体的な指摘があれば残す

残ったものを、重要度（修正の要求 / 任意 / 好みの差）と、指摘の種類（コードの書き方、テスト、命名、運用上の懸念など）で分ける。指摘が 1 件も無いことも、そのまま結果として伝える。件数を増やすために、承認のコメントを指摘として扱わない。

### 5. 対応を確かめる

各指摘について、どう対応されたかを確かめる。ユーザーの返信と、指摘の後に足されたコミットを見る。

```bash
gh pr view NUMBER --repo OWNER/REPO --json commits --jq '.commits[].messageHeadline'
```

| 対応 | 判断の材料 |
| --- | --- |
| 対応済み | 返信に「直しました」とある、指摘の後に該当するコミットがある、修正案が取り込まれている |
| 見送り | 返信で見送る理由が書かれている |
| 未対応 | 返信もコミットも無い。フォローアップとして残すべきかをユーザーに確かめる |

### 6. 次の作業で守る形に書き直す

指摘を、その PR 固有の事情（ファイル名、関数名、当時の不具合）から切り離し、「次の作業で何をするか」の形に書き直す。

- Bad: 「`foo.go` の 66 行目のコメントが長い」
- Good: 「コード内のコメントに修正前の経緯を書かない。経緯は PR 本文に書く」

これからの作業の内容が分かっている場合は、指摘ごとに、その作業のどこで当てはまるかを添える。

## 出力フォーマット

```markdown
## 対象
- リポジトリ: OWNER/REPO（PR N 本、期間 YYYY-MM〜YYYY-MM）

## 指摘
1. **（次の作業で守る形の一文）**
   - 出典: PR の URL（指摘した人、重要度）
   - 内容: 何が指摘されたかの要約
   - 対応: 対応済み / 見送り / 未対応（根拠）
   - 次の作業での当て方: （分かっていれば）

## 指摘が無かった PR
- N 本（承認のみ、またはコメント無し）
```

PR は絶対 URL で書く。`#123` のような短い表記は、別のリポジトリの番号として解決されることがある。

同じ趣旨の指摘が複数の PR で出ていたら、`record-lesson` で規約として残すことを提案する。

## 拡張ガイド（将来の作業者向け）

- 対象を GitHub 以外（GitLab のマージリクエストなど）に広げる場合は、取得のコマンドを `references/` に分けて置き、SKILL.md には手順の骨格だけを残す
- 特定のリポジトリで繰り返し出る指摘は、本スキルに書き足さず、そのリポジトリの `CLAUDE.md` や `.claude/skills/` に置く（`record-lesson` の配置の判断に従う）
