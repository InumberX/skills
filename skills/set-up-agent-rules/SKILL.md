---
name: set-up-agent-rules
description: "Write the shared baseline coding rules (for example, code comments: keep them minimal when the code is clear, fix or remove stale ones, no change history, assertions checked against the code) into the always-loaded instruction file so the agent follows them while writing code, not only at review time — the project's CLAUDE.md / AGENTS.md, or the user-level ~/.claude/CLAUDE.md / ~/.codex/AGENTS.md when the user asks. Picks the file that holds the project's conventions, checks for rules that already say the same thing, inserts the bundled template between start and end markers or replaces only what lies between them, and reports what changed. Use when the user asks to set up, add, or update the basic or baseline rules in CLAUDE.md or AGENTS.md, to make the coding rules apply while coding, or to bring a project's agent instructions up to the shared baseline. A single new lesson from a session belongs to the record-lesson skill instead."
---

# set-up-agent-rules

共有のスキルリポジトリが持つ**基本のコーディングルール**（`templates/coding-rules.md`）を、常に読み込まれる指示ファイル（`CLAUDE.md` / `AGENTS.md`）に書き込むスキル。

レビューの観点（`review-pr` の `rules/`）はレビューのときにしか読まれない。コードを書いている最中に守らせたいルールは、作業のたびに読み込まれるファイルに置く必要がある。本スキルは、その書き込みを毎回同じ形で行い、雛形が更新されたときに差し替えられるようにする。

## いつ発動するか

次のいずれかに該当する場合に使う:

- 「CLAUDE.md（AGENTS.md）に基本的なルールを書いて」と依頼された
- 「コーディングのときにもこのルールが効くようにして」と依頼された
- 「基本ルールを最新にして」「このプロジェクトの指示ファイルを整えて」と依頼された

会話の中で出た 1 件の教訓を書き留める依頼（「覚えておいて」「次から気をつけて」）は `record-lesson` の担当で、本スキルは使わない。

## 手順

### 1. 書き込み先を決める

ユーザーが指定していればそれに従う。指定が無ければ、今の作業リポジトリの指示ファイルにする。

| リポジトリの状態 | 書き込み先 |
| --- | --- |
| `CLAUDE.md` と `AGENTS.md` の両方があり、片方がもう一方を読み込むだけ（`@AGENTS.md` の 1 行など） | 読み込まれる側（規約の本体） |
| 両方あり、どちらにも規約が書かれている | 規約が多く書かれている方。もう一方にも要るかはユーザーに確かめる |
| 片方だけある | そのファイル。もう一方のツールはこのファイルを読まない（`CLAUDE.md` だけなら Codex、`AGENTS.md` だけなら Claude Code）ため、報告の「効く範囲」にどちらのツールに効くかを書く。もう一方のツールも使っているなら、「どちらも無い」の行の形（`AGENTS.md` を本体にし、`CLAUDE.md` から読み込む）に揃えることを提案する |
| どちらも無い | `AGENTS.md` を作って本体にし、`CLAUDE.md` には `@AGENTS.md` の 1 行だけを書く。Claude Code と Codex のどちらでも読まれるようにするため |

ユーザー単位の指示ファイル（Claude Code は `~/.claude/CLAUDE.md`、Codex は `~/.codex/AGENTS.md`）は、ユーザーが指定したときだけ書き込む。そのユーザーの全プロジェクトに効く一方、チームの他の人には効かないため、プロジェクトの代わりに勝手に選ばない。両方のツールを使っているなら、両方に同じ範囲を書く。

### 2. 既存のルールと突き合わせる

`templates/coding-rules.md` を読み、書き込み先に次のものが無いかを確かめる。

- 本スキルの開始の目印（`<!-- inumberx-skills/set-up-agent-rules: ... -->`）と終了の目印（`<!-- /inumberx-skills/set-up-agent-rules -->`）：その間は前回書き込んだもの。手順 3 で差し替える
- 雛形と同じ趣旨のルール（雛形の `###` の見出しの語と、その言い換えで探す。例：「コメント」「comment」）：目印の外にあるものが対象。言い回しが違っても同じ内容なら二重に書かない。雛形の文面に寄せてまとめるか、プロジェクトの文面を残すかをユーザーに提案する
- 雛形と食い違うルール（「関数ごとに必ずコメントを書く」など）：書き込まずに、どちらを採るかをユーザーに確かめる。プロジェクトの決まりを黙って上書きしないため

### 3. 書き込む

雛形の開始の目印から終了の目印までを、見出しのレベルを除いてそのまま書き込み先に入れる（雛形の先頭の見出しと説明は書き込まない）。

- 目印が既にあれば、開始と終了の目印の間だけを差し替える。目印の外にプロジェクトが足したルールには、同じ見出しの下にあっても触れない。差し替えるときは、前回の書き込みで使っていた見出しのレベルを引き継ぐ。雛形のレベルに戻すと、書き込み先の見出しの構成が崩れるため
- 開始の目印だけがあり終了の目印が無い場合は、どこまでが前回の書き込みか決められないので、差し替えずにユーザーに確かめる
- 目印が無ければ、既存の規約の節の近くに置く。ファイルの見出しの階層が雛形と違う場合は、見出しのレベルだけを合わせる。同じ名前の見出し（「コーディングのルール」など）が目印の外に既にあれば、その節のすぐ後に置き、見出しが重なることを報告に書く
- 目印のコメントは消さない。次に雛形が更新されたとき、差し替える範囲を決める手がかりになる

指示ファイルは作業のたびに全文が読み込まれるため、雛形の外の説明（背景や例）は足さない。詳しい説明は `review-pr` の `rules/code/comments.md` にある。

### 4. 報告する

次の出力フォーマットで報告する。作業リポジトリの変更はコミットしない（コミットは依頼があってから `write-commit` に従う）。

## 出力フォーマット

```markdown
## 書き込んだ先
- <ファイルパス>（新規作成 / 範囲を追加 / 範囲を差し替え）

## 既存のルールとの関係
- <重複・食い違いと、その扱い>（無ければ「なし」）

## 効く範囲
- <このリポジトリで作業する全員 / このユーザーの全プロジェクト>（<Claude Code・Codex / Claude Code のみ / Codex のみ>）
```

## 拡張ガイド（将来の作業者向け）

- ルールを足すときは `templates/coding-rules.md` の目印の間に追記し、frontmatter の `description` に挙げているルールの例も合わせて直す。常に読み込まれるファイルに入るため、言語やフレームワークに依存せず、どの作業でも守ることだけにする。特定の作業でしか使わないルールは、そのタスクのスキルの `rules/` に置く
- 雛形のルールは、`review-pr` の `rules/code/comments.md` のようなレビュー観点と対になっている。片方を変えたら、もう一方の趣旨と食い違っていないかを確かめる
- 置き場所の判断基準は `record-lesson` の `rules/placement.md` と揃えている
