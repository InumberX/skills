---
name: record-lesson
description: "Turn a mistake, a repeated correction, or a lesson from a session into a short rule and put it where the agent will actually read it next time — the project's CLAUDE.md / AGENTS.md, the project's .claude/skills, or a shared skills repository. Checks first whether the same rule already exists in different words (an existing rule means it is not being followed, not that a new one is needed), rewrites the lesson as trigger + action + reason, and keeps incident logs separate from rules. Use when the user says 'remember this', 'don't do that again', 'add this to CLAUDE.md', 'make this a rule', or 'I've told you this before', when the same correction comes up a second time, or when the user asks to turn retrospective notes, review comments, or a list of stumbling points into rules."
---

# record-lesson

作業中の失敗や、繰り返された指摘を**短いルール**に書き直し、次に同じ場面が来たときに AI が読む場所へ置くスキル。

同じ注意を何度も受けるのは、ルールが無いからとは限らない。ルールがあっても、書かれた場所が読まれない、書き方が曖昧で当てはまる場面が分からない、という理由で守られないことが多い。そのため、本スキルは新しく書く前に既存のルールを探し、書くときは「いつ」「何をするか」が読み取れる形にする。

## いつ発動するか

次のいずれかに該当する場合に使う:

- 「覚えておいて」「次から気をつけて」「二度とやらないで」と言われた
- 「CLAUDE.md に追記して」「ルールにして」と依頼された
- 「前にも言ったよね」「これ 2 回目」と言われた
- 同じセッションで、同じ趣旨の指摘を 2 回受けたと自分で気づいた
- 振り返りのメモ、レビュー指摘、詰まりの一覧からルールを作るよう依頼された

## 参照ファイルの選択

| 状況 | 参照ファイル |
| --- | --- |
| ルールの文面を書く・直す（毎回読む） | `rules/writing.md` |
| どこに書くかを決める（毎回読む） | `rules/placement.md` |

## 手順

### 1. 何が起きたかを 3 点に分ける

次の 3 点を、それぞれ 1〜2 文で書き出す。

- **状況**：何をしようとして、何が起きたか
- **原因**：なぜ起きたか。「不注意」で止めず、何を確かめていなかったかまで書く
- **汎用ルール**：別の場面でも同じ失敗を防げる行動

状況と原因は記録であって、ルールではない。ルールとして書くのは 3 点目だけにする。日付や個別のファイル名を含んだ記録を規約の場所に書くと、次に読んだ人が「この時だけの話」か「守るべき規約」かを区別できなくなるため。

### 2. 既存のルールを探す

置き場所の候補（`rules/placement.md`）を、**文言ではなく対象と動作のキーワード**で検索する。同じ趣旨のルールは、毎回違う言い回しで書かれる。文言で照合すると一致せず、同じルールが「新規」として何度も追加される。

```bash
git grep -n -i -e '<対象の語>' -e '<動作の語>' -- CLAUDE.md AGENTS.md '.claude/' 'docs/'
```

`git grep` は追跡されているファイルしか見ないため、`CLAUDE.local.md` のような未追跡のファイルや、ユーザー単位の `~/.claude/CLAUDE.md` は別に開いて確かめる。

見つかった場合は、新しいルールを足さない。**既存のルールが守られなかった**ものとして扱い、原因を次のどれかに分けて直す。

| 守られなかった原因 | 直し方 |
| --- | --- |
| 発動条件が曖昧で、当てはまると気づけなかった | `rules/writing.md` に沿って、条件を観察できる形に書き直す |
| 読まれない場所にあった（作業と関係ないファイル、長い文書の奥） | 作業時に読まれる場所へ移す（`rules/placement.md`） |
| 書いてあるが、確認の手段が無い | 確認の方法（コマンド、見る場所）を書き足す。機械的に検出できるなら lint やテストを提案する |

### 3. ルールの文面を書く

`rules/writing.md` に従って書く。「いつ」「何をする」を 1 文に、「なぜ」を続く 1 文にして、1 つの箇条書きにまとめる。

### 4. 置き場所を決めて書く

`rules/placement.md` に従って置き場所を決める。関連するルールの近くに追記する。ファイルの末尾に足し続けると、関連するルールが散らばって読まれなくなるため。

置き場所が今の作業リポジトリの外（共有のスキルリポジトリ、別プロジェクト）なら、自分では書き込まず、追記する文面と置き場所をユーザーに提案する。

### 5. 報告する

次の出力フォーマットで、何をどこに書いたかを報告する。

## 出力フォーマット

```markdown
## 記録したルール
- <ルール（いつ・何をする・なぜ）>
- 置き場所: <ファイルパス>（<節の名前>）

## 既存ルールとの関係
- 新規 / 既存のルールを修正（<元の文面> → <新しい文面>）/ 既存のルールを移動（<移動元> → <移動先>）

## 書かなかったもの
- <ルールにしなかった記録と、その理由>（無ければ「なし」）
```

依頼する側の書き方に関するルール（「依頼文にファイルパスを書く」など）は、AI 側のファイルに書いても効かない。その場合は、ルールとしてユーザーに示すだけにして、書き込まない。

## 拡張ガイド（将来の作業者向け）

ルールの書き方の観点は `rules/writing.md`、置き場所の判断は `rules/placement.md` に追記する。置き場所の基準は `create-skill` スキルの `rules/placement.md` と揃えている。どちらかを変えるときは、もう一方も確認する。
