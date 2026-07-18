---
name: create-skill
description: "Create a new Agent Skill following this repository's conventions — task-oriented naming, Agent Skills directory format, progressive disclosure, and placement rules (central skills repo vs each project's .claude/skills). Use whenever the user asks to add, create, draft, port, or restructure a skill, wants to turn existing docs, rules, or conversation knowledge into a skill, or asks where new AI-facing knowledge should live."
---

# create-skill

新しいスキルを作成するためのスキル。Issue #1 で決定した規約(Agent Skills 標準形式・タスク単位・段階的読み込み・配置の線引き)に沿ったスキルを、迷わず同じ形で作れるようにする。

## いつ発動するか

次のいずれかに該当する場合に使う:

- 「スキルを作って」「〜のルールをスキル化して」と依頼された
- 既存のドキュメント・CLAUDE.md の一部・会話で決まった規約をスキルに変換したいと依頼された
- 新しい知識やルールをどこに置くべきか(本リポジトリか各プロジェクトの `.claude/skills/` か)を相談された
- 既存スキルの分割・統合・移設(プロジェクト → 中央への昇格など)を依頼された

## 参照ファイルの選択

依頼内容に応じて読むファイルを決定する。

| 依頼パターン | 参照ファイル |
|---|---|
| 「スキルを作って」(全工程) | `rules/*.md` 全て + `templates/SKILL-template.md` |
| 「どこに置くべきか」「中央に昇格すべきか」の相談のみ | `rules/placement.md` |
| 「形式・命名・frontmatter を確認して」 | `rules/format.md` |
| 既存スキルの書き直し・分割・肥大化の解消 | `rules/writing.md`(形式も変える場合は `rules/format.md` も) |
| 雛形だけ欲しい | `templates/SKILL-template.md` |

## 作成手順

### 1. タスクを特定する

スキルは技術トピック(React、CSS)ではなく**タスク(動詞)単位**で切る。最初に次の一文を書けるか確認する:

> このスキルは、ユーザーが「◯◯して」と依頼したときに発動する。

この一文が書けない場合、単位が大きすぎるか、タスクではなく知識の羅列になっている。知識(React の書き方、CSS 規約など)は単独のスキルにせず、それを使うタスクスキルの `rules/`・`references/` に配置する。

### 2. 配置先を決める

`rules/placement.md` を読み、本リポジトリ(横断知識)か各プロジェクトの `.claude/skills/`(コード密着)かを決定する。**実コードのパスを引用するルールは必ずプロジェクト側に置く。** 迷ったらプロジェクト側に置く(中央への昇格は後からできる)。

### 3. 雛形から作る

`templates/SKILL-template.md` をコピーし、`rules/format.md` の形式規約(ディレクトリ構成・frontmatter・命名)に従って埋める。

### 4. 書き方の原則に従う

`rules/writing.md` を読んでから本文を書く。要点:

- SKILL.md は小さな入口に徹し、詳細は `rules/`・`examples/` に分割する(段階的読み込み)
- lint・formatter・typecheck で機械検出できるルールは書かない
- 「何をするか」だけでなく「なぜそうするか」を書く

### 5. チェックリストで確認する

完成前に以下を確認する:

- [ ] `name` はケバブケースの動詞句(例: `review-pr`、`create-component`)になっている
- [ ] `description` は英語で、「何をするか」と「いつ使うか(ユーザーの依頼パターン)」の両方を含む
- [ ] 本文冒頭に「いつ発動するか」セクションがある
- [ ] SKILL.md が長くなりすぎていない(目安 150 行。超えるなら `rules/` へ分割)
- [ ] 分割したファイルには SKILL.md から「いつ読むか」の案内がある(マッピング表など)
- [ ] 機械検出可能なルールを書いていない
- [ ] 配置先が `rules/placement.md` の線引きに合っている

## 拡張ガイド(将来の作業者向け)

本スキル自体の規約(形式・配置・書き方)を変更する場合は、該当する `rules/*.md` を更新し、必要なら Issue #1 の決定事項との差分をコミットメッセージに明記する。規約の変更は既存スキル全体に影響するため、変更前に既存スキルとの整合を確認する。
