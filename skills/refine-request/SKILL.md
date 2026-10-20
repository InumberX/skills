---
name: refine-request
description: "Check a draft request to an AI coding agent before it is sent, and point out what is missing — the exact target (paths, line ranges, a reference implementation), what may be changed and where to stop (commit only, no PR), wording constraints (title/body language, no mentions), the premises and sources the agent should rely on, and anything the user changed by hand since the last message. Returns the gaps as questions and a revised draft with placeholders, without inventing facts and without carrying out the request. Use when the user asks to review, check, improve, or tighten a prompt, instruction, request, or task description for Claude Code, Codex, or another agent, or asks 'will this be understood?' before sending it."
---

# refine-request

AI エージェントへの依頼文を、送る前に点検するスキル。抜けている情報を指摘し、埋めるべき箇所をプレースホルダーにした改善案を返す。

依頼の手戻りは、AI の能力より、依頼文に書かれていなかったことで起きることが多い。対象のファイルを特定していない、どこまでやってよいか書いていない、PR の言語を指定していない、手で直したファイルを伝えていない、などである。これらは AI 側の規約（`CLAUDE.md` など）に書いても防げず、依頼する側が依頼文に書くしかない。

## いつ発動するか

次のいずれかに該当する場合に使う:

- 「この依頼文をチェックして」「プロンプトを見直して」と依頼された
- 「この指示で伝わる？」「Codex に渡す前に確認して」と聞かれた
- エージェントに渡す Issue やタスクの説明文を、書き直すよう依頼された

依頼文そのものを実行するスキルではない。点検を頼まれたら、点検と改善案で止める。

## 参照ファイルの選択

| 状況 | 参照ファイル |
| --- | --- |
| どの依頼文でも（毎回読む） | `rules/checklist.md` |

## 手順

### 1. 依頼の種類を見分ける

依頼文が何を求めているかを、1 行で書き出す。実装、調査、レビュー、PR の作成、複数リポジトリへの横展開、相談（どちらにすべきか）など。種類によって、必要な情報が違う。

### 2. チェックリストと突き合わせる

`rules/checklist.md` を読み、依頼の種類に関係する項目だけを突き合わせる。すべての項目を機械的に当てはめない。関係の無い項目まで指摘すると、本当に足りないものが埋もれる。

依頼文に貼り付けられたログや出力に、トークン・パスワード・秘密鍵のような値が含まれていないかも確かめる。含まれていたら、最初に指摘する。指摘では値そのものを引用せず、場所（何行目の、どの項目か）だけを示す。改善案では、その値を `***` に置き換える。点検の出力に値を書き写すと、秘密が広がる先を増やすことになる。

### 3. 足りない情報を質問にする

足りない情報は、依頼者が答えられる質問の形にし、**作業を誤らせるもの**（対象・範囲と終点・前提）から順に並べる。文面の好みのような、無くても作業が大きく外れないものは後に回す。

質問は、「対象を明確にしてください」ではなく、「対象のファイルはどれですか（パスで）」のように書く。

**事実を補わない。** ファイルパス、ブランチ名、Issue 番号、数値のように依頼者しか知らない情報は、推測で埋めずにプレースホルダーにする。推測した値が改善案に入ると、依頼者が確かめずに送ってしまい、間違った前提で作業が進む。

### 4. 改善案を示す

元の依頼文を土台に、足りない箇所を `<要記入: ...>` のプレースホルダーで示した改善案を書く。元の文の意図や言い回しは、必要が無ければ変えない。依頼者の文体を書き換えることは、このスキルの目的ではない。

## 出力フォーマット

```markdown
## 足りない情報
1. <項目>: <なぜ必要か> → 質問: <依頼者に答えてほしいこと>

## 改善案
<元の依頼文に、足りない箇所を `<要記入: ...>` で加えたもの>

## 問題なかった点
- <すでに書けていて、そのままでよいもの>（無ければ省く）
```

足りない情報が無ければ、「このまま送って問題ない」と書き、理由を 1 行添える。

## 拡張ガイド（将来の作業者向け）

点検の観点を足すときは、`rules/checklist.md` の該当する分類に追記する。特定のプロジェクトでしか意味を持たない観点（そのプロジェクトのディレクトリ構成など）は、各プロジェクトの `.claude/skills/` に置く。
